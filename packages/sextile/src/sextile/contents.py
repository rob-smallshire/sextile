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

from sextile.addressing import PageAddress
from sextile.page import Page
from sextile.templates import Listing, MenuItem

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
    entries = [
        MenuItem(text=f"*{page.keyed}#", detail=page.title)
        for page in sorted(pages, key=lambda page: page.keyed)
    ]
    return Listing(
        title=title, entries=entries, home=home, empty=_NOTHING
    ).build(address)
