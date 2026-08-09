"""The Stardot forum as a Viewdata service."""

from stardot_viewdata.application import (
    DEFAULT_DATABASE_FILEPATH,
    PAGES,
    SERVICE_NAME,
    build_application,
)

__version__ = "0.1.0"

#: The application a server is pointed at: `sextile serve stardot_viewdata:app`.
app = build_application()

__all__ = [
    "DEFAULT_DATABASE_FILEPATH",
    "PAGES",
    "SERVICE_NAME",
    "app",
    "build_application",
]
