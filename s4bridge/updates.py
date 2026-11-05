# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Is there a newer release? One anonymous request to GitHub's public API, at most once a day.

Nothing about the user or their setup is sent; the request carries only a generic User-Agent.
Turn it off in Settings.
"""
from __future__ import annotations

import json
import re
import time

REPO = "fancy-butler/s4bridge"          # the one place the GitHub owner/repo lives in code
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases"
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
