"""Dispatching a page number to whatever answers it.

A pattern is literal digits and named fields. `82{post_id:int}` answers every
page number beginning 82 and hands the rest over as `post_id`, so a page builder
is written in terms of the post it is showing rather than in terms of the digits
that named it. The scheme then lives in one place, and `address_for` reads it
backwards, which is what stops a page number being respelled at every site that
links to one.

Because a viewdata request is terminated -- `*8#` and `*82489493#` are
unambiguously different -- page numbers need not be prefix-free, only distinct.
That is what lets fields vary in width and stay short, and it is the whole
reason this is not simply a dictionary of numbers.

Two rules keep matching predictable:

**Most literal wins.** Candidates are tried by how much of the pattern is fixed
digits, most first, so `90` beats `9{n:int}` however they were registered. A
routing table that depended on registration order would be a table whose meaning
changed when someone tidied it.

**Fields must be separable.** A page number has no separators, so two fields
can only be told apart if all but the last has a width known in advance.
`{year:int(4)}{month:int(2)}` is fine; two bare `int` fields running together
are refused at registration rather than matched arbitrarily.

Nothing here knows what a page is. The router maps addresses to targets, and
`sextile.application` decides that a target is something that builds a page.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final

from sextile.addressing import PageAddress, UnknownPageError

_FIELD: Final = re.compile(r"\{(?P<spec>[^{}]*)\}")

#: A converter, optionally given an argument: `int` or `int(4)`.
_CONVERTER: Final = re.compile(r"(?P<name>[A-Za-z_][A-Za-z_0-9]*)(?:\((?P<argument>[^()]*)\))?")

#: What `{name}` means when nothing else is said. Every field of a page number
#: is numeric, so there is only one sensible default.
_DEFAULT_CONVERTER: Final = "int"


class RouteError(ValueError):
    """A route, keyword or converter that could not be registered."""


class NoSuchRouteError(LookupError):
    """An address was asked for that cannot be built."""


class Converter:
    """How one field of a page number is read and written.

    ``field_pattern`` matches the field's digits; ``width`` is how many digits
    it always takes, or None when it varies. ``parse`` may raise ``ValueError``
    to reject digits its pattern could not exclude -- the 31st of February
    passes any regex worth writing.
    """

    def __init__(
        self,
        *,
        field_pattern: str,
        width: int | None = None,
        parse: Callable[[str], object] | None = None,
        format: Callable[[object], str] | None = None,
    ) -> None:
        self.field_pattern = field_pattern
        self.width = width
        self._parse = parse
        self._format = format

    def to_value(self, digits: str) -> object:
        """The value these digits stand for. May raise ``ValueError``."""
        return digits if self._parse is None else self._parse(digits)

    def to_digits(self, value: object) -> str:
        """How this value is written, or raise ``NoSuchRouteError``.

        The result is checked against the field's own pattern, so a value that
        would build something which is not a page number -- a negative id, a
        date where a number belongs -- fails here rather than producing an
        address that names nothing.
        """
        try:
            digits = str(value) if self._format is None else self._format(value)
        except (TypeError, ValueError, AttributeError) as error:
            raise NoSuchRouteError(f"{value!r} cannot be written as a field") from error
        if re.fullmatch(self.field_pattern, digits) is None:
            raise NoSuchRouteError(f"{value!r} is not a value this field can hold")
        return digits


def _to_date(digits: str) -> date:
    return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))


def _from_date(value: object) -> str:
    if not isinstance(value, date):
        raise TypeError(f"{value!r} is not a date")
    return f"{value:%Y%m%d}"


#  A leading zero is refused so that one page cannot have two numbers. Zero
#  itself is a number, and is spelled the one way.
INTEGER: Final = Converter(field_pattern=r"0|[1-9][0-9]*", parse=int)

DATE: Final = Converter(field_pattern=r"[0-9]{8}", width=8, parse=_to_date, format=_from_date)


def fixed_integer(width: int) -> Converter:
    """A whole number written in exactly ``width`` digits, padded with zeros.

    The leading-zero rule inverts here, and for the same reason it exists. A
    variable-width field refuses a leading zero because `0042` and `42` would be
    two numbers for one page; a fixed-width field *requires* the padding,
    because with the width settled there is again only one spelling of each
    value.

    Fixed widths are what let fields sit next to one another. A page number has
    no separators, so two fields can only be told apart if all but the last is
    of a width known in advance.
    """
    if width < 1:
        raise RouteError(f"a field of {width} digits could hold nothing")
    return Converter(
        field_pattern=rf"[0-9]{{{width}}}",
        width=width,
        parse=int,
        format=lambda value: _padded(value, width),
    )


def _padded(value: object, width: int) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{value!r} is not a whole number")
    #  A value too wide overflows its field rather than being truncated into
    #  a number that means something else; `to_digits` catches it.
    return f"{value:0{width}d}"


type ConverterFactory = Callable[[str | None], Converter]
"""How a converter is made from whatever was written in its brackets.

