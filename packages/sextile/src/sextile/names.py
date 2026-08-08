"""The words a reader can key in place of a page number.

    *ABOUT#     About this service
    *BYE#       Ring off
    *MAIN#      Main index

Prestel was almost entirely numeric, but other viewdata services took keywords
and a service that offers them has to say so somewhere. Generated from the
aliases, so it cannot drift from what the service actually answers -- which is
precisely what a list of keywords typed into a help page does, and did here.

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
from typing import Final

from sextile.addressing import PageAddress
from sextile.page import Page
from sextile.templates import Listing, MenuItem

TITLE: Final = "WORDS YOU CAN KEY"

_NOTHING: Final = "This service has no words to key."


def names_page(
    *,
    address: PageAddress,
    named: Mapping[str, PageAddress],
    describe: Callable[[PageAddress], str],
    home: PageAddress,
    title: str = TITLE,
) -> Page:
    """Build the page of named jumps, one row per word."""
    entries = [
        MenuItem(text=f"*{word}#", detail=describe(named[word])) for word in sorted(named)
    ]
    return Listing(
        title=title, entries=entries, home=home, empty=_NOTHING
    ).build(address)
