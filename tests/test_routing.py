"""Dispatching a page number to whatever answers it.

A pattern is literal digits and named fields: `82{post_id:int}` answers every
page number beginning 82, and hands the rest to its target as `post_id`. That is
the same bargain a web framework's routing table makes, and it is made here for
the same reason -- so that the scheme lives in one place and nothing downstream
has to spell it out again.

Because a request is terminated by `#`, numbers need not be prefix-free: `*8#`
and `*82489493#` are unambiguously different, and fields may vary in width.
"""

from datetime import date

import pytest

from sextile.addressing import PageAddress, UnknownPageError
from sextile.routing import Converter, NoSuchRouteError, RouteError, Router


def address(digits: str) -> PageAddress:
    return PageAddress(digits)


class TestLiteralPatterns:
    def test_a_literal_pattern_matches_its_own_number(self) -> None:
        router: Router[str] = Router()
        router.add("1", "main")
        found = router.match(address("1"))
        assert found is not None
        assert found.target == "main"

    def test_a_literal_pattern_matches_nothing_else(self) -> None:
        router: Router[str] = Router()
        router.add("1", "main")
        assert router.match(address("11")) is None

    def test_an_unrouted_number_matches_nothing(self) -> None:
        #  Not an error: an application decides what to say about a page it does
        #  not have.
        router: Router[str] = Router()
        assert router.match(address("6")) is None


class TestFields:
    def test_a_field_captures_the_rest(self) -> None:
        router: Router[str] = Router()
        router.add("82{post_id:int}", "post")
        found = router.match(address("82489493"))
        assert found is not None
        assert found.target == "post"
        assert found.params == {"post_id": 489493}

    def test_a_field_defaults_to_a_whole_number(self) -> None:
        #  Every field in a page number is numeric, so `int` is what `{name}`
        #  means when nothing else is said.
        router: Router[str] = Router()
        router.add("42{forum_id}", "forum")
        found = router.match(address("4253"))
        assert found is not None
        assert found.params == {"forum_id": 53}

    def test_a_field_needs_at_least_one_digit(self) -> None:
        router: Router[str] = Router()
        router.add("82{post_id:int}", "post")
        assert router.match(address("82")) is None

    def test_a_leading_zero_is_not_a_number(self) -> None:
        #  Accepting one would give a single page two different numbers.
        router: Router[str] = Router()
        router.add("82{post_id:int}", "post")
        assert router.match(address("8201")) is None

    def test_zero_itself_is_a_number(self) -> None:
        router: Router[str] = Router()
        router.add("82{post_id:int}", "post")
        found = router.match(address("820"))
        assert found is not None
        assert found.params == {"post_id": 0}

    def test_a_date_field_is_eight_digits(self) -> None:
        router: Router[str] = Router()
        router.add("32{day:date}", "day")
        found = router.match(address("3220260802"))
        assert found is not None
        assert found.params == {"day": date(2026, 8, 2)}

    def test_a_date_field_refuses_a_date_that_is_not_one(self) -> None:
        router: Router[str] = Router()
        router.add("32{day:date}", "day")
        assert router.match(address("3220260231")) is None

    def test_a_date_field_refuses_the_wrong_number_of_digits(self) -> None:
        router: Router[str] = Router()
        router.add("32{day:date}", "day")
        assert router.match(address("32202608")) is None

    def test_several_fields_are_captured_by_name(self) -> None:
        router: Router[str] = Router()
        router.add("6{day:date}{post_id:int}", "post-on-day")
        found = router.match(address("620260802489493"))
        assert found is not None
        assert found.params == {"day": date(2026, 8, 2), "post_id": 489493}