Given `None` where the pattern named the converter with no brackets at all, so
that `int` and `int()` are not the same thing: the second is somebody who meant
to say a width and did not.
"""


def _unparameterised(name: str, converter: Converter) -> ConverterFactory:
    def make(argument: str | None) -> Converter:
        if argument is not None:
            raise RouteError(f"the {name!r} converter takes no argument")
        return converter

    return make


def _integer(argument: str | None) -> Converter:
    if argument is None:
        return INTEGER
    if not (argument.isascii() and argument.isdigit()):
        raise RouteError(f"{argument!r} is not a width")
    return fixed_integer(int(argument))


@dataclass(frozen=True)
class _Field:
    name: str
    converter: Converter


@dataclass(frozen=True)
class Route[T]:
    """One pattern, and what answers it."""

    pattern: str
    target: T
    name: str | None
    expression: re.Pattern[str]
    parts: tuple[str | _Field, ...]
    literals: int
    """How many characters of the pattern are fixed digits, which is what
    decides the order candidates are tried in."""

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(part.name for part in self.parts if isinstance(part, _Field))


@dataclass(frozen=True)
class Match[T]:
    """A page number, what answers it, and what it said."""

    address: PageAddress
    target: T
    params: Mapping[str, object]


class Router[T]:
    """A table of page-number patterns, and what each of them leads to."""

    def __init__(self) -> None:
        self._routes: list[Route[T]] = []
        self._named: dict[str, Route[T]] = {}
        self._keywords: dict[str, PageAddress] = {}
        self._converters: dict[str, ConverterFactory] = {
            "int": _integer,
            "date": _unparameterised("date", DATE),
        }

    # -- registering --------------------------------------------------------

    def add(self, pattern: str, target: T, *, name: str | None = None) -> None:
        """Route every page number matching ``pattern`` to ``target``."""
        if any(route.pattern == pattern for route in self._routes):
            raise RouteError(f"{pattern!r} is already routed")
        if name is not None and name in self._named:
            raise RouteError(f"{name!r} already names a route")
        route = self._compile(pattern, target, name)
        self._routes.append(route)
        #  Sorted here rather than at match time: the table changes once, at
        #  startup, and is read on every keypress. `sort` is stable, so routes
        #  equally literal keep the order they were added in.
        self._routes.sort(key=lambda candidate: -candidate.literals)
        if name is not None:
            self._named[name] = route

    def converter(self, name: str, converter: Converter | ConverterFactory) -> None:
        """Offer a field shape of the application's own.

        Either a converter, used wherever `{field:name}` appears, or a factory
        taking whatever was written in brackets, so that `{field:name(3)}` can
        mean something the application decides.
        """
        if name in self._converters:
            raise RouteError(f"{name!r} is already a converter")
        self._converters[name] = (
            converter if callable(converter) else _unparameterised(name, converter)
        )

    def alias(self, keyword: str, address: str | PageAddress) -> None:
        """Let ``keyword`` be keyed in place of a page number.

        Prestel was almost entirely numeric, but other viewdata services took
        keywords and there is no reason to be bound by Prestel's database
        conventions. `*MAIN#` is easier to remember than `*1#` and costs
        nothing to offer beside it.
        """
        wanted = keyword.strip().upper()
        if not wanted:
            raise RouteError("a keyword needs some letters")
        if wanted.isascii() and wanted.isdigit():
            raise RouteError(f"{keyword!r} could never be reached: digits name themselves")
        if not (wanted.isascii() and wanted.isalnum()):
            #  The command parser accumulates letters and digits and nothing
            #  else, so anything more could not be keyed.
            raise RouteError(f"{keyword!r} is not something a terminal can send")
        if wanted in self._keywords:
            raise RouteError(f"{keyword!r} is already a keyword")
        self._keywords[wanted] = (
            address if isinstance(address, PageAddress) else PageAddress(address)
        )

    # -- using --------------------------------------------------------------

    def resolve(self, target: str) -> PageAddress:
        """The page a typed request names, whether by number or by keyword.

        Says what the reader meant. Whether anything answers it is the next
        question, and has the same answer for keywords and numbers alike.
        """
        typed = target.strip()
        if typed.isascii() and typed.isdigit():
            return PageAddress(typed)
        found = self._keywords.get(typed.upper())
        if found is None:
            raise UnknownPageError(f"{target!r} names no page here")
        return found

    def match(self, address: PageAddress) -> Match[T] | None:
        """What answers this page number, or None if nothing here does."""
        for route in self._routes:
            found = route.expression.fullmatch(address.digits)
            if found is None:
                continue
            params = self._read(route, found)
            if params is None:
                #  The digits fit the shape but not the meaning -- the 31st of
                #  February. Another route may yet want them.
                continue
            return Match(address=address, target=route.target, params=params)
        return None

    def address_for(self, name: str, **params: object) -> PageAddress:
        """Build the address a named route answers.

        The other direction, so that a page naming where a key leads does not
        respell the numbering scheme.
        """
        route = self._named.get(name)
        if route is None:
            raise NoSuchRouteError(f"{name!r} names no route")
        expected = set(route.fields)
        if set(params) != expected:
            raise NoSuchRouteError(
                f"{name!r} takes {sorted(expected) or 'no fields'}, not {sorted(params)}"
            )
        digits = "".join(
            part if isinstance(part, str) else part.converter.to_digits(params[part.name])
            for part in route.parts
        )
        return PageAddress(digits)

    def keywords(self) -> dict[str, PageAddress]:
        """The named jumps, for a page that wants to list them."""
        return dict(self._keywords)

    def routes(self) -> tuple[Route[T], ...]:
        """Every route, most literal first."""
        return tuple(self._routes)

    # -- reading a pattern --------------------------------------------------

    def _read(self, route: Route[T], found: re.Match[str]) -> dict[str, object] | None:
        params: dict[str, object] = {}
        for part in route.parts:
            if isinstance(part, _Field):
                try:
                    params[part.name] = part.converter.to_value(found.group(part.name))
                except ValueError:
                    return None
        return params

    def _compile(self, pattern: str, target: T, name: str | None) -> Route[T]:
        parts = self._parse(pattern)
        expression = "".join(
            re.escape(part)
            if isinstance(part, str)
            else f"(?P<{part.name}>{part.converter.field_pattern})"
            for part in parts
        )
        return Route(
            pattern=pattern,
            target=target,
            name=name,
            expression=re.compile(expression),
            parts=parts,
            literals=sum(len(part) for part in parts if isinstance(part, str)),
        )

    def _parse(self, pattern: str) -> tuple[str | _Field, ...]:
        if not pattern:
            raise RouteError("a pattern names no page")
        parts: list[str | _Field] = []
        seen: set[str] = set()
        position = 0
        for found in _FIELD.finditer(pattern):
            literal = pattern[position : found.start()]
            if literal:
                parts.append(self._literal(pattern, literal))
            field = self._field(pattern, found.group("spec"))
            if field.name in seen:
                raise RouteError(f"{pattern!r} names {field.name!r} twice")
            self._check_separable(pattern, parts)
            seen.add(field.name)
            parts.append(field)
            position = found.end()
        trailing = pattern[position:]
        if trailing:
            parts.append(self._literal(pattern, trailing))
        return tuple(parts)

    @staticmethod
    def _check_separable(pattern: str, parts: list[str | _Field]) -> None:
        """Refuse a field that runs straight on from a variable-width one."""
        if parts and isinstance(parts[-1], _Field) and parts[-1].converter.width is None:
            raise RouteError(
                f"{pattern!r} has two fields running together, "
                f"the first of no fixed width: there would be no telling them apart"
            )

    @staticmethod
    def _literal(pattern: str, literal: str) -> str:
        if not (literal.isascii() and literal.isdigit()):
            raise RouteError(f"{pattern!r} has {literal!r} in it, and a page number is digits")
        return literal

    def _field(self, pattern: str, spec: str) -> _Field:
        name, _, wanted = spec.partition(":")
        if not name.isidentifier():
            raise RouteError(f"{pattern!r} has {name!r} for a field name")
        found = _CONVERTER.fullmatch(wanted or _DEFAULT_CONVERTER)
        if found is None:
            raise RouteError(f"{pattern!r} has {wanted!r} where a converter belongs")
        make = self._converters.get(found.group("name"))
        if make is None:
            raise RouteError(f"{pattern!r} wants a {wanted!r} field, and there is none")
        try:
            converter = make(found.group("argument"))
        except RouteError as error:
            raise RouteError(f"{pattern!r}: {error}") from error
        return _Field(name=name, converter=converter)
