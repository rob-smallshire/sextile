"""A made-up service, for testing the framework without a real one.

The session and the server have to be driven by *some* application, and driving
them with Stardot's would prove only that the two still fit together. This one
is about nothing in particular: a menu, its items, a notice and a way out.

It is deliberately the smallest thing with all the shapes the framework has to
handle -- several frames to a page, a sequence running past the end of a frame,
and a page that ends the call.
"""

from typing import Final

from sextile.addressing import PageAddress
from sextile.application import PageRequest, Sextile
from sextile.page import Page, PageFrame
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, draw_chrome
from sextile.viewdata.controls import Colour

#: Nine choices to a frame, as a viewdata menu has.
PER_FRAME: Final = 9

#: What the service holds to begin with, newest first.
ITEMS: Final = 25


class Board(Sextile):
    """A service of no particular kind.

        1           the front page
        8           its items, nine to a frame
        82<id>      one item
        9           a notice, in one frame
        90          goodbye
    """

    def __init__(self) -> None:
        super().__init__()
        self.items: list[int] = [1000 + offset for offset in reversed(range(ITEMS))]
        self.page("1", name="main")(self.main)
        self.page("8", name="items")(self.items_menu)
        self.page("82{item_id:int}", name="item")(self.item)
        self.page("9", name="notice")(self.notice)
        self.page("90", name="goodbye")(self.goodbye)
        self.alias("MAIN", self.address_for("main"))
        self.alias("LATEST", self.address_for("items"))
        self.alias("BYE", self.address_for("goodbye"))

    async def main(self, request: PageRequest) -> Page:
        return self.menu(request.address, "THE BOARD", [self.address_for("items")])

    async def items_menu(self, request: PageRequest) -> Page:
        return self.menu(
            request.address,
            "ITEMS",
            [self.address_for("item", item_id=item) for item in self.items],
        )

    async def item(self, request: PageRequest, item_id: int) -> Page:
        canvas = Canvas()
        draw_chrome(
            canvas,
            title=f"ITEM {item_id}",
            page_number=request.address.frame_number(0),
            prompt="0 menu",
        )
        canvas.row(CONTENT_FIRST_ROW).text(f"Item {item_id}.", Colour.WHITE)
        choices = {"0": self.address_for("main")}
        #  Offered only to a reader who arrived through a menu, which is the one
        #  thing a page number cannot say for itself.
        if request.arrival.following is not None:
            choices["D"] = request.arrival.following
        if request.arrival.preceding is not None:
            choices["A"] = request.arrival.preceding
        return Page(frames=(PageFrame(frame=canvas.frame, choices=choices),))

    async def notice(self, request: PageRequest) -> Page:
        return self.menu(request.address, "A NOTICE", [])

    async def goodbye(self, request: PageRequest) -> Page:
        page = self.menu(request.address, "GOODBYE", [])
        return Page(frames=page.frames, hang_up=True)

    def menu(self, address: PageAddress, title: str, destinations: list[PageAddress]) -> Page:
        batches = [
            destinations[start : start + PER_FRAME]
            for start in range(0, len(destinations), PER_FRAME)
        ] or [[]]
        frames = []
        for index, batch in enumerate(batches):
            canvas = Canvas()
            draw_chrome(
                canvas,
                title=title,
                page_number=address.frame_number(index),
                prompt="1-9 select, 0 menu",
            )
            choices = {"0": self.address_for("main")}
            for offset, destination in enumerate(batch):
                choices[str(offset + 1)] = destination
                canvas.row(CONTENT_FIRST_ROW + offset).text(
                    f"{offset + 1} page {destination}", Colour.WHITE
                )
            moves = set()
            if index > 0:
                moves.add("W")
            if index + 1 < len(batches):
                moves.update({"S", "#"})
            frames.append(PageFrame(frame=canvas.frame, choices=choices, moves=frozenset(moves)))
        return Page(frames=tuple(frames))
