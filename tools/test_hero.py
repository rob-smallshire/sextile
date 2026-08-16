"""The hero example serves its title page, drawn from the shipped fonts."""

from examples.hero import app

from sextile.testing import fetch, text_of


async def test_the_title_page_draws_the_name_and_strapline() -> None:
    await app.startup()
    try:
        page = await fetch(app, "1")
    finally:
        await app.shutdown()
    assert "Viewdata services in Python." in text_of(page)
