#!/bin/sh
# Download the pinned Foreman release, check it and unzip it.
# Usage: sh fetch_release.sh [tag]                  whole package (default tag v0.3.0, never main)
#        sh fetch_release.sh [tag] --bot <slug>     one bot at a time: only that bot's files
# Slugs: follow-audit follow-finder shoutout-picker reply-queue fan-finder rerun-picker analytics-log
set -eu
TAG="${1:-v0.3.0}"
SLUG=""
if [ "${2:-}" = "--bot" ]; then
  SLUG="${3:-}"
  [ -n "$SLUG" ] || { echo "Give a bot slug after --bot, for example: --bot reply-queue" >&2; exit 1; }
fi
DEST_PARENT="${FOREMAN_DEST:-/workspace}"
case "$TAG" in main|master|"") echo "Use a pinned release tag like v0.3.0, never a branch." >&2; exit 1 ;; esac
if [ -e "$DEST_PARENT/foreman/.template-master" ]; then
  echo "STOP. This is the template master copy. Setup never runs here." >&2; exit 1
fi
BASE="${FOREMAN_BASE:-https://github.com/GlennHasABeard/foreman/releases/download/$TAG}"
ZIP="foreman-$TAG.zip"
WORK="$(mktemp -d)"
cd "$WORK"
curl -fsSL -o "$ZIP" "$BASE/$ZIP"
curl -fsSL -o SHA256SUMS "$BASE/SHA256SUMS"
if ! grep " $ZIP\$" SHA256SUMS | sha256sum -c -; then
  echo "STOP. The checksum does not match. Nothing was unzipped. Do not install this file." >&2
  exit 1
fi
mkdir -p "$DEST_PARENT"
if [ -z "$SLUG" ]; then
  unzip -q -o "$ZIP" -d "$DEST_PARENT"
  echo "Foreman $TAG checked and unzipped into $DEST_PARENT/foreman."
  exit 0
fi
unzip -q -o "$ZIP" foreman/foreman/standalone.json -d "$WORK/m"
FILES="$(python3 - "$WORK/m/foreman/foreman/standalone.json" "$SLUG" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
for b in m["bots"]:
    if b["slug"] == sys.argv[2]:
        print("\n".join("foreman/" + f for f in b["files"]))
        break
else:
    sys.exit("Unknown bot slug %r. Use one of: %s" % (sys.argv[2], " ".join(b["slug"] for b in m["bots"])))
PY
)"
# shellcheck disable=SC2086
unzip -q -o "$ZIP" $FILES -d "$DEST_PARENT"
echo "Foreman $TAG checked. Unzipped only $SLUG's files into $DEST_PARENT/foreman:"
echo "$FILES" | sed 's#^foreman/#  #'
