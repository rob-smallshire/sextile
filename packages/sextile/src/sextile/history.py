"""Where this caller has been, as a menu of shortcuts.

The session keeps a history so that `*0#` can retrace it one page at a time.
Showing the whole of it costs nothing more, and turns a stack into a map: key 1
for the page before this one, 2 for the one before that.

It is a framework page rather than each service's own because there is nothing
service-specific about it. What it lists are addresses, which the framework
already understands, and what it calls them comes from the route names, which
are the *application's* words -- so the labels read in the service's own
vocabulary without the framework knowing anything about forums or calendars.

Not registered anywhere. A service maps it into its own numbering, or does not
offer it at all:

    @page("92", name="history", title="Where you have been")
    async def _history(self, request: PageRequest) -> Page:
        return await self.history(request)

The page leaves itself out of the list. Visiting it is a move like any other, so
it enters the history too, and a list of places to go back to has no business
offering the one the reader is looking at.
"""

from collections.abc import Callable, Sequence
from typing import Final

from sextile.addressing import PageAddress
from sextile.page import Page
from sextile.templates import Menu, MenuItem

TITLE: Final = "WHERE YOU HAVE BEEN"

_NOWHERE: Final = "You have been nowhere else yet."


def history_page(
    *,
    address: PageAddress,
    been: Sequence[PageAddress],
    describe: Callable[[PageAddress], str],
    home: PageAddress,
    title: str = TITLE,
) -> Page:
    """Build the history page.

    ``been`` is oldest first, as the session keeps it; the page shows it newest
    first, so that key 1 means the same as `*0#` and the numbers count backwards
    through the call.
    """
    entries = [
        MenuItem(
            text=describe(where),
            #  How far back it is, because the digit only counts the steps on
            #  the first frame -- keys run 1-9 on every frame, as any other
            #  viewdata menu's do, so that no entry is shown which cannot be
            #  chosen.
            detail=f"*{where}#  {_how_far(step)}",
            destination=where,
        )
        for step, where in enumerate(
            (where for where in reversed(been) if where != address), start=1
        )
    ]
    return Menu(title=title, entries=entries, home=home, empty=_NOWHERE).build(address)


def _how_far(steps: int) -> str:
    """How many pages back this is, which the digit only says on the first frame."""
    return "one back" if steps == 1 else f"{steps} back"
