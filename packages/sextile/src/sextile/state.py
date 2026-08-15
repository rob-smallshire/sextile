"""What a service holds while it is running, and the typed keys into it.

What a service opens for the life of the process -- an archive, an HTTP client,
an index -- is held on the application and reached from a page. The framework
cannot know what any service puts there, so the store is untyped; a `StateKey`
states the type once, on the key, and carries it to both ends:

    DB = StateKey[Connection]("db")

    app.state[DB] = connect(...)          # in the lifespan
    conn = request.state[DB]              # in a page, typed Connection

A key's identity is the key, not its name: two `StateKey`s with the same name
are different keys and do not collide. The name is for `repr` and the message
when a key is read that was never written.
"""

from typing import Any, Generic, Protocol, TypeVar, cast

__all__ = [
    "State",
    "StateKey",
    "StateReader",
]

#: Old-style, invariant `TypeVar` on purpose. A PEP 695 `class StateKey[T]`
#: gets its variance inferred, and with `T` used only as the key's own tag mypy
#: infers it loosely enough that `state[key_of_int] = "a string"` type-checks --
#: which is the one thing this class exists to stop. The invariant `Generic[T]`
#: pins `T` from the key so the value is checked against it, as `pytest.Stash`
#: does for the same reason.
_T = TypeVar("_T")


class StateKey(Generic[_T]):  # noqa: UP046 -- invariance, see _T above
    """A typed key into a service's state.

    Attributes:
        name: What the key is called, used in `repr` and in the error a missing
            key raises. It is not how the value is stored: the key's own
            identity is, so two keys of the same name are distinct.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"StateKey({self.name!r})"


class StateReader(Protocol):
    """The read-only view of a service's state that a page is given.

    A page reads what the service holds and never writes it: shared state
    changed from a page would reach every other caller at once. This is that
    guarantee said in the types -- there is no `__setitem__` here.
    """

    def __getitem__(self, key: StateKey[_T]) -> _T: ...

    def get(self, key: StateKey[_T], default: _T | None = None) -> _T | None: ...

    def __contains__(self, key: StateKey[Any]) -> bool: ...


class State:
    """What a service holds while it is running, keyed by `StateKey`.

    Writable, and held on the application; a page is given the read-only
    `StateReader` view of it instead.
    """

    def __init__(self) -> None:
        self._held: dict[StateKey[Any], object] = {}

    def __setitem__(self, key: StateKey[_T], value: _T) -> None:
        self._held[key] = value

    def __getitem__(self, key: StateKey[_T]) -> _T:
        try:
            held = self._held[key]
        except KeyError:
            raise KeyError(
                f"the service is not holding {key.name!r}; has it started?"
            ) from None
        return cast("_T", held)

    def get(self, key: StateKey[_T], default: _T | None = None) -> _T | None:
        return cast("_T | None", self._held.get(key, default))

    def __contains__(self, key: StateKey[Any]) -> bool:
        return key in self._held

    def clear(self) -> None:
        """Forget everything held, as the service stops."""
        self._held.clear()
