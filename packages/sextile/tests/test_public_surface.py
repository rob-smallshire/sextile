"""What the services import of the framework, held to what is written down.

The surface used to be a sentence in a document and was crossed in six places
without anyone noticing, which is what a rule nobody checks is worth. This
reads the three services and fails when one reaches for machinery.

New public module? Add it to `PUBLIC` here and to `docs/public-surface.md`,
which is where a reader looks. Closing a crossing? Delete its line from
`CROSSINGS` and watch this stay green.
"""

import ast
import pathlib
from collections.abc import Iterator
from typing import Final

import pytest

#: Public as modules, with the names each offers listed in
#: `docs/public-surface.md`. A service may import from any of these and from
#: nothing else.
PUBLIC: Final = frozenset(
    {
        "sextile",
        "sextile.templates",
        "sextile.keys",
        "sextile.content",
        "sextile.content.blocks",
        "sextile.forms",
        "sextile.handlers",
        "sextile.middleware",
        "sextile.visits",
        "sextile.cli",
        "sextile.testing",
        "sextile.viewdata",
        "sextile.viewdata.blocks",
        "sextile.viewdata.canvas",
        "sextile.viewdata.charset",
        "sextile.viewdata.charting",
        "sextile.viewdata.composition",
        "sextile.viewdata.controls",
        "sextile.viewdata.drawing",
        "sextile.viewdata.encoding",
        "sextile.viewdata.font",
        "sextile.viewdata.frame",
        "sextile.viewdata.lettering",
        "sextile.viewdata.wrapping",
    }
)

#: Machinery a service reaches for because the framework offers it no other
#: way, each written up under "Where the line is crossed" in
#: `docs/public-surface.md`. Every line here is a framework defect, not a
#: permission.
CROSSINGS: Final = frozenset(
    {
        #  Chrome, footers and pagination drawn by hand, for want of a template
        #  whose shape is a heading and a body.
        "sextile.viewdata.chrome",
        "sextile.viewdata.footer",
        "sextile.viewdata.typesetting",
    }
)

SERVICES: Final = ("stardot-viewdata", "weather-viewdata", "calendar-viewdata")

_WORKSPACE: Final = pathlib.Path(__file__).resolve().parents[3]


def imports_of(service: str) -> Iterator[tuple[pathlib.Path, str]]:
    """Every module of `sextile` that one service imports, and where from."""
    for found in sorted((_WORKSPACE / "packages" / service).rglob("*.py")):
        tree = ast.parse(found.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                named = node.module or ""
                if named == "sextile" or named.startswith("sextile."):
                    yield found, named
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "sextile" or alias.name.startswith("sextile."):
                        yield found, alias.name


class TestTheServicesImportOnlyWhatIsPublic:
    """Read the services rather than trusting the document, which was wrong.

    Both are checked: that nothing reaches past the surface, and that the list
    of known crossings does not quietly grow stale in the other direction --
    an exception left behind after the defect it names has been fixed reads as
    permission to do it again.
    """

    @pytest.mark.parametrize("service", SERVICES)
    def test_nothing_reaches_into_the_machinery(self, service: str) -> None:
        reached = {
            (found.name, module)
            for found, module in imports_of(service)
            if module not in PUBLIC and module not in CROSSINGS
        }
        assert not reached, (
            f"{service} imports framework machinery: {sorted(reached)}. "
            "Either the framework should offer this and docs/public-surface.md "
            "wants updating, or the service should not be doing it."
        )

    def test_every_known_crossing_is_still_crossed(self) -> None:
        reached = {
            module for service in SERVICES for _, module in imports_of(service)
        }
        stale = CROSSINGS - reached
        assert not stale, (
            f"no service imports {sorted(stale)} any more: delete it from "
            "CROSSINGS and from docs/public-surface.md."
        )

    def test_the_public_list_names_modules_that_exist(self) -> None:
        source = _WORKSPACE / "packages" / "sextile" / "src"
        for module in PUBLIC | CROSSINGS:
            path = source / pathlib.Path(*module.split("."))
            assert path.with_suffix(".py").is_file() or (path / "__init__.py").is_file(), (
                f"{module} is listed as public and does not exist"
            )
