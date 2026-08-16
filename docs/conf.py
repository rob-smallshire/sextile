"""Sphinx configuration for the Sextile documentation set.

The framework is the subject; the applications appear as worked examples. The
pages are MyST Markdown, and the API reference is generated from the framework's
own docstrings, which are its primary documentation.
"""

import os
import sys
from importlib.metadata import PackageNotFoundError, version

#  The Viewdata-frame directive lives beside the docs, not in the package.
sys.path.insert(0, os.path.abspath("_ext"))
#  The repo root, so the directive can draw the hero example (examples/hero.py).
sys.path.insert(0, os.path.abspath(".."))

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
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sextile_frames",
]

source_suffix = {".md": "markdown"}
root_doc = "index"

#  Everything the documentation set is made of lives under the Diátaxis tree and
#  the one legacy file it pulls in whole (the rework plan). Anything else under
#  docs/ is kept out so it raises no orphan warning. The architecture notes,
#  target architecture, open questions and spikes README are excluded rather than
#  pulled in: they link to files under packages/*/docs and to the raw
#  discussions, none of which are in this tree, so they cannot build clean until
#  the Phase 4 content pass ports them. They stay where they are meanwhile.
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "discussions/**",
    "spikes/*.py",
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

# -- autodoc / napoleon -------------------------------------------------------

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

#  Cross-references Sphinx cannot resolve under -n, with the reason each is
#  ignored rather than fixed:
nitpick_ignore = [
    #  Genuinely private types, none part of the surface, appearing only inside
    #  the annotations of public signatures.
    ("py:obj", "sextile.state._T"),  # the TypeVar behind StateKey
    ("py:class", "sextile.state._T"),
    ("py:class", "sextile.session.session.Session"),  # what a Caller wraps
    ("py:class", "sextile.routing.Match"),  # routing's internal match result
    ("py:class", "sextile.viewdata.attributes.Run"),  # the attribute planner's
]

# -- intersphinx --------------------------------------------------------------

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

# -- HTML ---------------------------------------------------------------------

html_theme = "furo"
html_title = f"Sextile {release}"

#  A docs-only bezel around the frames (the frame itself is the package's
#  viewdata.css, copied into _static by the sextile-frame directive).
html_static_path = ["_static"]
html_css_files = ["sextile-docs.css"]
