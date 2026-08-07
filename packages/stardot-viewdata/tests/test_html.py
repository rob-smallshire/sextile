"""Turning a phpBB post body into semantic blocks.

Tested against the markup the board actually emits. A survey of thirty captured
posts found only fourteen distinct tags, all machine-generated, which is why
this is built on the standard library's HTML parser rather than a dependency.

The output is deliberately structural rather than typographic. On a forty-column
screen, colour earns its keep distinguishing a quotation from a code listing
from the author's own words; it earns nothing rendering an italic.
"""

import re
from pathlib import Path

import pytest

from sextile.content.blocks import (
    Attachment,
    Block,
    Code,
    Document,
    Image,
    ListItem,
    Paragraph,
    Quote,
)
from stardot_viewdata.feed.atom import parse_feed
from stardot_viewdata.html import parse_post_body

FIXTURES = Path(__file__).parent / "data"
BOARD_POSTS = parse_feed((FIXTURES / "board-feed.xml").read_text()).posts
TOPIC_POSTS = parse_feed((FIXTURES / "topic-28000-feed.xml").read_text()).posts
ALL_POSTS = BOARD_POSTS + TOPIC_POSTS


class TestParagraphs:
    def test_plain_text_is_one_paragraph(self) -> None:
        content = parse_post_body("Hello there.")
        assert content.blocks == (Paragraph(("Hello there.",)),)

    def test_a_single_break_starts_a_new_line_in_the_same_paragraph(self) -> None:
        #  A line break is not a paragraph break: on twenty-four rows, spending
        #  a blank row on every <br> would be ruinous.
        content = parse_post_body("first<br>second")
        assert content.blocks == (Paragraph(("first", "second")),)

    def test_a_double_break_starts_a_new_paragraph(self) -> None:
        content = parse_post_body("first<br><br>second")
        assert content.blocks == (Paragraph(("first",)), Paragraph(("second",)))

    def test_a_paragraph_element_starts_a_new_paragraph(self) -> None:
        content = parse_post_body("<p>first</p><p>second</p>")
        assert content.blocks == (Paragraph(("first",)), Paragraph(("second",)))

    def test_whitespace_is_tidied(self) -> None:
        content = parse_post_body("  lots   of\n   space  ")
        assert content.blocks == (Paragraph(("lots of space",)),)

    def test_html_entities_are_decoded(self) -> None:
        content = parse_post_body("A &amp; B &lt;C&gt; &quot;D&quot; &#163;5")
        assert content.blocks == (Paragraph(('A & B <C> "D" £5',)),)

    def test_an_empty_body_yields_nothing(self) -> None:
        assert parse_post_body("").blocks == ()

    def test_a_body_of_only_whitespace_yields_nothing(self) -> None:
        assert parse_post_body("  <br> <br>  ").blocks == ()


class TestTheStatisticsFooter:
    """phpBB appends a footer to every post body. It must not reach the screen."""

    def test_the_footer_is_removed(self) -> None:
        body = (
            "The actual post.<p>Statistics: Posted by "
            '<a href="https://stardot.org.uk/forums/memberlist.php?mode=viewprofile&amp;u=1">'
            "someone</a> — Sun Aug 02, 2026 9:20 pm</p><hr />"
        )
        assert parse_post_body(body).blocks == (Paragraph(("The actual post.",)),)

    def test_no_captured_post_shows_its_footer(self) -> None:
        for post in ALL_POSTS:
            rendered = _text_of(parse_post_body(post.content_html))
            assert "Statistics: Posted by" not in rendered

    def test_the_author_link_in_the_footer_is_not_offered_as_a_reference(self) -> None:
        #  It is plumbing, not something a reader asked to follow.
        for post in ALL_POSTS:
            content = parse_post_body(post.content_html)
            assert not any("memberlist.php" in link.url for link in content.links)


class TestQuotations:
    def test_a_quotation_becomes_a_quote_block(self) -> None:
        body = '<blockquote class="uncited"><div>Quoted words</div></blockquote>Reply'
        content = parse_post_body(body)
        assert content.blocks == (
            Quote((Paragraph(("Quoted words",)),)),
            Paragraph(("Reply",)),
        )

    def test_quotations_nest(self) -> None:
        body = (
            '<blockquote class="uncited"><div>Outer'
            '<blockquote class="uncited"><div>Inner</div></blockquote>'
            "</div></blockquote>"
        )
        content = parse_post_body(body)
        assert content.blocks == (
            Quote((Paragraph(("Outer",)), Quote((Paragraph(("Inner",)),)))),
        )

    def test_a_real_nested_quotation_survives(self) -> None:
        #  The topic feed has genuinely nested quoting.
        quoting = [
            post for post in TOPIC_POSTS if "<blockquote" in post.content_html
        ]
        assert quoting
        for post in quoting:
            assert any(
                isinstance(block, Quote) for block in parse_post_body(post.content_html).blocks
            )


