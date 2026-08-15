"""One thing a service holds, named once and narrowed once.

Every service was writing the same function per thing it held -- take the
mapping, get the name, check the type, raise with some words -- and each copy
raised its own version of the same complaint. `Held` is that function written
once, so these tests are the contract the copies were each keeping alone.
"""

from typing import Final, Protocol, runtime_checkable

import pytest

from sextile import Held, PageRequest, Sextile
from sextile.addressing import PageAddress


class Archive:
    """Stands in for whatever a service opens."""


ARCHIVE = Held("archive", Archive)


@runtime_checkable
class Log(Protocol):
    """Stands in for a protocol-shaped holding, such as a visits log."""

    def record(self) -> None: ...


class Kept:
    def record(self) -> None: ...


LOG: Final[Held[Log]] = Held.checking("log", Log)


class TestChecking:
    """A key whose kind is a protocol or an abstract class.

    The same key, made another way: mypy refuses a protocol where a type is
    expected, on the ground that it might be instantiated, and a key never
    instantiates.
    """

    def test_narrows_against_the_protocol(self) -> None:
        kept = Kept()

        assert LOG.of({"log": kept}) is kept

    def test_refuses_what_does_not_fit_the_protocol(self) -> None:
        with pytest.raises(RuntimeError, match="log"):
            LOG.of({"log": object()})


class TestOf:
    def test_answers_what_is_held_under_the_name(self) -> None:
        opened = Archive()

        assert ARCHIVE.of({"archive": opened}) is opened

    def test_refuses_a_service_holding_nothing_by_naming_the_key(self) -> None:
        with pytest.raises(RuntimeError, match="archive"):
            ARCHIVE.of({})

    def test_refuses_a_value_of_the_wrong_type(self) -> None:
        #  A mistyped assignment in a lifespan should fail at the key, with
        #  the key's name in the complaint, rather than at the far end of a
        #  telephone line.
        with pytest.raises(RuntimeError, match="archive"):
            ARCHIVE.of({"archive": "not an archive"})


class TestFoundIn:
    def test_answers_what_is_held(self) -> None:
        opened = Archive()

        assert ARCHIVE.found_in({"archive": opened}) is opened

    def test_answers_none_for_a_service_holding_nothing(self) -> None:
        assert ARCHIVE.found_in({}) is None

    def test_answers_none_for_a_value_of_the_wrong_type(self) -> None:
        assert ARCHIVE.found_in({"archive": object()}) is None


class TestFind:
    def test_reads_what_a_request_carries(self) -> None:
        opened = Archive()
        request = PageRequest(
            address=PageAddress("1"), app=Sextile(), service={"archive": opened}
        )

        assert ARCHIVE.find(request) is opened

    def test_answers_none_when_the_request_carries_nothing(self) -> None:
        request = PageRequest(address=PageAddress("1"), app=Sextile())

        assert ARCHIVE.find(request) is None


class TestHolding:
    def test_is_the_entry_a_lifespan_yields(self) -> None:
        opened = Archive()

        assert ARCHIVE.holding(opened) == {"archive": opened}

    def test_composes_with_another_key_by_union(self) -> None:
        other = Held("clock", Archive)
        first, second = Archive(), Archive()

        held = ARCHIVE.holding(first) | other.holding(second)

        assert held == {"archive": first, "clock": second}
