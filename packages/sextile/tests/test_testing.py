"""Driving a service the way a caller does, for a service's own tests.

Every service wants this and the framework offered no way to do it, so weather
reached into `sextile.session.session` and wrote the plumbing again. What is
tested here is the helper, not the session: that keys arrive, that the screen
can be read, and that the service is opened and closed around the call.
"""

from sextile import Page, PageAddress, PageRequest, PageRoute, Sextile
from sextile.formatting import Lines, Menu, MenuItem
from sextile.layout import Flow, PageLayout
from sextile.testing import calling


async def index(request: PageRequest) -> Page:
    app = request.app
    return PageLayout(
        title="INDEX",
        home=app.index,
        parts=[
            Flow(
                Menu(
                    entries=[
                        MenuItem(
                            text="The weather", destination=app.address_for("weather")
                        )
                    ]
                )
            )
        ],
    ).build(request)


async def weather(request: PageRequest) -> Page:
    return PageLayout(
        title="WEATHER",
        home=PageAddress("1"),
        parts=[Flow(Lines(said=("Rain, mostly.",)))],
    ).build(request)


def service() -> Sextile:
    return Sextile(
        pages=[
            PageRoute("1", index, name="index", title="Index"),
            PageRoute("2", weather, name="weather", title="The weather"),
        ]
    )


class TestCallingAService:
    async def test_the_first_frame_is_shown_without_asking(self) -> None:
        async with calling(service()) as caller:
            assert "INDEX" in caller.shown

    async def test_a_digit_chooses(self) -> None:
        async with calling(service()) as caller:
            await caller.key("1")
            assert caller.address == PageAddress("2")
            assert "Rain, mostly." in caller.shown

    async def test_a_page_can_be_keyed_by_number(self) -> None:
        async with calling(service()) as caller:
            await caller.key("*2#")
            assert caller.address == PageAddress("2")

    async def test_keys_may_be_sent_one_at_a_time_or_together(self) -> None:
        async with calling(service()) as caller:
            for character in "*2#":
                await caller.key(character)
            assert caller.address == PageAddress("2")

    async def test_a_code_no_keyboard_spells_is_sent_as_bytes(self) -> None:
        #  RETURN is 0x5F on this wire, which is not what a keyboard's return
        #  key sends and not something a string can carry unambiguously.
        async with calling(service()) as caller:
            await caller.key(b"*2\x5f")
            assert caller.address == PageAddress("2")

    async def test_the_call_may_start_anywhere(self) -> None:
        async with calling(service(), start="2") as caller:
            assert caller.address == PageAddress("2")

    async def test_what_the_service_sent_is_kept(self) -> None:
        async with calling(service()) as caller:
            await caller.key("1")
            assert caller.sent, "nothing was sent to the terminal"


class TestTheServiceIsOpenedAndClosedAroundTheCall:
    async def test_the_lifespan_runs(self) -> None:
        opened, closed = [], []

        class Watched(Sextile):
            async def startup(self) -> None:
                opened.append(True)
                await super().startup()

            async def shutdown(self) -> None:
                closed.append(True)
                await super().shutdown()

        app = Watched(pages=[PageRoute("1", index, name="index", title="Index")])
        async with calling(app) as caller:
            assert opened
            assert not closed
            assert caller.shown
        assert closed
