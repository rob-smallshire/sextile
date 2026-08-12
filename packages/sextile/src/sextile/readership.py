"""What readers have been looking at, as pages a reader can look at.

Two of them, and both are menus rather than tables: every row is a page number,
so every row is somewhere to go. A list of what other people have been reading
that you cannot follow is a list that has been written at you.

Registered nowhere, like the history, the contents and the words. A service
maps them into its own numbering or does without.

**A page that no longer exists is left off.** A log is a record of what was
fetched and a menu is an offer, so the two are not the same list: a number that
answered last week and does not answer now belongs in one and not the other.
`describe` is asked, and a page the service will not name is not offered.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Final

from sextile.addressing import PageAddress, keyed
from sextile.page import Page, PageFrame
from sextile.templates import CHOICES_PER_FRAME, Menu, MenuItem
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, draw_chrome
from sextile.viewdata.controls import Colour
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.footer import ROOM, FooterItem, Priority, render_footer
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.wrapping import wrap_text
from sextile.visits import Visit

RECENT_TITLE: Final = "Lately read"
POPULAR_TITLE: Final = "Most read"
CALLERS_TITLE: Final = "Who has called"

#: The windows the count of callers is reported over. Days rather than
#: calendar days, so that no clock and no zone comes into it: "the last seven
#: days" means the same thing to a service and to whoever is reading it,
#: wherever either of them is.
PERIODS: Final = (
    (timedelta(days=1), "Last 24 hours"),
    (timedelta(days=7), "Last 7 days"),
    (timedelta(days=30), "Last 30 days"),
)

#: What a caller is, said on the page rather than left for somebody to wonder
#: about. A figure about readers that does not say what it counts invites the
#: worst guess.
_WHAT_A_CALLER_IS: Final = (
    "A caller is one connection. The log keeps a token for each and nothing "
    "else, so this can say how many and never who."
)

_NOTHING_CALLED: Final = "Nobody has called yet."

#: Where the figures sit: two cells of margin, the widest label, and then the
#: count right-aligned against a column of its own.
_LABEL_AT: Final = 2
_COUNT_CELLS: Final = 6
_GAP: Final = 2

_NOTHING_RECENT: Final = "Nothing has been read yet."
_NOTHING_POPULAR: Final = "Nothing has been read yet."

#: How long ago, in the largest unit that says something. A reader wants "an
#: hour ago" rather than "63 minutes ago", and "just now" rather than a figure
#: that will be wrong by the time the frame has finished arriving.
_AGES: Final = ((86400, "day"), (3600, "hour"), (60, "minute"))


def recent_page(
    *,
    address: PageAddress,
    visits: Sequence[Visit],
    describe: Callable[[PageAddress], str],
    home: PageAddress,
    title: str = RECENT_TITLE,
    now: datetime | None = None,
) -> Page:
    """What has been looked at lately, newest first."""
    when = now or datetime.now(UTC)
    return _menu(
        address=address,
        title=title,
        home=home,
        empty=_NOTHING_RECENT,
        entries=[
            (visit, _ago(when - visit.at.astimezone(UTC))) for visit in visits
        ],
        describe=describe,
    )


def popular_page(
    *,
    address: PageAddress,
    visits: Sequence[Visit],
    describe: Callable[[PageAddress], str],
    home: PageAddress,
    title: str = POPULAR_TITLE,
) -> Page:
    """What has been looked at most, the most read first."""
    return _menu(
        address=address,
        title=title,
        home=home,
        empty=_NOTHING_POPULAR,
        entries=[(visit, _times(visit.times)) for visit in visits],
        describe=describe,
    )


def _menu(
    *,
    address: PageAddress,
    title: str,
    home: PageAddress,
    empty: str,
    entries: Sequence[tuple[Visit, str]],
    describe: Callable[[PageAddress], str],
) -> Page:
    return Menu(
        title=title,
        entries=[
            MenuItem(
                text=named,
                detail=f"{keyed(visit.page)}  {said}",
                destination=visit.page,
            )
            for visit, said in entries
            if (named := describe(visit.page))
        ][:CHOICES_PER_FRAME],
        home=home,
        empty=empty,
    ).build(address)


def _ago(since: timedelta) -> str:
    """How long ago something happened, in one unit and plain words."""
    seconds = int(since.total_seconds())
    for size, unit in _AGES:
        if seconds >= size:
            how_many = seconds // size
            return f"{how_many} {unit}{'s' if how_many > 1 else ''} ago"
    return "just now"


def _times(count: int) -> str:
    return "read once" if count == 1 else f"read {count} times"


def callers_page(
    *,
    address: PageAddress,
    counts: Sequence[tuple[str, int]],
    home: PageAddress,
    title: str = CALLERS_TITLE,
) -> Page:
    """How many have called, over each of a few periods.

    The only figure a service keeps about its readers, and a count of
    connections rather than of anybody: `record_visits` mints a token per
    session and stores nothing else.

    **A period longer than the log is kept for reads low**, and silently. The
    default periods end at thirty days because that is what the log keeps by
    default; a service that trims sooner should pass its own.
    """
    canvas = Canvas()
    draw_chrome(
        canvas,
        title=title,
        page_number=address.frame_number(0),
        prompt=render_footer([FooterItem("0", "index", Priority.ESSENTIAL)], ROOM),
    )
    row = CONTENT_FIRST_ROW
    if not counts or not any(count for _, count in counts):
        canvas.row(row).text(_NOTHING_CALLED, Colour.WHITE)
    else:
        column = max(cell_count(label) for label, _ in counts) + _GAP
        for offset, (label, count) in enumerate(counts):
            written = canvas.row(row + offset)
            written.skip(_LABEL_AT)
            written.text(f"{label:<{column}}", Colour.WHITE)
            written.text(f"{count:>{_COUNT_CELLS}}", Colour.CYAN)
        row += len(counts) + 1
    for offset, line in enumerate(wrap_text(_WHAT_A_CALLER_IS, COLUMNS - 1)):
        canvas.row(row + offset + 1).text(line, Colour.GREEN)
    return Page(
        frames=(PageFrame(frame=canvas.frame, choices={"0": home}),)
    )
