#!/usr/bin/env bash
#
# Run the CI sequence locally, in a throwaway environment, so the wheel-based
# tests can be proven green before anything is pushed. This mirrors the steps in
# .github/workflows/ci.yml. The point of the exercise: the tests run against the
# INSTALLED WHEELS, not the editable source tree, so a missing package-data
# declaration (a font, the CSS, the licence text) fails here rather than in a
# user's install.
#
# CI does this in a fresh runner where `uv sync --no-install-workspace` leaves a
# .venv with no editable workspace on it. Locally your .venv already has the
# editable workspace, which would smuggle packages/*/src onto sys.path, so this
# builds and activates a dedicated environment instead.
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export UV_PROJECT_ENVIRONMENT="$WORK/venv"

echo "== 1/7 sync third-party dependencies only (no workspace packages) =="
uv sync --no-install-workspace

# Activate the throwaway environment so pip/python/pytest below all resolve to
# it rather than to the developer's .venv.
export VIRTUAL_ENV="$WORK/venv"
export PATH="$WORK/venv/bin:$PATH"

echo "== 2/7 ruff (against source) =="
ruff check .

echo "== 3/7 mypy --strict (against source, via mypy_path) =="
mypy

echo "== 4/7 build every workspace wheel =="
rm -rf dist/
uv build --all-packages --out-dir dist/
ls -1 dist/*.whl

# Metadata check only, local to this script -- publishing itself is `uv publish`
# (no twine anywhere in the repo). twine is fetched ephemerally, not depended on.
echo "-- twine metadata check (local only) --"
uv run --no-project --with twine twine check dist/*

echo "== 5/7 install the wheels into the environment =="
uv pip install dist/*.whl

echo "== 6/7 guard: sextile must import from the wheel, not the source tree =="
python scripts/check-wheel-import.py

echo "== 7/7 tests against the installed wheels =="
pytest -v

echo "== all steps passed =="
