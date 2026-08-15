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

Registered nowhere, like `history` and `contents`. A service maps it into its
numbering or does without:

    @page("94", name="names", title="Words you can key", keywords=("KEYWORDS",))
    async def _names(self, request: PageRequest) -> Page:
        return await self.names(request)
"""

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Final

from sextile.addressing import PageAddress, keyed
from sextile.formatting import Listing, MenuItem
from sextile.layout import Flowing, PageLayout
from sextile.page import Page

if TYPE_CHECKING:
    from sextile.requests import PageRequest

TITLE: Final = "WORDS YOU CAN KEY"

_NOTHING: Final = "This service has no words to key."


def names_page(
    *,
    request: "PageRequest",
    named: Mapping[str, PageAddress],
    describe: Callable[[PageAddress], str],
    title: str = TITLE,
) -> Page:
    """Build the page of named jumps, one row per word."""
    entries = [
        MenuItem(text=keyed(word), detail=describe(named[word])) for word in sorted(named)
    ]
    return PageLayout(
        title=title, parts=[Flowing(Listing(entries=entries, empty=_NOTHING))]
    ).build(request)
