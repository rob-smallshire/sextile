"""Dispatching a page number to whatever answers it.

A pattern is literal digits and named fields. `82{n:int}` answers every page
number beginning 82 and hands the rest to a handler as `n`, so a handler is
written in terms of the value rather than the digits that named it. The scheme
lives in one place, and `address_for` builds an address from a pattern and named
values, which stops a page number being respelled at every site that links to
one.

Because a viewdata request is terminated -- `*8#` and `*82489493#` are
unambiguously different -- page numbers need not be prefix-free, only distinct.
That is what lets fields vary in width and stay short.

Two rules keep matching predictable:

**Most literal wins.** Candidates are tried by how much of the pattern is fixed
digits, most first, so `90` beats `9{n:int}` however they were registered. A
routing table that depended on registration order would be a table whose meaning
changed when someone tidied it.

**Fields must be separable.** A page number has no separators, so two fields
can only be told apart if all but the last has a width known in advance.
`{year:int(4)}{month:int(2)}` is fine; two bare `int` fields running together
are refused at registration rather than matched arbitrarily.

This module maps addresses to targets; `sextile.application` is what makes a
target build a page. It also holds the page *declaration*: `PageRoute` is
everything about a page stated as a value, and `PageRouter` collects those from
`@router.page` for a handler in a module of its own. A service is a list of
`PageRoute`s, which is what makes registration order unobservable.
"""

