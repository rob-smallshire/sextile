"""Stardot as a Viewdata service: one Sextile application among the possible ones."""

from stardot_viewdata.application import (
    DEFAULT_DATABASE_FILEPATH,
    StardotApplication,
)

__version__ = "0.1.0"

#: The application a server is pointed at: `sextile serve stardot_viewdata:app`.
app = StardotApplication()

__all__ = ["DEFAULT_DATABASE_FILEPATH", "StardotApplication", "app"]
