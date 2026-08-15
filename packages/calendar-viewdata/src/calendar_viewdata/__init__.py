"""A calendar as a Viewdata service: the framework's worked example."""

from calendar_viewdata.application import SERVICE_NAME, build_application

__version__ = "0.1.0"

#: The application a server is pointed at: `sextile serve calendar_viewdata:app`.
app = build_application()

__all__ = ["SERVICE_NAME", "app", "build_application"]