import re
from collections.abc import (
    Awaitable,
    Callable,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from dataclasses import dataclass
from datetime import date
from typing import Final

from sextile.page import Page, PageAddress, UnknownPageError

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

    The leading-zero rule inverts here. A variable-width field refuses a leading
    zero because `0042` and `42` would be two numbers for one page; a fixed-width
    field *requires* the padding, because with the width settled each value again
    has one spelling.

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

Given `None` when the pattern named the converter with no brackets, so `int` and
`int()` differ: `int()` is a width omitted by mistake, and is rejected.
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
    sets the order candidates are tried in."""

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(part.name for part in self.parts if isinstance(part, _Field))

    @property
    def keyed(self) -> str:
        """The pattern as a reader would see it: `82<n>`.

        For a page that lists pages. The converter is left out: what a field
        accepts is internal, and the reader keys only the value.
        """
        return "".join(
            part if isinstance(part, str) else f"<{part.name}>" for part in self.parts
        )


@dataclass(frozen=True)
class Match[T]:
    """A page number, what answers it, and what it said."""

    address: PageAddress
    target: T
    params: Mapping[str, object]
    name: str | None = None
    """The route's name, for a caller reading an address back to what it is."""


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
        mean something the service defines.
        """
        if name in self._converters:
            raise RouteError(f"{name!r} is already a converter")
        self._converters[name] = (
            converter if callable(converter) else _unparameterised(name, converter)
        )

    def alias(self, keyword: str, address: str | PageAddress) -> None:
        """Let ``keyword`` be keyed in place of a page number.

        `*MAIN#` is easier to remember than `*1#` and costs nothing to offer
        beside it. Prestel was almost entirely numeric; viewdata need not be.
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

        Returns the address the reader meant. Whether anything answers it is a
        separate question, the same for keywords and numbers.
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
            return Match(
                address=address, target=route.target, params=params, name=route.name
            )
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
        """Return the keyword-to-address jumps, for a page that lists them."""
        return dict(self._keywords)

    def routes(self) -> tuple[Route[T], ...]:
        """Every route, most literal first."""
        return tuple(self._routes)

    def named(self, name: str) -> Route[T]:
        """The route registered under a name, or raise ``NoSuchRouteError``."""
        found = self._named.get(name)
        if found is None:
            raise NoSuchRouteError(f"{name!r} names no route")
        return found

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


# -- declaring a page ------------------------------------------------------

#: A page handler. `None` rather than a page means there is no such page --
#: something *said* to a reader who has not moved, as against somewhere they
#: have gone -- and the session tells the two apart.
type Handler = Callable[..., Awaitable[Page | None]]


@dataclass(frozen=True)
class PageRoute:
    """One page of a service, declared as a value rather than as a decoration.

    Everything about a page is here: its place in the numbering, what builds it,
    what to call it where it is listed, and the words that reach it. The service
    is a list of these. Declaring pages as data makes registration order
    unobservable: converters, pages, middleware and lifespan all arrive in one
    constructor call, so no step has to run before another.

    A route also carries what the service reads back about the page it declared:
    `Sextile.route` and `Sextile.routes` return these, with `keyed` filled
    in. On a route a caller constructs, `keyed` is empty until a service
    registers it: there is no numbering to read it against yet.
    """

    pattern: str
    """The page numbers this answers, as literal digits and named fields."""

    handler: Handler
    """What builds the page. `None` rather than a page means there is no such
    page, which the session shows differently from one it could not build."""

    name: str | None = None
    """What `address_for` calls it. The handler's own name unless given."""

    title: str = ""
    """What to call this page where it is *listed* rather than shown -- in a
    menu, in the history, in the contents. A page with no title is not
    advertised, which is how a title frame stays off the contents."""

    detail: str = ""
    """A second line, wherever the title gets one."""

    keywords: Sequence[str] = ()
    """Words a reader may key instead of the number."""

    label: str | Callable[..., str] | None = None
    """What to call the page in a list of *visited* pages, where the listed
    title is wrong because the number carried a field: the title names the kind
    of page, the label names the one a reader was on. A `str.format` template
    over the route's captured fields (`label="Item {n}"`), or a callable taking
    them as keyword arguments (`label=lambda n: title_of(n)`). None leaves
    `Sextile.label_for` to build one from the title and the fields."""

    keyed: str = ""
    """The number a reader keys, fields shown as `<name>`: `52<n>`. Filled in
    when a service registers the route, from the numbering it registers it into;
    empty on a route a caller has only constructed."""


def declaring[H: Handler](
    keep: Callable[[PageRoute], object],
    pattern: str,
    *,
    name: str | None,
    title: str,
    detail: str,
    keywords: Sequence[str],
    label: str | Callable[..., str] | None,
) -> Callable[[H], H]:
    """A `@page`-style decorator that hands the `PageRoute` it builds to `keep`.

    The one implementation behind `Sextile.page` and `PageRouter.page`: both
    build a `PageRoute` from the same arguments and differ only in where it
    goes, so neither decorator can come to build one differently from the other.

    Args:
        keep: What to do with the route the decorated handler declares --
            `Sextile.add_page` for a service, a list's `append` for a router.
        pattern: The page numbers the handler answers.
        name: What `address_for` calls it, or None to take the handler's name.
        title: What to call it where it is listed rather than shown.
        detail: A second line, wherever the title gets one.
        keywords: Words a reader may key instead of the number.
        label: What to call the page in a list of visited pages, when the title
            is wrong because the number carried a field. See `PageRoute.label`.

    Returns:
        A decorator that registers its handler and returns it unchanged.
    """

    def register(handler: H) -> H:
        keep(
            PageRoute(
                pattern=pattern,
                handler=handler,
                name=name,
                title=title,
                detail=detail,
                keywords=keywords,
                label=label,
            )
        )
        return handler

    return register


class PageRouter:
    """Pages declared together, in a module of their own, for one service.

    A handler that lives apart from the `Sextile` it serves is declared with
    `@router.page(...)`, the same call as `@app.page`, and the module's pages
    reach the service in one spread. Iterating a router yields each `PageRoute`
    in the order they were declared, so a service reads the way its source does.

    Example:
        A module's pages, gathered and spread into a service::

            router = PageRouter()

            @router.page("3", title="By day", keywords=("WHO",))
            async def days(request: PageRequest) -> Page:
                ...

            app = Sextile(pages=[*router, *standard_pages(history="92")])
    """

    def __init__(self) -> None:
        self._routes: list[PageRoute] = []

    def page[H: Handler](
        self,
        pattern: str,
        *,
        name: str | None = None,
        title: str = "",
        detail: str = "",
        keywords: Sequence[str] = (),
        label: str | Callable[..., str] | None = None,
    ) -> Callable[[H], H]:
        """Declare a page beside the function that builds it.

        The same call as `Sextile.page`, for a handler in a module that has no
        application object to hang it on. The route takes the handler's own name
        unless given one.

        Args:
            pattern: The page numbers this answers: literal digits and fields.
            name: What `address_for` calls it, or None for the handler's name.
            title: What to call it where it is listed. Untitled is unadvertised.
            detail: A second line, wherever the title gets one.
            keywords: Words a reader may key instead of the number.
            label: What to call it in a list of visited pages, when the title is
                wrong because the number carried a field. See `PageRoute.label`.

        Returns:
            A decorator that collects its handler's route and returns it
            unchanged, so a service checked strictly stays so past the decorator.
        """
        return declaring(
            self._routes.append,
            pattern,
            name=name,
            title=title,
            detail=detail,
            keywords=keywords,
            label=label,
        )

    def include(self, routes: Iterable[PageRoute]) -> None:
        """Add every route in `routes`, after the ones this router already has."""
        self._routes.extend(routes)

    def __iter__(self) -> Iterator[PageRoute]:
        return iter(self._routes)
