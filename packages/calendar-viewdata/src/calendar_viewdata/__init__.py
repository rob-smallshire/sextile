"""A calendar as a Viewdata service: the second Sextile application."""

from calendar_viewdata.application import SERVICE_NAME, CalendarApplication

__version__ = "0.1.0"

#: The application a server is pointed at: `sextile serve calendar_viewdata:app`.
app = CalendarApplication()

__all__ = ["SERVICE_NAME", "CalendarApplication", "app"]
