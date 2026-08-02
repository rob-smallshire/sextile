"""The walking skeleton: proves the package imports and the test harness runs."""

from importlib.metadata import version

import sextile


def test_package_is_importable() -> None:
    assert sextile.__name__ == "sextile"


def test_package_reports_a_version() -> None:
    assert version("sextile") == sextile.__version__
