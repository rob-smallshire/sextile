"""The typed store a service holds, keyed by `StateKey`."""

from typing import assert_type

import pytest

from sextile.state import State, StateKey

DB = StateKey[str]("db")
COUNT = StateKey[int]("count")


class TestState:
    def test_what_is_written_is_read_back(self) -> None:
        state = State()
        state[DB] = "a connection"
        assert state[DB] == "a connection"

    def test_the_value_read_back_carries_the_key_s_type(self) -> None:
        state = State()
        state[DB] = "a connection"
        assert_type(state[DB], str)
        assert_type(state.get(DB), str | None)

    def test_get_returns_the_default_where_nothing_is_held(self) -> None:
        assert State().get(DB) is None
        assert State().get(COUNT, 0) == 0

    def test_a_key_never_written_is_a_key_error_that_names_it(self) -> None:
        with pytest.raises(KeyError, match="db"):
            _ = State()[DB]

    def test_contains_says_whether_a_key_is_held(self) -> None:
        state = State()
        assert DB not in state
        state[DB] = "x"
        assert DB in state

    def test_two_keys_of_the_same_name_are_distinct(self) -> None:
        one = StateKey[str]("db")
        another = StateKey[str]("db")
        state = State()
        state[one] = "first"
        state[another] = "second"
        assert state[one] == "first"
        assert state[another] == "second"

    def test_clearing_forgets_everything(self) -> None:
        state = State()
        state[DB] = "x"
        state.clear()
        assert DB not in state

    def test_a_wrongly_typed_write_is_refused(self) -> None:
        #  A negative test the type checker runs: `strict` makes an unused
        #  `type: ignore` an error, so this fails if State ever stops checking
        #  the value against the key's type.
        state = State()
        state[COUNT] = "not an int"  # type: ignore[misc]
        assert COUNT in state
