#!/usr/bin/env bash
#
# Fail unless a release tag matches the sextile package version, so a `vX.Y.Z`
# tag can never publish a different version than the one declared in the
# package. Reproducible locally: scripts/check-tag-version.sh v0.1.0
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"

tag="${1:-${GITHUB_REF_NAME:-}}"
tag="${tag#v}"
if [ -z "$tag" ]; then
  echo "no tag given (argument or GITHUB_REF_NAME)"; exit 2
fi

version="$(grep -m1 '^version = ' packages/sextile/pyproject.toml | sed -E 's/^version = "([^"]+)"/\1/')"

if [ "$tag" != "$version" ]; then
  echo "release tag '$tag' does not match sextile version '$version'"; exit 1
fi
echo "release tag matches sextile version $version"
