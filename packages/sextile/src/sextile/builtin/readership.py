"""What readers have been looking at, as pages a reader can look at.

What has been read lately and what has been read most are menus rather than
tables: every row is a page number, so every row is somewhere to go. How many
have called is a table of figures, there being nothing to follow in a count.

Registered nowhere, like the history, the contents and the words. A service
maps them into its own numbering or does without.

**A page that no longer exists is left off.** A log is a record of what was
fetched and a menu is an offer, so the two are not the same list: a number that
answered last week and does not answer now belongs in one and not the other.
`label` is asked, and a page the service will not name is not offered.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

from sextile.addressing import PageAddress, keyed
from sextile.formatting import Figures, Lines, Menu, MenuItem
from sextile.layout import Every, Flowing, PageLayout
from sextile.page import Page
from sextile.viewdata.controls import Colour
from sextile.viewdata.frame import COLUMNS

if TYPE_CHECKING:
    from sextile.requests import PageRequest
from sextile.viewdata.wrapping import wrap_text
from sextile.visits import Visit

#  Upper-cased, as every heading is: `Sextile.heading` upper-cases the title a
#  service registered, and these are what it falls back to when a service
#  registered none. Two adjacent framework pages should not disagree about
#  their own case.
RECENT_TITLE: Final = "LATELY READ"
POPULAR_TITLE: Final = "MOST READ"
CALLERS_TITLE: Final = "WHO HAS CALLED"

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

#  One string: what the two pages have to say about an empty log is the same
#  thing, and two copies of it drift.
_NOTHING_READ: Final = "Nothing has been read yet."

#: How long ago, in the largest unit that says something. A reader wants "an
#: hour ago" rather than "63 minutes ago", and "just now" rather than a figure
#: that will be wrong by the time the frame has finished arriving.
_AGES: Final = ((86400, "day"), (3600, "hour"), (60, "minute"))


def recent_page(
    *,
    request: "PageRequest",
    visits: Sequence[Visit],
    label: Callable[[PageAddress], str],
    title: str = RECENT_TITLE,
    now: datetime | None = None,
) -> Page:
    """What has been looked at lately, newest first."""
    when = now or datetime.now(UTC)
    return _menu(
        request=request,
        title=title,
        empty=_NOTHING_READ,
        entries=[
            (visit, _ago(when - visit.at.astimezone(UTC))) for visit in visits
        ],
        label=label,
    )


def popular_page(
    *,
    request: "PageRequest",
    visits: Sequence[Visit],
    label: Callable[[PageAddress], str],
    title: str = POPULAR_TITLE,
) -> Page:
    """What has been looked at most, the most read first."""
    return _menu(
        request=request,
        title=title,
        empty=_NOTHING_READ,
        entries=[(visit, _times(visit.times)) for visit in visits],
        label=label,
    )


def _menu(
    *,
    request: "PageRequest",
    title: str,
    empty: str,
    entries: Sequence[tuple[Visit, str]],
    label: Callable[[PageAddress], str],
) -> Page:
    return PageLayout(
        title=title,
        parts=[
            Flowing(
                Menu(
                    entries=[
                        MenuItem(
                            text=named,
                            detail=f"{keyed(visit.page)}  {said}",
                            destination=visit.page,
                        )
                        for visit, said in entries
                        if (named := label(visit.page))
                    ],
                    empty=empty,
                )
            )
        ],
    ).build(request)


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
    request: "PageRequest",
    counts: Sequence[tuple[str, int]],
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
    #  Nought against every period reads as a fault rather than as a service
    #  that has only just been switched on, so it is the empty case too.
    reporting = counts if any(count for _, count in counts) else ()
    return PageLayout(
        title=title,
        parts=[
            Flowing(
                Figures(
                    entries=[
                        MenuItem(text=said, detail=str(count))
                        for said, count in reporting
                    ],
                    empty=_NOTHING_CALLED,
                )
            ),
            #  Beneath the figures on every frame, a blank row above it: a
            #  figure about readers that does not say what it counts invites
            #  the worst guess.
            Every(
                Lines(
                    said=("", *wrap_text(_WHAT_A_CALLER_IS, COLUMNS - 1)),
                    colour=Colour.GREEN,
                )
            ),
        ],
    ).build(request)
