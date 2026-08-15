"""Sphinx configuration for the Sextile documentation set.

The framework is the subject; the applications appear as worked examples. The
pages are MyST Markdown, and the API reference is generated from the framework's
own docstrings, which are its primary documentation.
"""

from importlib.metadata import PackageNotFoundError, version

project = "Sextile"
author = "Robert Smallshire"
copyright = "Robert Smallshire"  # noqa: A001

try:
    release = version("sextile")
except PackageNotFoundError:
    release = "0"
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
]

templates_path = ["_templates"]
source_suffix = {".md": "markdown"}
root_doc = "index"

#  Everything the documentation set is made of lives under the Diátaxis tree and
#  the legacy files it pulls in by name. Anything else under docs/ -- the raw
#  discussions, the spikes' code -- is kept out so it raises no orphan warning.
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "discussions/**",
    "**/__pycache__/**",
]

# -- MyST ---------------------------------------------------------------------

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "attrs_inline",
]
myst_heading_anchors = 3

# -- autodoc / autosummary / napoleon -----------------------------------------

autosummary_generate = True

#  Every docstring is Google style; napoleon is configured for that and numpy is
#  off so it does not try to read them the other way.
napoleon_google_docstring = True
napoleon_numpy_docstring = False

#  With :members: and a module that declares __all__, autodoc documents exactly
#  the stated surface, which is what public-surface.md pins.
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
}
autodoc_member_order = "bysource"

#  sphinx-autodoc-typehints reads the annotations and moves them into the
#  parameter descriptions, so a signature is not repeated in full twice.
always_document_param_types = True

# -- intersphinx --------------------------------------------------------------

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

# -- HTML ---------------------------------------------------------------------

html_theme = "furo"
html_title = f"Sextile {release}"
