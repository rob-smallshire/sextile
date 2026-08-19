# Accept typed input

A how-to guide: a form the reader types into, one field or several, finished with
RETURN.

```{sextile-frame}
:page: "1"
:keys: "ADA"
:show-code:

from sextile import OnOneFrame, Page, PageAddress, PageLayout, PageRequest, PageRouter, Sextile
from sextile.forms import Field, FieldSet

router = PageRouter()

@router.page("1", name="signin", title="Sign in")
async def signin(request: PageRequest) -> Page:
    form = FieldSet(
        fields=[Field(name="name", label="NAME", row=0, accepts=str.isalpha, width=12, hint=" your name", hint_row=1)],
        on_submit=lambda values: PageAddress("2") if values["name"] else None,
        submit_label="sign in",
    )
    return PageLayout(parts=[OnOneFrame(form)]).build(request)

app = Sextile(name="Desk", pages=[*router])
```

A `FieldSet` owns some rows of the frame: each `Field` has a `label`, an `accepts`
predicate saying what belongs in it, a `width`, and a `hint` drawn beneath it.
`on_submit` is asked the keyed values whenever the form is drawn and returns where
RETURN leads, or `None` while there is nowhere to go — so the `# sign in` mark
appears only once the form can be submitted.

Two or more fields are moved between with TAB, and a `footnote` says something
about what has been keyed so far:

```{sextile-frame}
:page: "1"
:keys: "ADA\tLOVELACE"
:show-code:

from sextile import OnOneFrame, Page, PageAddress, PageLayout, PageRequest, PageRouter, Sextile
from sextile.forms import Field, FieldSet

router = PageRouter()

@router.page("1", name="signin", title="Sign in")
async def signin(request: PageRequest) -> Page:
    async def whole(values: dict[str, str]) -> str:
        return f"{values['first']} {values['last']}".strip()
    form = FieldSet(
        fields=[
            Field(name="first", label="FIRST", row=0, accepts=str.isalpha, width=10),
            Field(name="last", label="LAST", row=2, accepts=str.isalpha, width=10),
        ],
        on_submit=lambda values: PageAddress("2") if values["first"] and values["last"] else None,
        footnote=whole, footnote_row=4, submit_label="sign in",
    )
    return PageLayout(parts=[OnOneFrame(form)]).build(request)

app = Sextile(name="Desk", pages=[*router])
```

A field takes digits as data — a nought keyed into it is a nought — so a page
carrying a form cannot offer `0` for the index. Name a way out in the footer
instead, with the `FieldSet`'s `footer_items`.

The form API is {py:mod}`sextile.forms`; why a form is a menu whose choices
change, and why a digit chooses while a letter types, is in
{doc}`../explanation/design-decisions`. For a field with matches beneath it, see
{doc}`type-ahead-completion`.
