"""What a service is made of, from its own registrations.

A list of the pages a service advertises, each with the number a reader would
key. Where a page number carries a field, the field is shown as a placeholder
rather than enumerated:

    *5#            By user
    *52<user-id>#  One user

Nobody can list every user on a screen, but everybody holding a user number can
be shown where to key it. This works because the framework knows the patterns,
not a hand-maintained list of addresses.

A page appears here if it was given a title when it was registered. That is how
a title frame stays off the list without a flag of its own: giving a page a
title is a service saying it may be advertised.

Registered nowhere, like the history page. A service gives it a number with
`standard_pages` or does without:

    Sextile(pages=list(standard_pages(contents="93")))
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Final

from sextile.formatting import Listing, MenuItem
from sextile.layout import PageLayout
from sextile.page import Page, keyed

if TYPE_CHECKING:
    from sextile.requests import PageRequest
    from sextile.routing import PageRoute

TITLE: Final = "EVERY PAGE"

_NOTHING: Final = "This service advertises no pages."


def contents_page(
    *,
    request: "PageRequest",
    pages: Sequence["PageRoute"],
    title: str = TITLE,
) -> Page:
    """Build the contents page: one row per advertised page, over as many frames as it needs.

    Args:
        request: The request this page answers.
        pages: The routes to list.
        title: What the header calls the page.

    Returns:
        The page, ordered by the number rather than by declaration order.
        Sorting the digits as text puts each namespace root beside its members
        (5 then 52<n>), which is what a scheme whose first digit names a
        namespace means. A title too long for the room left after the numbers
        carries on to a second row.
    """
    entries = [
        MenuItem(text=keyed(page.keyed), detail=page.title)
        for page in sorted(pages, key=lambda page: page.keyed)
    ]
    return PageLayout(
        title=title, parts=[Listing(entries=entries, empty=_NOTHING)]
    ).build(request)
