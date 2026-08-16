"""Fail unless `sextile` imports from an installed wheel, not the source tree.

Run after installing the built wheels and before the tests, so a suite that
quietly imported `packages/*/src` -- and so never exercised the packaged
artefact -- is caught rather than passing against the wrong code. This is what
turns a missing package-data declaration (a font, the CSS, the licence text)
into a red build.
"""

import sys
from pathlib import Path

import sextile

where = Path(sextile.__file__).resolve()
print("sextile imported from:", where)
if "packages" in where.parts and "src" in where.parts:
    sys.exit(f"FAIL: sextile imported from the source tree, not the installed wheel: {where}")
print("OK: imported from the installed wheel")
