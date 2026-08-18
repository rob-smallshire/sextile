# The weather

A worked example: the weather, from met.no and a local gazetteer. It is the third
application, and the first to be deployed — it lives in its own repository,
[rob-smallshire/weather-viewdata](https://github.com/rob-smallshire/weather-viewdata),
and answers calls as the first live Sextile service at `weather.viewdata.no`, port
16651. It is a page of shapes where a forum is a page of words, which is why it
drove most of the framework's growth, and why not one of those changes was about
weather.

## What it asked of the framework

This is the point of the exercise. The calendar needed few framework changes;
this service needed a great many, and none of them was about weather — which is
the test the arrangement had to pass.

Every one of these came from something that could not yet be drawn:

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
