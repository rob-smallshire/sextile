"""The request a handler is given, and what a departing caller leaves behind.

A handler is a function of a request, not of a page number. A viewdata terminal
is a display and nothing more, so all session state is held at the server, and
two callers keying the same number can be shown different things: because they
arrived through different menus, or because one is logged in.
"""

from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sextile.addressing import PageAddress
from sextile.state import State, StateReader

if TYPE_CHECKING:
    from sextile.application import Sextile


@dataclass(frozen=True)
class Neighbours:
    """The pages either side of this one, in the sequence being read.

    Which sequence depends on how the reader got here: a page reached through
    one menu has that menu's pages either side of it, and through another has
    that one's. A page reached by keying its number has neither, and should be
    offered neither.

    Attributes:
        previous: The page before this one in the sequence, or None.
        next: The page after this one in the sequence, or None.
    """

    previous: PageAddress | None = None
    next: PageAddress | None = None


@dataclass(frozen=True)
class PageRequest:
    """One page, asked for."""

    address: PageAddress

    app: "Sextile"
    """The service this page belongs to.

    Starlette's `request.app`. It lets a handler be an ordinary function
    declared beside its fellows rather than a closure built in a factory: a page
    that offers another page looks up where that page is through the service.
    """

    params: dict[str, object] = field(default_factory=dict)
    """What the route's pattern captured. Also passed to the handler as keyword
    arguments, so a handler need not unpack them."""

    neighbours: Neighbours = Neighbours()
    """The pages either side of this one in the sequence the reader is following,
    or a `Neighbours` of two Nones for a page reached by keying its number."""

    session: MutableMapping[str, object] = field(default_factory=dict)
    """What this caller has accumulated over their connection. The connection is
    the session -- the terminal keeps nothing but the frame on screen -- so this
    is where anything outlasting a single page belongs."""

    history: tuple[PageAddress, ...] = ()
    """Where this caller has been, oldest first, as far back as the session
    keeps. The terminal remembers none of it, so a service wanting to offer a
    way back through the call has to be handed the way back."""

    state: StateReader = field(default_factory=State)
    """What the service opened, for as long as it is running -- an archive, a
    client, an index -- read back through the `StateKey` it was written under.

    The counterpart of `session`: `session` is one caller's and lasts as long as
    the line, `state` is shared and lasts as long as the process. A read-only
    view here, because a change would reach every other caller at once; the
    lifespan writes it through `app.state`."""

@dataclass(frozen=True)
class Parting:
    """How far into a page a caller had got when the line was taken from them.

    Handed to the timeout hook alongside the `PageRequest` for the page they
    were on, which carries the address, the history and the session. Only the
    frame is here, because a request names a page and a page runs to several
    frames: there is no frame on a request to read this off.
    """

    frame_index: int = 0
    """Which frame of the page they were on, for a page that ran to several."""
