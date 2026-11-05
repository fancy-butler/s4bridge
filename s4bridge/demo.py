# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""A pretend DJ app for demo mode, so the LEDs react without real software."""
from __future__ import annotations

import math
import random
import threading
import time

TOGGLES = {0x0A, 0x08, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x3E, 0x3F, 0x44}
GLOBAL_TOGGLES = {0x07, 0x08, 0x0B, 0x0C, 0x0D, 0x18, 0x19, 0x1A, 0x1B, 0x22, 0x23, 0x24, 0x25}


class DemoHost:
    def __init__(self, core):
        self.core = core
        self.t = core.translator
        self.state: dict = {}
        self.volume = {d: 0.0 for d in "ABCD"}
        self.loop = {d: 4 for d in "ABCD"}
        self.hot = {}
        self._stop = threading.Event()
        self.t.listeners.append(self._on)
        threading.Thread(target=self._meters, daemon=True).start()

    def _reply(self, st, d1, d2):
        self.t.handle_midi(st, d1, d2)

    def _on(self, ev):
        if ev["t"] != "out":
            return
        st, d1, d2 = ev["msg"]
        kind, ch = st & 0xF0, st & 0x0F
        p = self.core.profile
        deck = {v: k for k, v in p["deck_channels"].items()}.get(ch)
        if kind == 0x90 and d2:
            g = ch == p["global_channel"]
            if (g and d1 in GLOBAL_TOGGLES) or (not g and d1 in TOGGLES):
                key = (ch, d1)
                self.state[key] = not self.state.get(key, False)
                vel = 127 if self.state[key] else 0
                if not g and 0x0B <= d1 <= 0x0E and self.state[key]:
                    vel = random.choice((30, 70, 110))
                threading.Thread(target=self._reply, args=(0x90 | ch, d1, vel), daemon=True).start()
            if not g and d1 == 0x09:  # cue flashes while held
                self._reply(0x90 | ch, 0x09, 127)
        elif kind == 0x80 and deck and d1 == 0x09:
            self._reply(0x90 | ch, 0x09, 0)
        elif kind == 0xB0 and deck:
            if d1 == 0x45:
                self.volume[deck] = d2 / 127
            elif d1 in (0x15, 0x35):
                step = 1 if d2 > 64 else -1
                self.loop[deck] = max(1, min(64, self.loop[deck] * (2 if step > 0 else 0.5)))
                self._reply(0xB0 | ch, 0x50, int(self.loop[deck]))

    def _meters(self):
        p = self.core.profile
        t0 = time.time()
        for d in "ABCD":
            self._reply(0xB0 | p["deck_channels"][d], 0x50, 4)
        self._reply(0x90 | p["deck_channels"]["A"], 0x60, 127)   # on air
        while not self._stop.is_set():
            now = time.time() - t0
            for i, d in enumerate("ABCD"):
                ch = p["deck_channels"][d]
                playing = self.state.get((ch, 0x0A), False)
                lvl = 0
                if playing:
                    beat = 0.55 + 0.45 * abs(math.sin(now * 4.2 + i))
                    lvl = int(min(127, 126 * self.volume[d] * beat + random.random() * 10))
                self.t.handle_midi(0xB0 | ch, 0x46, lvl)
            time.sleep(0.05)

    def stop(self):
        self._stop.set()
