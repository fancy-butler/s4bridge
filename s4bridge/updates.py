# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Is there a newer version, and installing it.

Checking: once a day, one anonymous request for the version number in the code on GitHub's main
branch. Nothing about the user or their setup is sent; the request carries only a generic User-Agent.
Turn it off in Settings.

Installing (Arch-based systems, where S4 Bridge was installed as a pacman package): download the main
branch, build the package as the user, install it with one polkit password prompt, restart.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time

REPO = "fancy-butler/s4bridge"          # the one place the GitHub owner/repo lives in code
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases"
VERSION_URL = f"https://raw.githubusercontent.com/{REPO}/main/s4bridge/__init__.py"
TARBALL_URL = f"https://github.com/{REPO}/archive/refs/heads/main.tar.gz"
CHANGELOG_URL = f"https://github.com/{REPO}/blob/main/CHANGELOG.md"
ISSUES_URL = f"https://github.com/{REPO}/issues/new"
USER_AGENT = "S4-Bridge-update-check"
INTERVAL = 24 * 3600


def parse_version(v: str) -> tuple[int, ...]:
    m = re.match(r"v?(\d+(?:\.\d+)*)", (v or "").strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    n = max(len(a), len(b))
    return bool(a) and a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def due(settings: dict, now: float | None = None) -> bool:
    if not settings.get("check_updates", True):
        return False
    return (now or time.time()) - float(settings.get("update_checked_at", 0)) >= INTERVAL


def parse_release(body: bytes) -> tuple[str, str] | None:
    """(version, url) from the releases/latest JSON, skipping drafts and pre-releases."""
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name") or ""
    if not parse_version(tag):
        return None
    return tag.lstrip("v"), data.get("html_url") or RELEASES_URL


def parse_version_file(text: str) -> str | None:
    """The __version__ out of s4bridge/__init__.py as served raw from GitHub."""
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text or "", re.M)
    return m.group(1) if m and parse_version(m.group(1)) else None


# ------------------------------------------------------------------ one-click install
def _pacman_owns_us() -> bool:
    if not (shutil.which("pacman") and shutil.which("makepkg") and shutil.which("pkexec")
            and shutil.which("curl")):
        return False
    here = os.path.realpath(os.path.join(os.path.dirname(__file__), "__init__.py"))
    try:
        r = subprocess.run(["pacman", "-Qqo", here], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip() == "s4bridge"


def can_self_update() -> bool:
    """True when "Update now" can do the whole job (Arch-family install from our PKGBUILD)."""
    return sys.platform.startswith("linux") and _pacman_owns_us()


def update_script() -> str:
    """Shell run as the user. Prints STEP: lines for the progress dialog. Only pacman runs as root."""
    return f"""set -e
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cd "$work"
echo "STEP: Downloading"
curl -fsSL "{TARBALL_URL}" -o src.tar.gz
tar xzf src.tar.gz
cd s4bridge-main/packaging/arch
echo "STEP: Building"
makepkg -f --nodeps --noconfirm
pkg=$(ls -1 s4bridge-*.pkg.tar.* | head -n 1)
echo "STEP: Installing"
pkexec pacman -U --noconfirm "$PWD/$pkg"
echo "STEP: Done"
"""


def relaunch_command() -> list[str]:
    exe = shutil.which("s4bridge")
    return ["/bin/sh", "-c", f"sleep 2; exec {exe or sys.executable + ' -m s4bridge.app'}"]
