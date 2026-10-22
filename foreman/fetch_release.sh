#!/bin/sh
# Download the pinned Foreman release, check it and unzip it.
# Usage: sh fetch_release.sh [tag]   (default tag v0.1.0, never main)
set -eu
TAG="${1:-v0.1.0}"
case "$TAG" in main|master|"") echo "Use a pinned release tag like v0.1.0, never a branch." >&2; exit 1 ;; esac
BASE="https://github.com/GlennHasABeard/foreman/releases/download/$TAG"
ZIP="foreman-$TAG.zip"
WORK="$(mktemp -d)"
cd "$WORK"
curl -fsSL -o "$ZIP" "$BASE/$ZIP"
curl -fsSL -o SHA256SUMS "$BASE/SHA256SUMS"
if ! grep " $ZIP\$" SHA256SUMS | sha256sum -c -; then
  echo "STOP. The checksum does not match. Nothing was unzipped. Do not install this file." >&2
  exit 1
fi
mkdir -p /workspace
unzip -q -o "$ZIP" -d /workspace
echo "Foreman $TAG checked and unzipped into /workspace/foreman."
