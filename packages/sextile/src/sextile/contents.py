"""What a service is made of, from its own registrations.

A list of the pages a service advertises, each with the number a reader would
key. Where a page number carries a field, the field is shown as a placeholder
rather than enumerated:

    *5#            By contributor
    *52<user-id>#  One contributor

Nobody can list every contributor on a screen, but everybody with a contributor
number in their hand can be told where to put it. That is the whole idea, and it
is only possible because the framework knows the patterns rather than a list of
addresses somebody keeps up to date by hand.

A page appears here if it was given a title when it was registered. That is how
a title frame stays off the list without a flag of its own: giving a page a
title is a service saying it may be advertised.

Registered nowhere, like the history page. A service maps it into its numbering
or does without:

    @page("93", name="contents", title="Every page")
    async def _contents(self, request: PageRequest) -> Page:
        return await self.contents(request)
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Final

from sextile.addressing import PageAddress, keyed
from sextile.page import Page
from sextile.templates import Listing, MenuItem
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.wrapping import wrap_within

if TYPE_CHECKING:
    from sextile.application import PageInfo

TITLE: Final = "EVERY PAGE"

_NOTHING: Final = "This service advertises no pages."


def contents_page(
    *,
    address: PageAddress,
    pages: Sequence["PageInfo"],
    home: PageAddress,
    title: str = TITLE,
) -> Page:
    """Build the contents page, one row per page, as many frames as it takes.

    Ordered by the number rather than by the order a service happens to declare
    its pages in. Sorting the digits as text puts each namespace root next to
    its members -- 5 then 52<user_id> -- which is what a scheme whose first
    digit names a namespace already means.
    """
    numbered = [
        (keyed(page.keyed), page.title)
        for page in sorted(pages, key=lambda page: page.keyed)
    ]
    return Listing(
        title=title, entries=_entries(numbered), home=home, empty=_NOTHING
    ).build(address)


def _entries(numbered: Sequence[tuple[str, str]]) -> list[MenuItem]:
    """One row a page, or two where the title will not fit on one.

    A title is written for a menu, where it has the width of the frame, and a
    contents page gives it what is left after the widest page number. That is
    enough for a service whose pages are called `One day` and not for one whose
    pages are called `Forecast by lat/lon position` -- and a title cut to
    `Forecast by lat/lon ` reads as a fault rather than as a shortage of room.

    So a title too long for the column is carried on to a second row, under
    itself and with no number beside it: a page number and a title that has run
    on are told apart by which column they are in, which is the same thing the
    guide does with a meaning too long for its own column.
    """
    column = min(
        max((cell_count(number) for number, _ in numbered), default=0) + 1,
        Listing.widest(),
    )
    room = COLUMNS - column - Listing.ATTRIBUTES
    entries = []
    for number, title in numbered:
        #  Two rows at most. A third would be a title that wants rewriting,
        #  and a contents page is a directory rather than a description.
        for offset, line in enumerate(wrap_within(title, cells=room, rows=2)):
            entries.append(MenuItem(text=number if not offset else "", detail=line))
    return entries
