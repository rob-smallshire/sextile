# Write a converter

A how-to guide: number pages by a field of your own — a date, a coordinate, a
code — read from the digits and written back for a link.

```{sextile-frame}
:page: "93"
:show-code:

from sextile import Converter, Page, PageRequest, PageRouter, Sextile, fixed_integer, notice_page, standard_pages

router = PageRouter()

MONTH = Converter(field_pattern=r"0[1-9]|1[0-2]", width=2, parse=int, format=lambda value: f"{value:02d}")


@router.page("7{year:year}{month:month}", name="report", title="Monthly report")
async def report(request: PageRequest, year: int, month: int) -> Page:
    return notice_page(request, f"Report for {year}-{month:02d}.")


app = Sextile(
    name="Reports",
    converters={"year": fixed_integer(4), "month": MONTH},
    pages=[*router, *standard_pages(contents="93")],
)
```

A `Converter` says how one field is read and written: `field_pattern` matches its
digits, `width` fixes how many so two fields sit next to each other with no
separator, `parse` turns the digits into what the handler is passed, and `format`
writes a value back for `address_for("report", year=2026, month=8)`.
`fixed_integer(4)` is the framework's own converter for a zero-padded whole number
of a set width, which is what the year wants; `MONTH` adds the `01`–`12` range a
plain integer would not check. Name the converters in `converters=` and reference
each by name in a pattern — `{month:month}`. `parse` may raise `ValueError` to
reject digits its pattern could not, and the contents page shows a field as a
placeholder rather than enumerating it.
