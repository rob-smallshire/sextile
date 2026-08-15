"""Naming one thing a service holds, and narrowing it back out.

What a service holds is typed as `object`, because the framework cannot know
what any service puts there. A `Held` key states the narrowing once: the name
and the type travel together, so a page reaches what the lifespan opened in one
call, and a mistyped key fails by name rather than at the far end of a telephone
line.

    PLACES = Held("places", Index)

    yield PLACES.holding(index) | VISITS.holding(log)     # in the lifespan
    index = PLACES.of(request.service)                    # in a page
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from sextile.application import PageRequest


class Held[T]:
    """One thing a service holds: its key, and the type it must be."""

    def __init__(self, name: str, kind: type[T]) -> None:
        self.name = name
        self.kind = kind

    @classmethod
    def checking(cls, name: str, kind: object) -> "Held[T]":
        """The same key, whose kind is a protocol or an abstract class.

        The type checker refuses those where a type is expected, on the
        ground that the function might instantiate one; a key never
        instantiates, only checks against, so this takes them without the
        complaint. Say what `T` is on the assignment:

            VISITS: Final[Held[Visits]] = Held.checking("visits", Visits)
        """
        return cls(name, cast("type[T]", kind))

    def of(self, service: Mapping[str, object]) -> T:
        """What the service holds under this key, or raise ``RuntimeError``.

        For the things a service cannot run without. Absence means the
        lifespan never yielded it, which is a fault in the assembly rather
        than in the page that noticed.
        """
        held = service.get(self.name)
        if not isinstance(held, self.kind):
            raise RuntimeError(
                f"the service is not holding {self.name!r}; has it started?"
            )
        return held

    def found_in(self, service: Mapping[str, object]) -> T | None:
        """What the service holds under this key, or None.

        For the things a service may run without, where the page says so
        instead of failing.
        """
        held = service.get(self.name)
        return held if isinstance(held, self.kind) else None

    def find(self, request: "PageRequest") -> T | None:
        """`found_in`, from a request: the shape a middleware finder takes."""
        return self.found_in(request.service)

    def holding(self, value: T) -> dict[str, object]:
        """The entry a lifespan yields, composable with ``|``."""
        return {self.name: value}