class TestCode:
    def test_a_codebox_becomes_a_code_block(self) -> None:
        body = '<div class="codebox"><p>Code: </p><pre><code>LDA #&amp;19</code></pre></div>'
        assert parse_post_body(body).blocks == (Code(("LDA #&19",)),)

    def test_code_keeps_its_own_spacing(self) -> None:
        #  Collapsing whitespace inside a listing would destroy its alignment.
        body = "<pre><code>  lda     &amp;b5fe\n  cmp     #MAGIC0</code></pre>"
        assert parse_post_body(body).blocks == (
            Code(("  lda     &b5fe", "  cmp     #MAGIC0")),
        )

    def test_the_feed_preserves_the_line_breaks_in_a_listing(self) -> None:
        """It did not always.

        phpBB's feed used to strip every character below 0x20 from a post body,
        so listings arrived as a single run-on line. Reported to the Stardot
        administrators, who narrowed the sanitiser to the characters XML
        actually forbids. This is the test that used to pin the defect, now
        pinning the fix.
        """
        listings = [
            block
            for post in TOPIC_POSTS
            for block in parse_post_body(post.content_html).blocks
            if isinstance(block, Code)
        ]
        assert listings, "the topic feed is expected to contain code"
        assert any(len(block.lines) > 1 for block in listings)

    def test_a_real_listing_keeps_its_own_lines(self) -> None:
        listing = next(
            block
            for post in TOPIC_POSTS
            for block in parse_post_body(post.content_html).blocks
            if isinstance(block, Code) and len(block.lines) > 2
        )
        assert listing.lines[0].startswith(";; Step 2")
        assert any("lda" in line for line in listing.lines)

    def test_the_code_label_is_not_treated_as_text(self) -> None:
        body = '<div class="codebox"><p>Code: </p><pre><code>NOP</code></pre></div>'
        assert not any(
            isinstance(block, Paragraph) for block in parse_post_body(body).blocks
        )


class TestLinks:
    def test_link_text_stays_in_place_and_the_target_is_collected(self) -> None:
        body = 'See <a class="postlink" href="https://example.com/x">this page</a> now.'
        content = parse_post_body(body)
        assert content.blocks == (Paragraph(("See this page [1] now.",)),)
        assert content.links[0].url == "https://example.com/x"
        assert content.links[0].number == 1

    def test_links_are_numbered_in_the_order_they_appear(self) -> None:
        body = '<a href="https://a.example">A</a> and <a href="https://b.example">B</a>'
        content = parse_post_body(body)
        assert [link.number for link in content.links] == [1, 2]
        assert [link.url for link in content.links] == ["https://a.example", "https://b.example"]

    def test_the_same_target_twice_is_one_reference(self) -> None:
        body = '<a href="https://a.example">A</a> and <a href="https://a.example">again</a>'
        content = parse_post_body(body)
        assert len(content.links) == 1
        assert content.blocks == (Paragraph(("A [1] and again [1]",)),)


class TestImagesAndAttachments:
    def test_a_smiley_becomes_the_text_the_poster_typed(self) -> None:
        #  phpBB keeps the original emoticon in the alt attribute, which is
        #  both shorter and more honest than describing the picture.
        body = '<img class="smilies" src="x.gif" alt="=D&gt;" title="Applause">'
        assert parse_post_body(body).blocks == (Paragraph(("=D>",)),)

    def test_an_image_becomes_a_named_placeholder(self) -> None:
        body = '<img class="postimage" src="x.png" alt="cap1.png" title="cap1.png (35 KiB)">'
        assert parse_post_body(body).blocks == (Image("cap1.png"),)

    def test_an_image_with_no_description_still_announces_itself(self) -> None:
        assert parse_post_body('<img class="postimage" src="x.png">').blocks == (Image(""),)

    def test_an_attachment_is_named(self) -> None:
        body = (
            '<div class="inline-attachment"><dl class="file"><dt>'
            '<span class="imageset icon_topic_attach"></span> '
            '<a class="postlink" href="https://stardot.org.uk/forums/download/file.php?id=96852">'
            "BtLoader 1.ssd</a></dt></dl></div>"
        )
        blocks = parse_post_body(body).blocks
        assert Attachment("BtLoader 1.ssd") in blocks


