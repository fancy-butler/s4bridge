# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Which apps are playing, and moving them onto the mixer's decks (via pactl,
which PipeWire's pulse server understands)."""
from __future__ import annotations

import re
import subprocess

DECK_SINK = {"A": "s4bridge_deck_a", "B": "s4bridge_deck_b"}
SINK_DECK = {v: k for k, v in DECK_SINK.items()}


def _pactl(*args) -> str:
    try:
        return subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def parse_sinks(short: str) -> dict[str, str]:
    """`pactl list short sinks` -> {index: name}"""
    out = {}
    for line in short.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out[parts[0].strip()] = parts[1].strip()
    return out


def parse_streams(text: str, sinks: dict[str, str]) -> list[dict]:
    """`pactl list sink-inputs` -> [{id, app, title, sink, deck}]"""
    streams = []
    for chunk in re.split(r"^Sink Input #", text, flags=re.M)[1:]:
        sid = chunk.split("\n", 1)[0].strip()
        sink = re.search(r"^\s*Sink:\s*(\S+)", chunk, re.M)
        sink_name = sinks.get(sink.group(1), sink.group(1)) if sink else ""

        def prop(key):
            m = re.search(rf'^\s*{re.escape(key)}\s*=\s*"(.*)"\s*$', chunk, re.M)
            return m.group(1) if m else ""

        app = prop("application.name") or prop("application.process.binary") or "Unknown app"
        title = prop("media.name")
        if prop("application.process.binary") in ("pw-cat", "pw-play") and not title:
            continue
        streams.append({"id": sid, "app": app, "title": title if title != app else "",
                        "sink": sink_name, "deck": SINK_DECK.get(sink_name, "")})
    return streams


def list_streams() -> list[dict]:
    sinks = parse_sinks(_pactl("list", "short", "sinks"))
    return parse_streams(_pactl("list", "sink-inputs"), sinks)


def default_sink() -> str:
    name = _pactl("get-default-sink").strip()
    return "" if name in SINK_DECK else name


def send(stream_id: str, deck: str):
    """deck = "A" / "B" / "" (back to the normal output)."""
    target = DECK_SINK.get(deck) or default_sink()
    if target:
        _pactl("move-sink-input", stream_id, target)
