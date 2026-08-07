"""Reading robots.txt correctly.

Written because Python's own `urllib.robotparser` gets Stardot's file wrong: it
returns the first matching rule, so the `Allow: /` near the top masks every
`Disallow` below it and it cheerfully permits `viewtopic.php?p=`, which the site
plainly forbids. RFC 9309 says the *longest* matching rule wins, with a tie
going to Allow.

Getting this backwards would mean fetching pages we have been asked not to, so
it is tested against the board's real file rather than a paraphrase.
"""

from pathlib import Path

import pytest

from stardot_viewdata.feed.robots import RobotsRules

FIXTURES = Path(__file__).parent / "data"
STARDOT_ROBOTS = (FIXTURES / "stardot-robots.txt").read_text()

AGENT = "Sextile/0.1 (+viewdata gateway for Stardot)"


@pytest.fixture
def stardot() -> RobotsRules:
    return RobotsRules.parse(STARDOT_ROBOTS)


class TestStardotsActualRules:
    """The file as the board actually publishes it."""

    @pytest.mark.parametrize(
        "path",
        [
            "/forums/app.php/feed",
            "/forums/app.php/feed/topics",
            "/forums/app.php/feed/topic/28000",
            "/forums/app.php/feed/forum/53",
            "/forums/viewtopic.php?t=33387",
            "/forums/index.php",
        ],
    )
    def test_the_feeds_we_need_are_permitted(self, stardot: RobotsRules, path: str) -> None:
        assert stardot.permits(AGENT, path)

    @pytest.mark.parametrize(
        "path",
        [
            "/forums/viewtopic.php?p=489493",
            "/forums/search.php",
            "/forums/memberlist.php",
            "/forums/posting.php",
            "/forums/ucp.php",
            "/forums/download/file.php?id=96852",
        ],
    )
    def test_the_forbidden_paths_are_refused(self, stardot: RobotsRules, path: str) -> None:
        assert not stardot.permits(AGENT, path)

    def test_the_post_page_that_would_reveal_a_topic_id_is_forbidden(
        self, stardot: RobotsRules
    ) -> None:
        #  The single most consequential rule for this project: it is why thread
        #  browsing cannot simply scrape a post page for its topic id.
        assert not stardot.permits(AGENT, "/forums/viewtopic.php?p=489493")

    def test_the_crawl_delay_is_a_minute(self, stardot: RobotsRules) -> None:
        assert stardot.crawl_delay(AGENT) == 60.0

    def test_an_allow_early_in_the_file_does_not_mask_a_later_disallow(
        self, stardot: RobotsRules
    ) -> None:
        #  Exactly the bug in urllib.robotparser that this module exists to avoid.
        assert stardot.permits(AGENT, "/forums/index.php")
        assert not stardot.permits(AGENT, "/forums/search.php")


class TestLongestMatchWins:
    def test_a_longer_disallow_beats_a_shorter_allow(self) -> None:
        rules = RobotsRules.parse("User-agent: *\nAllow: /\nDisallow: /private/")
        assert rules.permits(AGENT, "/public")
        assert not rules.permits(AGENT, "/private/thing")

    def test_a_longer_allow_beats_a_shorter_disallow(self) -> None:
        rules = RobotsRules.parse("User-agent: *\nDisallow: /files/\nAllow: /files/public/")
        assert not rules.permits(AGENT, "/files/secret")
        assert rules.permits(AGENT, "/files/public/thing")

    def test_a_tie_is_resolved_in_favour_of_allowing(self) -> None:
        rules = RobotsRules.parse("User-agent: *\nDisallow: /thing\nAllow: /thing")
        assert rules.permits(AGENT, "/thing")

    def test_an_empty_disallow_forbids_nothing(self) -> None:
        rules = RobotsRules.parse("User-agent: *\nDisallow:")
        assert rules.permits(AGENT, "/anything")


class TestWildcards:
    def test_a_star_matches_any_run_of_characters(self) -> None:
        rules = RobotsRules.parse("User-agent: *\nDisallow: /*.pdf")
        assert not rules.permits(AGENT, "/docs/manual.pdf")
        assert rules.permits(AGENT, "/docs/manual.html")

    def test_a_dollar_anchors_the_end(self) -> None:
        rules = RobotsRules.parse("User-agent: *\nDisallow: /*.php$")
        assert not rules.permits(AGENT, "/index.php")
        assert rules.permits(AGENT, "/index.php?x=1")

    def test_a_query_string_is_part_of_the_path_for_matching(self) -> None:
        rules = RobotsRules.parse("User-agent: *\nDisallow: /view.php?p=")
        assert not rules.permits(AGENT, "/view.php?p=1")
        assert rules.permits(AGENT, "/view.php?t=1")


class TestAgentSelection:
    def test_a_named_group_is_preferred_to_the_wildcard(self) -> None:
        rules = RobotsRules.parse(
            "User-agent: *\nDisallow:\n\nUser-agent: Sextile\nDisallow: /forums/"
        )
        assert not rules.permits("Sextile/0.1", "/forums/index.php")

    def test_an_unnamed_agent_falls_back_to_the_wildcard(self) -> None:
        rules = RobotsRules.parse(
            "User-agent: *\nDisallow: /secret\n\nUser-agent: OtherBot\nDisallow: /"
        )
        assert rules.permits(AGENT, "/public")
        assert not rules.permits(AGENT, "/secret")

    def test_repeated_wildcard_groups_are_merged(self) -> None:
        #  Stardot's file has two `User-agent: *` groups, and the rules in the
        #  second are just as binding as those in the first.
        rules = RobotsRules.parse(
            "User-agent: *\nAllow: /\n\nUser-agent: *\nDisallow: /forums/search.php"
        )
        assert not rules.permits(AGENT, "/forums/search.php")

    def test_agent_matching_ignores_case(self) -> None:
        rules = RobotsRules.parse("User-agent: SEXTILE\nDisallow: /")
        assert not rules.permits("sextile/0.1", "/anything")

    def test_a_group_naming_another_bot_does_not_apply_to_us(self) -> None:
        #  Stardot forbids ClaudeBot outright; that rule is not ours to obey in
        #  place of the wildcard group's.
        rules = RobotsRules.parse("User-agent: *\nAllow: /\n\nUser-agent: ClaudeBot\nDisallow: /")
        assert rules.permits(AGENT, "/forums/app.php/feed")


class TestDegenerateFiles:
    def test_an_empty_file_permits_everything(self) -> None:
        assert RobotsRules.parse("").permits(AGENT, "/anything")

    def test_comments_and_blank_lines_are_ignored(self) -> None:
        rules = RobotsRules.parse("# a comment\n\nUser-agent: *\nDisallow: /x  # trailing\n")
        assert not rules.permits(AGENT, "/x")

    def test_rules_before_any_user_agent_line_are_ignored(self) -> None:
        assert RobotsRules.parse("Disallow: /\nUser-agent: *\nAllow: /").permits(AGENT, "/x")

    def test_an_unparseable_crawl_delay_is_absent(self) -> None:
        rules = RobotsRules.parse("User-agent: *\nCrawl-delay: soon")
        assert rules.crawl_delay(AGENT) is None

    def test_no_crawl_delay_is_absent_rather_than_zero(self) -> None:
        assert RobotsRules.parse("User-agent: *\nDisallow:").crawl_delay(AGENT) is None
