"""What a page is asked with, and what a caller leaves behind.

A handler is a function of a *request*, not of a page number. That
distinction matters more here than the corresponding one does on the web: a
viewdata terminal is a display and nothing more, so everything a session
knows is held at this end, and two callers keying the same number can
legitimately be shown different things once there is such a thing as being
logged in, or as having arrived from a particular menu.
"""

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sextile.addressing import PageAddress

if TYPE_CHECKING:
    from sextile.application import Application


@dataclass(frozen=True)
class Arrival:
    """The pages either side of this one, in the sequence being read.

    Which sequence depends on how the reader got here: a page reached through
    one menu has that menu's pages either side of it, and through another has
    that one's. A page reached by keying its number has neither, and should be
    offered neither.
    """

    preceding: PageAddress | None = None
    following: PageAddress | None = None


@dataclass(frozen=True)
class PageRequest:
    """One page, asked for."""

    address: PageAddress

    params: dict[str, object] = field(default_factory=dict)
    """What the route's pattern captured. Also passed to the handler as keyword
    arguments, so a handler need not unpack them."""

    arrival: Arrival = Arrival()

    session: MutableMapping[str, object] = field(default_factory=dict)
    """What this caller has accumulated over their connection. The connection is
    the session -- the terminal keeps nothing but the frame on screen -- so this
    is where anything outlasting a single page belongs."""

    history: tuple[PageAddress, ...] = ()
    """Where this caller has been, oldest first, as far back as the session
    keeps. The terminal remembers none of it, so a service wanting to offer a
    way back through the call has to be handed the way back."""

    application: "Application | None" = None
    """The service this page belongs to.

    Starlette's `request.app`, and here for the same reason: it is what lets a
    handler be an ordinary function declared beside its fellows rather than a
    closure built inside a factory. A page that offers another page has to ask
    the numbering where that one is, and this is how it asks.

    Optional only because a request built by hand in a test has no service
    behind it. Anything the session or the renderer builds carries one.
    """

    service: Mapping[str, object] = field(default_factory=dict)
    """What the service opened, for as long as it is running -- an archive, a
    client, an index.

    The counterpart of `session`, and the contrast is the whole point of there
    being two: `session` is this caller's and lasts as long as the line,
    `service` is everybody's and lasts as long as the process. Read-only here,
    because a page that changed what the service holds would be changing it for
    every other caller at once.

    What goes in it is whatever the application's `lifespan` yielded."""

    @property
    def app(self) -> "Application":
        """The service this page belongs to, and not None.

        `application` is optional because a request built by hand in a test
        has no service behind it. Every request the session or the renderer
        builds carries one, so a handler reached through either says
        `request.app` -- the narrowing every application was otherwise
        writing for itself, at the top of its own module.
        """
        if self.application is None:
            raise RuntimeError("this page was asked for outside a running service")
        return self.application


@dataclass(frozen=True)
class Parting:
    """Where a caller had got to when the line was taken from them.

    Everything the session knew, handed over because the terminal keeps none of
    it. A service can say "you were reading *82489493#", which is the one thing
    worth telling somebody who is about to dial back in.
    """

    address: PageAddress
    """The page they were on."""

    frame_index: int = 0
    """Which frame of it, for a page that ran to several."""

    history: tuple[PageAddress, ...] = ()
    """Where they had been, oldest first, as far back as the session kept."""

    session: Mapping[str, object] = field(default_factory=dict)
    """What they had accumulated over the call."""
