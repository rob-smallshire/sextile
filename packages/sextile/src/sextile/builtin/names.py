"""The words a reader can key in place of a page number.

    *ABOUT#     About this service
    *BYE#       Log off
    *MAIN#      Main index

Prestel was almost entirely numeric, but other viewdata services took keywords,
and a service that offers them has to say so somewhere. Generated from the
aliases, so it cannot drift from what the service answers, unlike a keyword list
typed into a help page by hand.

Listed alphabetically rather than by the page they reach: somebody reading this
is looking a word up, not browsing. Several words for one page are all shown,
each on its own line, because the reader has one of them in mind and wants to
find it rather than to learn that it has synonyms.

Registered nowhere, like `history` and `contents`. A service gives it a number
with `standard_pages` or does without:

    Sextile(pages=list(standard_pages(keywords="94")))
"""

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Final

from sextile.formatting import Listing, MenuItem
from sextile.layout import PageLayout
from sextile.page import Page, PageAddress, keyed

if TYPE_CHECKING:
    from sextile.requests import PageRequest

TITLE: Final = "WORDS YOU CAN KEY"

_NOTHING: Final = "This service has no words to key."


def names_page(
    *,
    request: "PageRequest",
    named: Mapping[str, PageAddress],
    label: Callable[[PageAddress], str],
    title: str = TITLE,
) -> Page:
    """Build the page of named jumps, one row per word.

    Args:
        request: The request this page answers.
        named: The keyword-to-address jumps to list.
        label: What to call each address.
        title: What the header calls the page.

    Returns:
        The page, of as many frames as the words needed.
    """
    entries = [
        MenuItem(text=keyed(word), detail=label(named[word])) for word in sorted(named)
    ]
    return PageLayout(
        title=title, parts=[Listing(entries=entries, empty=_NOTHING)]
    ).build(request)