class TestChoosingBetweenRoutes:
    #  Patterns are tried by how much of them is literal, most first, so a
    #  specific number beats a general one whatever order they were added in.

    def test_the_more_literal_pattern_wins(self) -> None:
        router: Router[str] = Router()
        router.add("9{n:int}", "general")
        router.add("90", "logoff")
        found = router.match(address("90"))
        assert found is not None
        assert found.target == "logoff"

    def test_registration_order_does_not_decide_it(self) -> None:
        router: Router[str] = Router()
        router.add("90", "logoff")
        router.add("9{n:int}", "general")
        found = router.match(address("90"))
        assert found is not None
        assert found.target == "logoff"

    def test_the_general_pattern_still_serves_the_rest(self) -> None:
        router: Router[str] = Router()
        router.add("9{n:int}", "general")
        router.add("90", "logoff")
        found = router.match(address("91"))
        assert found is not None
        assert found.target == "general"


class TestRefusingAmbiguity:
    def test_two_variable_fields_running_together_are_refused(self) -> None:
        #  There would be no telling where one ended and the next began.
        router: Router[str] = Router()
        with pytest.raises(RouteError):
            router.add("8{a:int}{b:int}", "ambiguous")

    def test_a_variable_field_may_follow_a_fixed_one(self) -> None:
        router: Router[str] = Router()
        router.add("6{day:date}{post_id:int}", "post-on-day")

    def test_the_same_pattern_twice_is_refused(self) -> None:
        router: Router[str] = Router()
        router.add("1", "main")
        with pytest.raises(RouteError):
            router.add("1", "other")

    def test_the_same_name_twice_is_refused(self) -> None:
        router: Router[str] = Router()
        router.add("1", "main", name="index")
        with pytest.raises(RouteError):
            router.add("2", "other", name="index")

    def test_the_same_field_name_twice_is_refused(self) -> None:
        router: Router[str] = Router()
        with pytest.raises(RouteError):
            router.add("8{id:date}{id:int}", "confused")


class TestRefusingNonsense:
    @pytest.mark.parametrize(
        "pattern",
        [
            "",  # names no page
            "4a",  # a page number is digits
            "42{forum_id",  # unclosed
            "42{}",  # unnamed
            "42{2forums:int}",  # not an identifier
            "42{forum_id:furlong}",  # no such converter
        ],
    )
    def test_a_pattern_that_is_not_one_is_refused(self, pattern: str) -> None:
        router: Router[str] = Router()
        with pytest.raises(RouteError):
            router.add(pattern, "target")


class TestNamedJumps:
    #  Prestel itself was almost entirely numeric, but other viewdata services
    #  accepted keywords and there is no reason to be bound by Prestel's
    #  database conventions. `*MAIN#` is easier to remember than `*1#`.

    def test_a_keyword_resolves_to_an_address(self) -> None:
        router: Router[str] = Router()
        router.alias("MAIN", "1")
        assert router.resolve("MAIN") == address("1")

    def test_a_keyword_is_matched_whatever_its_case(self) -> None:
        router: Router[str] = Router()
        router.alias("main", "1")
        assert router.resolve("Main") == address("1")

    def test_digits_resolve_to_themselves(self) -> None:
        router: Router[str] = Router()
        assert router.resolve("82489493") == address("82489493")

    def test_a_word_that_is_not_a_keyword_names_no_page(self) -> None:
        router: Router[str] = Router()
        with pytest.raises(UnknownPageError):
            router.resolve("BANANA")

    def test_a_keyword_need_not_be_routed_to_be_resolved(self) -> None:
        #  Resolving says what a reader meant; whether anything answers it is
        #  the next question, and has one answer for keywords and numbers alike.
        router: Router[str] = Router()
        router.alias("MAIN", "1")
        assert router.match(router.resolve("MAIN")) is None

    def test_a_keyword_of_digits_is_refused(self) -> None:
        #  It could never be reached: digits resolve to themselves.
        router: Router[str] = Router()
        with pytest.raises(RouteError):
            router.alias("42", "1")

    def test_a_keyword_a_reader_could_not_key_is_refused(self) -> None:
        #  The command parser accumulates letters and digits and nothing else,
        #  so a keyword with punctuation in it could never be reached.
        router: Router[str] = Router()
        with pytest.raises(RouteError):
            router.alias("MAIN MENU", "1")

    def test_the_same_keyword_twice_is_refused(self) -> None:
        router: Router[str] = Router()
        router.alias("MAIN", "1")
        with pytest.raises(RouteError):
            router.alias("MAIN", "2")

    def test_several_keywords_may_name_one_page(self) -> None:
        router: Router[str] = Router()
        router.alias("MAIN", "1")
        router.alias("HOME", "1")
        assert router.resolve("HOME") == router.resolve("MAIN")

    def test_the_keywords_can_be_listed(self) -> None:
        #  A service that offers named jumps has to be able to say so on a page.
        router: Router[str] = Router()
        router.alias("MAIN", "1")
        assert router.keywords() == {"MAIN": address("1")}


