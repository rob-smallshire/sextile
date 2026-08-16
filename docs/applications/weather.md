# The weather

A worked example: the weather, from met.no and a local gazetteer. It is the third
application, and a page of shapes where a forum is a page of words — which is why
it drove most of the framework's growth, and why not one of those changes was
about weather.

## The numbering

A third digit says how a forecast is drawn — a table, a graph — because the
presentation is part of the address a reader writes down:

```{literalinclude} ../../packages/weather-viewdata/docs/design.md
:language: text
:lines: 72-81
```

## Running it

```sh
uv run weather-viewdata import-places              # fill the gazetteer first (seconds)
uv run weather-viewdata serve                      # then answer calls
uv run weather-viewdata render --page 3213133880   # or draw Trondheim's forecast
```

## A forecast

`build_application` takes its forecast source as its one argument with no default,
so a fake source and a one-place index — seeded in a temporary file — draw a real
forecast offline:

```{sextile-frame}
:page: "3213133880"

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from weather_viewdata import build_application
from weather_viewdata.forecast.model import Forecast, Moment
from weather_viewdata.forecast.source import ForecastSource
from weather_viewdata.geonames import Place
from weather_viewdata.store import Index

TRONDHEIM = Place(
    geoname_id=3133880,
    name="Trondheim",
    ascii_name="Trondheim",
    alternate_names=(),
    latitude=63.43049,
    longitude=10.39506,
    feature_class="P",
    feature_code="PPL",
    country="NO",
    admin1="21",
    population=147139,
    elevation=18,
    timezone="Europe/Oslo",
)


class OneForecast(ForecastSource):
    """A forecast source that answers every place with the same weather."""

    async def forecast_for(self, place: Place) -> Forecast | None:
        del place
        start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        moments = tuple(
            Moment(
                at=start + timedelta(hours=hour),
                temperature=12.4 + hour,
                wind_speed=2.3,
                wind_from=225.0,
                precipitation=0.4,
                covers=timedelta(hours=1),
                symbol="lightrain",
            )
            for hour in range(12)
        )
        return Forecast(updated_at=start - timedelta(minutes=31), moments=moments)


_workspace_dirpath = Path(tempfile.mkdtemp())
_index_filepath = _workspace_dirpath / "places.sqlite"
with Index.open(_index_filepath) as _index:
    _index.add_places([TRONDHEIM])

app = build_application(
    source=OneForecast(),
    index_filepath=_index_filepath,
    visits_filepath=_workspace_dirpath / "visits.sqlite",
)
```

## What it asked of the framework

This is the point of the exercise. The calendar needed no framework change at
all; this service needed a great many, and none of them was about weather — which
is the test the arrangement had to pass.

The first were one thing wearing several hats: registration order was observable,
so each way of declaring a service was missing whatever the other had — a
converter that could not be registered in time for a class-declared pattern, a
module-level application that could not open anything or resolve a word of its
own, a `Handler` typed too narrowly to return `Page | None`. The answer was to
follow Starlette: a lifespan yielding what the service holds, `request.app`, pages
declared as data, and a middleware stack.

Then the drawing. Every one of these came from something that could not yet be
drawn:

| what was wanted | what the framework gained |
|---|---|
| two clocks in one lead-in, told apart by colour | a preamble line may be `Span`s |
| a strip of mosaics above a table | `Block`, a lead-in that is drawn |
| a lead-in filling the whole first frame | capacity may be nought; headings only where there are entries |
| a legend of pictures, placed by cell | `SequencePart.draw_entry` |
| days with air between them | `gap`, blanks between entries and not after each |
| temperature and wind as lines, rain as bars | `charting.curve`, `charting.bars` |
| a divider inside a page rather than at its edge | `thin_rule` |
| a symbol name in three rows of fourteen cells | `wrap_within` |
| `F` back to the search, on every frame | `Shortcut` |
| a title too long for a contents column | `Listing` carries it on rather than cutting |
| a page of what has been looked at | `visits`, `record_visits`, and two pages |
| a compass for a service with no item keys | `compass(items=False)` |
| the number a page was served under, read back | `Sextile.params_for` |

And three faults, each invisible until a service did something no service had done
before, and each in the framework rather than here: a keystroke that drew nothing
still moved the cursor (found by typing `ULAN BATOR`); a field lost its cursor
when a `*` request was cancelled; and the arrow keys did nothing on any service,
because nothing read a pressed arrow back as the letter it stood for. The last had
been true since the forum was written, and nobody had pressed one — the clearest
argument for a third application.
