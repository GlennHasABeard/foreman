#!/usr/bin/env python3
"""Foreman update notice. Read only on X: this never touches X. It only reads GitHub's
public release list, anonymously, at no cost.

  python3 update_check.py check [--force]
      At most once a day per computer: ask GitHub for the newest Foreman release.
      If it is newer than this package's pinned version, print its release notes and
      the question to ask the owner. Downloads nothing. Exit code 0 always, except bad use.
  python3 update_check.py fetch <tag> --yes
      Only after the owner said yes to that exact tag: download foreman-<tag>.zip and
      SHA256SUMS into a staging folder and check the zip against SHA256SUMS. On a
      mismatch it deletes the zip and stops. It never installs or unzips over the
      running bots; install from the checked zip with fetch_release.sh <tag> as usual.

Settings (environment, all optional):
  FOREMAN_REPO         owner/name of the release repo (default: the repo in RELEASES below)
  FOREMAN_API          API base (default https://api.github.com)
  FOREMAN_UPDATE_DIR   where the once-a-day note and staged downloads go
                       (default /workspace/foreman-updates, shared by every bot on this computer)
"""
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RELEASES = "https://github.com/GlennHasABeard/foreman/releases"
REPO = os.environ.get("FOREMAN_REPO", "/".join(RELEASES.split("/")[3:5]))
API = os.environ.get("FOREMAN_API", "https://api.github.com").rstrip("/")
UPDATE_DIR = os.environ.get("FOREMAN_UPDATE_DIR", "/workspace/foreman-updates")
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def parse_tag(tag):
    m = TAG_RE.match(tag or "")
    return tuple(int(x) for x in m.groups()) if m else None


def pinned_version():
    with open(os.path.join(HERE, "standalone.json"), encoding="utf-8") as f:
        return json.load(f)["version"]


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "foreman-update-check",
                                               "Accept": "application/vnd.github+json"})
    # anonymous on purpose: no token is ever sent
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if binary else json.loads(data.decode("utf-8"))


def state_path():
    return os.path.join(UPDATE_DIR, "update_check.json")


def load_state():
    try:
        with open(state_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(s):
    os.makedirs(UPDATE_DIR, exist_ok=True)
    tmp = state_path() + ".%d.tmp" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, state_path())


def newest_release():
    """Newest published, non-draft, non-prerelease release with a vX.Y.Z tag."""
    rels = get(f"{API}/repos/{REPO}/releases?per_page=30")
    best = None
    for r in rels:
        v = parse_tag(r.get("tag_name"))
        if not v or r.get("draft") or r.get("prerelease"):
            continue
        if best is None or v > parse_tag(best["tag_name"]):
            best = r
    return best


def cmd_check(force=False, today=None):
    today = today or datetime.now(timezone.utc).date().isoformat()
    current = pinned_version()
    st = load_state()
    if not force and st.get("checked_on") == today:
        if st.get("newer"):
            print(f"Already checked today. {st['newer']} is available (this package is {current}). "
                  "It was already shown to the owner; ask again only if they bring it up.")
        else:
            print(f"Already checked today. Foreman {current} is the newest release.")
        return 0
    try:
        rel = newest_release()
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"FLAGGED: could not reach GitHub to check for a Foreman update ({e.__class__.__name__}). "
              "Nothing was changed. It tries again tomorrow.")
        return 0
    st = {"checked_on": today, "current": current, "newer": None}
    if rel and parse_tag(rel["tag_name"]) > parse_tag(current):
        tag = rel["tag_name"]
        st["newer"] = tag
        save_state(st)
        notes = (rel.get("body") or "(no release notes)").strip()
        print(f"UPDATE AVAILABLE: Foreman {tag} (this package is {current}).")
        print(f"Release page: {rel.get('html_url', '')}")
        print("Release notes:")
        print(notes)
        print()
        print(f'ASK THE OWNER: "Foreman {tag} is out. Here is what changed (above). '
              f'Do you want me to download and check it? Nothing changes unless you say yes."')
        print("Do not download, install or change anything until the owner says yes to this exact version.")
        return 0
    save_state(st)
    print(f"No update. Foreman {current} is the newest release.")
    return 0


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_fetch(tag, yes=False):
    if not yes:
        print("STOP. fetch needs --yes, given only after the owner said yes to this exact version. "
              "Nothing was downloaded.", file=sys.stderr)
        return 2
    if not parse_tag(tag):
        print("STOP. Use a release tag like v1.0.2, never a branch. Nothing was downloaded.", file=sys.stderr)
        return 2
    base = os.environ.get("FOREMAN_BASE", f"https://github.com/{REPO}/releases/download/{tag}")
    dest = os.path.join(UPDATE_DIR, tag)
    os.makedirs(dest, exist_ok=True)
    zname = f"foreman-{tag}.zip"
    zpath, spath = os.path.join(dest, zname), os.path.join(dest, "SHA256SUMS")
    with open(spath, "wb") as f:
        f.write(get(f"{base}/SHA256SUMS", binary=True))
    with open(zpath, "wb") as f:
        f.write(get(f"{base}/{zname}", binary=True))
    want = None
    for line in open(spath, encoding="utf-8", errors="replace"):
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == zname:
            want = parts[0].lower()
    got = sha256(zpath)
    if not want or want != got:
        os.remove(zpath)
        print(f"STOP. The checksum for {zname} does not match SHA256SUMS"
              f"{' (no line for it)' if not want else ''}. The download was deleted. Do not install it.",
              file=sys.stderr)
        return 1
    print(f"Foreman {tag} downloaded and checked against SHA256SUMS: OK.")
    print(f"Checked zip: {zpath}")
    print(f"Next, with the owner's yes still standing: sh fetch_release.sh {tag} (add --bot <slug> for an individual template). It checks the zip again.")
    return 0


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if a[:1] == ["check"]:
        return cmd_check(force="--force" in a)
    if a[:1] == ["fetch"] and len(a) >= 2:
        return cmd_fetch(a[1], yes="--yes" in a)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