class TestBuildingAnAddress:
    #  The other direction: a page naming where a key leads without respelling
    #  the numbering scheme. This is what keeps the scheme in one place.

    def test_a_named_route_builds_its_address(self) -> None:
        router: Router[str] = Router()
        router.add("82{post_id:int}", "post", name="post")
        assert router.address_for("post", post_id=489493) == address("82489493")

    def test_a_literal_route_builds_its_address(self) -> None:
        router: Router[str] = Router()
        router.add("1", "main", name="main")
        assert router.address_for("main") == address("1")

    def test_a_date_is_formatted_as_the_pattern_reads_it(self) -> None:
        router: Router[str] = Router()
        router.add("32{day:date}", "day", name="day")
        assert router.address_for("day", day=date(2026, 8, 2)) == address("3220260802")

    def test_an_address_built_matches_the_route_it_was_built_from(self) -> None:
        router: Router[str] = Router()
        router.add("32{day:date}", "day", name="day")
        built = router.address_for("day", day=date(2026, 8, 2))
        found = router.match(built)
        assert found is not None
        assert found.params == {"day": date(2026, 8, 2)}

    def test_an_unnamed_route_cannot_be_built(self) -> None:
        router: Router[str] = Router()
        router.add("1", "main")
        with pytest.raises(NoSuchRouteError):
            router.address_for("main")

    def test_a_missing_field_is_refused(self) -> None:
        router: Router[str] = Router()
        router.add("82{post_id:int}", "post", name="post")
        with pytest.raises(NoSuchRouteError):
            router.address_for("post")

    def test_a_field_that_is_not_in_the_pattern_is_refused(self) -> None:
        router: Router[str] = Router()
        router.add("82{post_id:int}", "post", name="post")
        with pytest.raises(NoSuchRouteError):
            router.address_for("post", post_id=1, forum_id=2)

    def test_a_value_of_the_wrong_kind_is_refused(self) -> None:
        router: Router[str] = Router()
        router.add("32{day:date}", "day", name="day")
        with pytest.raises(NoSuchRouteError):
            router.address_for("day", day=489493)

    def test_a_value_the_pattern_could_not_match_is_refused(self) -> None:
        #  A negative id would build something that is not a page number at all,
        #  and the failure belongs where it was caused.
        router: Router[str] = Router()
        router.add("82{post_id:int}", "post", name="post")
        with pytest.raises(NoSuchRouteError):
            router.address_for("post", post_id=-1)


class TestApplicationConverters:
    #  The extension point: an application whose numbering needs a field shape
    #  the framework does not offer registers its own.

    def test_a_converter_can_be_registered(self) -> None:
        router: Router[str] = Router()
        router.converter("pair", Converter(field_pattern="[0-9]{2}", width=2))
        router.add("7{code:pair}", "coded", name="coded")
        found = router.match(address("742"))
        assert found is not None
        assert found.params == {"code": "42"}
        assert router.address_for("coded", code="42") == address("742")

    def test_a_registered_converter_may_be_fixed_width(self) -> None:
        #  Which is what lets a variable field follow it.
        router: Router[str] = Router()
        router.converter("pair", Converter(field_pattern="[0-9]{2}", width=2))
        router.add("7{code:pair}{rest:int}", "coded")

    def test_the_same_converter_name_twice_is_refused(self) -> None:
        router: Router[str] = Router()
        router.converter("pair", Converter(field_pattern="[0-9]{2}", width=2))
        with pytest.raises(RouteError):
            router.converter("pair", Converter(field_pattern="[0-9]{3}", width=3))
