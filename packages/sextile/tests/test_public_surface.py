"""What the services import of the framework, held to what is written down.

The surface used to be a sentence in a document and was crossed in six places
without anyone noticing, which is what a rule nobody checks is worth. This
reads the three services and fails when one reaches for machinery.

New public module? Add it to `PUBLIC` here and to `docs/public-surface.md`,
which is where a reader looks. Closing a crossing? Delete its line from
`CROSSINGS` and watch this stay green.
"""

import ast
import importlib
import pathlib
import re
from collections.abc import Iterator
from typing import Final

import pytest

#: Public as modules, with the names each offers listed in
#: `docs/public-surface.md`. A service may import from any of these and from
#: nothing else.
PUBLIC: Final = frozenset(
    {
        "sextile",
        "sextile.formatting",
        "sextile.layout",
        "sextile.keys",
        "sextile.content",
        "sextile.content.blocks",
        "sextile.forms",
        "sextile.handlers",
        "sextile.pages",
        "sextile.middleware",
        "sextile.state",
        "sextile.visits",
        "sextile.cli",
        "sextile.viewdata.compass",
        "sextile.testing",
        "sextile.viewdata",
        "sextile.viewdata.blocks",
        "sextile.viewdata.canvas",
        "sextile.viewdata.charset",
        "sextile.viewdata.charting",
        "sextile.viewdata.composition",
        "sextile.viewdata.controls",
        "sextile.viewdata.drawing",
        "sextile.viewdata.measure",
        "sextile.viewdata.font",
        "sextile.viewdata.frame",
        "sextile.viewdata.html",
        "sextile.viewdata.lettering",
        "sextile.viewdata.typesetting",
        "sextile.viewdata.wrapping",
    }
)

#: Machinery a service reaches for because the framework offers it no other
#: way, each written up under "Where the line is crossed" in
#: `docs/public-surface.md`. Every line here would be a framework defect rather
#: than a permission, and there are none: splitting a page into its furniture
#: and the parts between closed the last of them.
CROSSINGS: Final[frozenset[str]] = frozenset()

SERVICES: Final = ("stardot-viewdata", "weather-viewdata", "calendar-viewdata")

_WORKSPACE: Final = pathlib.Path(__file__).resolve().parents[3]


def imports_of(service: str) -> Iterator[tuple[pathlib.Path, str]]:
    """Every module of `sextile` that one service imports, and where from."""
    for found in sorted((_WORKSPACE / "packages" / service).rglob("*.py")):
        tree = ast.parse(found.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                named = node.module or ""
                if named == "sextile" or named.startswith("sextile."):
                    yield found, named
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "sextile" or alias.name.startswith("sextile."):
                        yield found, alias.name


def _service_src_dirpath(service: str) -> pathlib.Path:
    return _WORKSPACE / "packages" / service / "src"


def named_imports_of(service: str) -> Iterator[tuple[pathlib.Path, str, str]]:
    """Every `from sextile.<module> import <name>` in one service's source.

    Yields (path, module, name) for the source tree only, not the tests: a
    service's tests may reach for machinery to drive it, but its source is held
    to the surface. A `from sextile.x import y` where `y` is itself a public
    submodule is a module import, not a name, and is reported so the caller can
    accept it as such.
    """
    for found in sorted(_service_src_dirpath(service).rglob("*.py")):
        tree = ast.parse(found.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                named = node.module or ""
                if named == "sextile" or named.startswith("sextile."):
                    for alias in node.names:
                        yield found, named, alias.name


def _name_resolves(module: str, name: str) -> bool:
    """Whether a name listed in `module.__all__` can be obtained from it.

    A leaf name is an attribute; a public submodule (`sextile.viewdata` lists
    `lettering`) is not an attribute of its parent until first imported, so ask
    the import machinery for it directly.
    """
    imported = importlib.import_module(module)
    if hasattr(imported, name):
        return True
    try:
        importlib.import_module(f"{module}.{name}")
    except ImportError:
        return False
    return True


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


class TestEveryPublicModuleStatesItsNames:
    """`__all__` is the surface a module offers; the doc follows it.

    A module without `__all__` has no stated surface, so `from it import *`
    would take everything and a reader cannot tell contract from machinery.
    Each name in `__all__` must be obtainable, or the list is a promise the
    module does not keep.
    """

    @pytest.mark.parametrize("module", sorted(PUBLIC))
    def test_the_module_declares_all(self, module: str) -> None:
        imported = importlib.import_module(module)
        assert hasattr(imported, "__all__"), (
            f"{module} is public but declares no __all__; state its surface."
        )

    @pytest.mark.parametrize("module", sorted(PUBLIC))
    def test_every_name_in_all_resolves(self, module: str) -> None:
        imported = importlib.import_module(module)
        unresolved = [
            name for name in getattr(imported, "__all__", ()) if not _name_resolves(module, name)
        ]
        assert not unresolved, f"{module}.__all__ names what it does not offer: {unresolved}"


class TestTheServicesImportOnlyNamedSurface:
    """Beyond the module, the name: a service imports what a module exports.

    The module-level check says a service reaches for no machinery module; this
    says that within a public module it reaches for no name the module does not
    put in `__all__`. Only the services' source is held to this: their tests may
    drive the framework through machinery.
    """

    @pytest.mark.parametrize("service", SERVICES)
    def test_named_imports_are_all_exported(self, service: str) -> None:
        reached = set()
        for found, module, name in named_imports_of(service):
            if module not in PUBLIC:
                continue  # the module-level test already reports this crossing
            if name not in importlib.import_module(module).__all__:
                reached.add((found.name, module, name))
        assert not reached, (
            f"{service} imports names not in a module's __all__: {sorted(reached)}. "
            "Either the framework should export them and their __all__ wants "
            "updating, or the service should not be reaching for them."
        )

    def test_the_top_level_re_exports_all_resolve(self) -> None:
        import sextile

        unresolved = [name for name in sextile.__all__ if not _name_resolves("sextile", name)]
        assert not unresolved, f"sextile.__all__ names what it does not re-export: {unresolved}"


#: The API reference toctree: every `modules/<dotted module>` entry in it.
_API_INDEX: Final = _WORKSPACE / "docs" / "reference" / "api" / "index.md"
_MODULE_LINE: Final = re.compile(r"^\s*modules/(sextile(?:\.\w+)*)\s*$")


def _api_reference_modules() -> set[str]:
    return {
        match.group(1)
        for line in _API_INDEX.read_text(encoding="utf-8").splitlines()
        if (match := _MODULE_LINE.match(line))
    }


class TestTheApiReferenceMatchesTheSurface:
    """The API reference documents every public module and no other.

    The toctree in `docs/reference/api/index.md` lists a page per module;
    holding that list to `PUBLIC` keeps a new public module from being added
    without a reference page, and a page from outliving the module it documented.
    """

    def test_it_lists_exactly_the_public_modules(self) -> None:
        assert _api_reference_modules() == set(PUBLIC)