class TestLists:
    def test_list_items_become_their_own_blocks(self) -> None:
        body = "<ul><li>first</li><li>second</li></ul>"
        assert parse_post_body(body).blocks == (ListItem("first"), ListItem("second"))


class TestEveryCapturedPost:
    """Whatever the board threw at us, it must come out usable."""

    @pytest.mark.parametrize("index", range(len(ALL_POSTS)))
    def test_a_post_produces_at_least_one_block(self, index: int) -> None:
        assert parse_post_body(ALL_POSTS[index].content_html).blocks

    @pytest.mark.parametrize("index", range(len(ALL_POSTS)))
    def test_no_markup_survives_into_the_text(self, index: int) -> None:
        #  A bare '<' is not evidence of markup: emoticons such as `[-o<` are
        #  exactly what the poster typed, and keeping them is the point.
        rendered = _text_of(parse_post_body(ALL_POSTS[index].content_html))
        assert not re.search(r"</?[a-zA-Z]+[\s/>]", rendered)
        assert "&amp;" not in rendered
        assert "&lt;" not in rendered

    @pytest.mark.parametrize("index", range(len(ALL_POSTS)))
    def test_no_block_is_empty_padding(self, index: int) -> None:
        for block in parse_post_body(ALL_POSTS[index].content_html).blocks:
            if isinstance(block, Paragraph):
                assert block.lines
                assert all(line.strip() for line in block.lines)


def _text_of(content: Document) -> str:
    parts: list[str] = []

    def walk(blocks: tuple[Block, ...]) -> None:
        for block in blocks:
            match block:
                case Paragraph(lines):
                    parts.extend(lines)
                case Code(lines):
                    parts.extend(lines)
                case Quote(blocks=inner):
                    walk(inner)
                case ListItem(text) | Attachment(text) | Image(text):
                    parts.append(text)

    walk(content.blocks)
    return "\n".join(parts)


class TestEntityReferences:
    """A post body goes through an HTML parser, so entities resolve there.

    Tested anyway, and across the awkward places -- inside a listing, inside an
    attribute, in the numeric and hexadecimal forms -- because the same defect
    reached the screen from the title, which does not.
    """

    @pytest.mark.parametrize(
        ("escaped", "expected"),
        [
            ("A &amp; B", "A & B"),
            ("&lt;tag&gt;", "<tag>"),
            ("&quot;quoted&quot;", '"quoted"'),
            ("Bob&apos;s", "Bob's"),
            ("&#163;5", "£5"),
            ("&#x26;80", "&80"),
            ("&#38;81", "&81"),
            ("6502&nbsp;CPU", "6502 CPU"),  # a no-break space is still a space
        ],
    )
    def test_entities_in_running_text(self, escaped: str, expected: str) -> None:
        assert parse_post_body(escaped).blocks == (Paragraph((expected,)),)

    def test_entities_inside_a_listing(self) -> None:
        #  6502 source is full of ampersands, so this is the common case.
        body = "<pre><code>lda &amp;b5fe\ncmp #&amp;19</code></pre>"
        assert parse_post_body(body).blocks == (Code(("lda &b5fe", "cmp #&19")),)

    def test_entities_in_an_attribute(self) -> None:
        #  A smiley's alt text is the emoticon the poster typed.
        body = '<img class="smilies" src="x.gif" alt="=D&gt;" title="Applause">'
        assert parse_post_body(body).blocks == (Paragraph(("=D>",)),)

    def test_entities_in_an_image_description(self) -> None:
        body = '<img class="postimage" src="x.png" alt="Tube &amp; Econet.png">'
        assert parse_post_body(body).blocks == (Image("Tube & Econet.png"),)

    @pytest.mark.parametrize("index", range(len(ALL_POSTS)))
    def test_no_entity_reference_survives_a_captured_post(self, index: int) -> None:
        rendered = _text_of(parse_post_body(ALL_POSTS[index].content_html))
        assert not _ENTITY.search(rendered), rendered


_ENTITY = re.compile(r"&(?:[a-zA-Z][a-zA-Z0-9]{1,10}|#[0-9]{1,6}|#[xX][0-9a-fA-F]{1,5});")
