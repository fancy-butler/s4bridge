# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Runs the standalone mixer engine and connects it to the S4: knobs and faders in,
VU meters and CUE lights out."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import threading
from typing import Callable, Optional

from ..hw.controls import ENC_RANGE, IND_BY_ID

STRIPS = "ABCD"
XF_SIDE = {"A": "L", "C": "L", "B": "R", "D": "R"}
METER_DB = (-30, -20, -12, -6, -3, -0.5)      # thresholds for the six meter segments


def deps_missing() -> str:
    for mod, pkg in (("numpy", "python-numpy"), ("scipy", "python-scipy"), ("jack", "python-jack-client")):
        try:
            __import__(mod)
        except Exception:  # noqa: BLE001  (jack raises OSError when libjack is missing)
            return pkg if mod != "jack" else "python-jack-client and pipewire-jack"
    return ""


class MixerController:
    def __init__(self, core):
        self.core = core
        self.proc: Optional[subprocess.Popen] = None
        self.status: dict = {"state": "off"}
        self.meters: dict = {}
        self.clip = False
        self.listeners: list[Callable[[dict], None]] = []
        self.cue = {s: False for s in STRIPS}
        self.gain_db = {s: 0.0 for s in STRIPS}
        self._prev_enc: dict[int, int] = {}
        self._wlock = threading.Lock()

    # ------------------------------------------------------------ lifecycle
    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _emit(self, ev: dict):
        for cb in list(self.listeners):
            try:
                cb(ev)
            except Exception:
                pass

    def start(self):
        if self.running:
            return
        missing = deps_missing()
        if missing:
            self.status = {"state": "error", "error": f"Install {missing} to use the standalone mixer."}
            self._emit({"t": "mixer_status", **self.status})
            return
        env = dict(os.environ)
        env.setdefault("PIPEWIRE_LATENCY", "256/48000")
        self.proc = subprocess.Popen([sys.executable, "-m", "s4bridge.mixer.engine"], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
                                     env=env)
        self.status = {"state": "starting"}
        self._emit({"t": "mixer_status", **self.status})
        threading.Thread(target=self._reader, name="s4bridge-mixer-out", daemon=True).start()
        self.core.translator.listeners.append(self._on_event)
        self._push_all()
        self._strip_leds()

    def stop(self):
        if self.core.translator.listeners.count(self._on_event):
            self.core.translator.listeners.remove(self._on_event)
        if self.proc:
            try:
                self._send({"quit": 1})
                self.proc.wait(timeout=3)
            except Exception:  # noqa: BLE001
                self.proc.kill()
            self.proc = None
        self.status = {"state": "off"}
        self.meters = {}
        self._emit({"t": "mixer_status", **self.status})
        self._clear_leds()
        self.core.translator.refresh_all()

    def set_source(self, strip: str, name: str):
        self._send({"sources": {strip: name}})
        self.core.settings.setdefault("mixer_sources", {})[strip] = name
        self.core.save_settings()

    # ------------------------------------------------------------ engine I/O
    def _send(self, msg: dict):
        if not self.running:
            return
        with self._wlock:
            try:
                self.proc.stdin.write(json.dumps(msg) + "\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, ValueError):
                pass

    def _reader(self):
        proc = self.proc
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if "m" in msg:
                self.meters = msg["m"]
                self.clip = msg.get("clip", False)
                self._meter_leds()
                self._emit({"t": "mixer_meters", "m": self.meters, "clip": self.clip, "xruns": msg.get("xruns", 0)})
            elif "status" in msg:
                self.status = {"state": msg["status"], **{k: v for k, v in msg.items() if k != "status"}}
                if msg["status"] == "running":
                    saved = self.core.settings.get("mixer_sources") or {}
                    want = {s: n for s, n in saved.items() if n in msg.get("available", [])
                            and msg.get("sources", {}).get(s) != n}
                    if want:
                        self._send({"sources": want})
                    self._strip_leds()
                self._emit({"t": "mixer_status", **self.status})
            elif "available" in msg:
                self.status.update(msg)
                self._emit({"t": "mixer_status", **self.status})
        if self.status.get("state") != "error" and self.proc is proc:
            self.status = {"state": "error", "error": "The mixer engine stopped unexpectedly."}
            self._emit({"t": "mixer_status", **self.status})

    # ------------------------------------------------------------ controls in
    def _raw(self, cid: str, default: float) -> float:
        c = self.core.hw.controls.get(cid)
        if c is None or c.code is None or c.code not in self.core.translator.raw:
            return default
        return self.core.translator.raw[c.code] / 4095

    def _push_all(self):
        for s in STRIPS:
            self._send({"strip": s, "gain_db": self.gain_db[s], "cue": self.cue[s],
                        "hi": self._raw(f"{s}.hi", 0.5), "mid": self._raw(f"{s}.mid", 0.5),
                        "low": self._raw(f"{s}.low", 0.5), "filter": self._raw(f"{s}.filter", 0.5),
                        "volume": self._raw(f"{s}.volume", 0.75)})
        self._send({"xfader": self._raw("G.crossfader", 0.5), "cue_mix": self._raw("G.cue_mix", 0.5)})

    def _on_event(self, ev: dict):
        if ev.get("t") != "in":
            return
        cid, code, v = ev["cid"], ev["code"], ev["value"]
        area, _, func = cid.partition(".")
        if area in STRIPS:
            if func in ("hi", "mid", "low", "filter", "volume"):
                self._send({"strip": area, func: v / 4095})
            elif func == "gain":
                prev = self._prev_enc.get(code)
                self._prev_enc[code] = v
                if prev is not None:
                    d = (v - prev) % ENC_RANGE
                    d = d - ENC_RANGE if d > ENC_RANGE // 2 else d
                    self.gain_db[area] = max(-24.0, min(12.0, self.gain_db[area] + d * 0.75))
                    self._send({"strip": area, "gain_db": self.gain_db[area]})
            elif func == "gain_press" and v:
                self.gain_db[area] = 0.0
                self._send({"strip": area, "gain_db": 0.0})
            elif func == "cue" and v:
                self.cue[area] = not self.cue[area]
                self._send({"strip": area, "cue": self.cue[area]})
                self._strip_leds()
        elif cid == "G.crossfader":
            self._send({"xfader": v / 4095})
        elif cid == "G.cue_mix":
            self._send({"cue_mix": v / 4095})

    # ------------------------------------------------------------ LEDs out
    def _set(self, names, level):
        for n in names:
            self.core.device.set_led(n, level)

    def _strip_leds(self):
        connected = (self.status.get("sources") or {})
        for s in STRIPS:
            p = f"LED: Channel {s}: "
            self._set([p + "Cue"], 31 if self.cue[s] else 3)
            self._set([p + "<"], 31 if XF_SIDE[s] == "L" else 0)
            self._set([p + ">"], 31 if XF_SIDE[s] == "R" else 0)
            self._set([p + "Active"], 31 if s in connected else 0)

    def _meter_leds(self):
        for s in STRIPS:
            peak = self.meters.get(s, 0.0)
            db = 20 * math.log10(peak) if peak > 1e-6 else -120
            leds = IND_BY_ID[f"{s}.meter"].leds
            for i, name in enumerate(leds[:6]):
                self.core.device.set_led(name, 31 if db >= METER_DB[i] else 0)
            self.core.device.set_led(leds[6], 31 if peak >= 0.999 else 0)
        self.core.device.set_led("LED: Master: Warning", 31 if self.clip else 0)

    def _clear_leds(self):
        for s in STRIPS:
            self._set(IND_BY_ID[f"{s}.meter"].leds, 0)
            p = f"LED: Channel {s}: "
            self._set([p + "Cue", p + "<", p + ">", p + "Active"], 0)
        self.core.device.set_led("LED: Master: Warning", 0)
