# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""The translation engine: S4 events -> MIDI, MIDI -> S4 LEDs.

Runs on the device/MIDI threads (not the GUI thread) so a busy UI can never
add latency to the jog wheels.  The GUI just subscribes to ``listeners``.
"""
from __future__ import annotations

import math
import threading
import time
from typing import Callable, Optional

from ..hw.controls import (BUTTON, ENC_RANGE, ENCODER, IND_BY_ID, INDICATORS, JOG, JOG_RANGE, POT,
                           TOUCH, Control, HardwareMap)
from .profile import area_key

SIDE_DECKS = {"L": ("A", "C"), "R": ("B", "D")}
DECK_SIDE = {"A": "L", "C": "L", "B": "R", "D": "R"}
TOUCH_HYSTERESIS = 150

# 7-segment font, segments A..G (A top, then clockwise, G middle)
SEGMENTS = {
    "0": "ABCDEF", "1": "BC", "2": "ABDEG", "3": "ABCDG", "4": "BCFG", "5": "ACDFG",
    "6": "ACDEFG", "7": "ABC", "8": "ABCDEFG", "9": "ABCDFG", "-": "G", " ": "",
    "A": "ABCEFG", "C": "ADEF", "E": "ADEFG", "F": "AEFG", "H": "BCEFG", "L": "DEF",
    "P": "ABEFG", "U": "BCDEF", "b": "CDEFG", "d": "BCDEG", "o": "CDEG", "n": "CEG", "r": "EG",
    "t": "DEFG", "S": "ACDFG", "y": "BCDFG",
}
# display CC values above 101 spell short words (mode names for the deck display)
DISPLAY_WORDS = {101: "--", 102: "LP", 103: "tL", 104: "CA", 105: "SA", 106: "St", 107: "rL", 108: "FL"}

Midi = tuple[int, int, int]


def led_level(vel: int, lo: int = 3) -> int:
    """MIDI velocity 0..127 -> caiaq brightness 0..31."""
    if vel <= 0:
        return 0
    return max(lo, min(31, round(vel * 31 / 127)))


class Translator:
    def __init__(self, hwmap: HardwareMap, profile: dict, device, send: Callable[[int, int, int], None]):
        self.hw = hwmap
        self.device = device
        self._pot_last: dict[int, int] = {}
        self.send_raw = send
        self.lock = threading.RLock()
        self.listeners: list[Callable[[dict], None]] = []
        self.active = {"L": "A", "R": "B"}
        self.shift = {"L": False, "R": False}
        self._last_out: dict = {}
        self._prev: dict[int, int] = {}
        self._jog_frac: dict[str, float] = {"L": 0.0, "R": 0.0}
        self._touch: dict[str, bool] = {"L": False, "R": False}
        self.raw: dict[int, int] = {}            # latest raw value per code (for UI/calibration)
        self.jog_ticks: dict[str, int] = {"L": 0, "R": 0}
        # measured ticks per platter turn -> normalised to 1024 per turn, so
        # DJ software sees the same resolution on every S4
        self.jog_norm = 1.0
        # LED caches: deck-side LEDs are cached per deck so flipping A<->C
        # restores what the software last told us about that deck.
        self.deck_led: dict[str, dict[str, int]] = {d: {} for d in "ABCD"}
        # soft takeover (tempo faders): the software's tempo per deck, and whether
        # a side's fader is waiting to catch it after a deck flip
        self.tempo_fb: dict[str, Optional[int]] = {d: None for d in "ABCD"}
        self.takeover: dict[str, bool] = {"L": False, "R": False}
        self._tk_prev: dict[str, Optional[int]] = {"L": None, "R": None}
        self.last_activity = time.time()
        self.set_profile(profile)

    # ------------------------------------------------------------ profile
    def set_profile(self, profile: dict):
        with self.lock:
            self.p = profile
            self._last_out.clear()
            self._build_reverse()

    def _build_reverse(self):
        """(status_kind, channel, number) -> list of targets for LED feedback."""
        p = self.p
        rev: dict[tuple, list] = {}

        def add(kind, ch, num, target):
            rev.setdefault((kind, ch, num), []).append(target)

        dch = p["deck_channels"]
        for key, m in list(p["map"].items()) + list(p["leds"].items()):
            kind = 0x90 if m["type"] == "note" else 0xB0
            scope, func = key.split(".", 1)
            if scope == "deck":
                for deck in "ABCD":
                    add(kind, dch[deck], m["num"], ("deck", deck, func))
            elif scope == "strip":
                for deck in "ABCD":
                    add(kind, dch[deck], m["num"], ("strip", deck, func))
            else:
                add(kind, p["global_channel"], m["num"], (scope, None, func))
        self._rev = rev

    # ------------------------------------------------------------ helpers
    def _emit(self, ev: dict):
        for cb in list(self.listeners):
            try:
                cb(ev)
            except Exception:
                pass

    def _channel(self, c: Control) -> int:
        if c.area in ("L", "R"):
            return self.p["deck_channels"][self.active[c.area]]
        if c.area in "ABCD":
            return self.p["deck_channels"][c.area]
        return self.p["global_channel"]

    def _shifted(self, c: Control) -> bool:
        if c.area in ("L", "R"):
            return self.shift[c.area]
        return self.shift["L"] or self.shift["R"]

    def _send(self, status: int, d1: int, d2: int, c: Optional[Control] = None, dedup=None):
        if dedup is not None:
            if self._last_out.get(dedup) == (status, d1, d2):
                return
            self._last_out[dedup] = (status, d1, d2)
        self.send_raw(status, d1, d2)
        self._emit({"t": "out", "msg": (status, d1, d2), "cid": c.cid if c else None, "time": time.time()})

    def _rel(self, delta: int) -> int:
        delta = max(-63, min(63, delta))
        if self.p.get("relative_encoding") == "twos":
            return delta & 0x7F
        return 64 + delta

    # ------------------------------------------------------------ input
    def handle_event(self, code: int, value: int):
        with self.lock:
            self.last_activity = time.time()
            self.raw[code] = value
            c = self.hw.lookup(code)
            if c is None:
                self._emit({"t": "unknown", "code": code, "value": value})
                return
            if c.kind == POT and not self._pot_moved(code, value):
                return   # electrical noise, not a hand on the knob
            self._emit({"t": "in", "cid": c.cid, "code": code, "value": value})
            m = self.p["map"].get(area_key(c.area, c.func))
            if c.kind == BUTTON:
                self._button(c, m, value != 0)
            elif c.kind == POT:
                self._pot(c, m, value)
            elif c.kind == ENCODER:
                self._encoder(c, m, code, value)
            elif c.kind == JOG:
                self._jog(c, m, code, value)
            elif c.kind == TOUCH:
                self._touch_sensor(c, m, value)

    POT_DEADBAND = 4   # of 4096 steps: the S4's pots wobble a count or two when LEDs or audio load the supply

    def _pot_moved(self, code: int, v: int) -> bool:
        last = self._pot_last.get(code)
        if last is None or abs(v - last) >= self.POT_DEADBAND or (v != last and v in (0, 0xFFF)):
            self._pot_last[code] = v
            return True
        return False

    def _num(self, c: Control, m: dict) -> int:
        n = m["num"]
        if m.get("shiftable", True) and self._shifted(c):
            n += self.p["global_shift_offset"] if c.area in ("G", "FX1", "FX2") else self.p["deck_shift_offset"]
        return n & 0x7F

    def _button(self, c: Control, m: Optional[dict], pressed: bool):
        if c.func == "deck_toggle":
            if pressed:
                self.toggle_deck(c.area)
            # still tell the software, on the deck we just switched to
        if c.func == "shift":
            self.shift[c.area] = pressed
            self._set_leds(c.led, 31 if pressed else 0)
        if m is None:
            return
        ch = self._channel(c)
        num = self._num(c, m)
        if m["type"] == "note":
            self._send((0x90 if pressed else 0x80) | ch, num, 127 if pressed else 0, c)
        else:
            self._send(0xB0 | ch, num, 127 if pressed else 0, c)
        if self.p.get("local_press_feedback") and c.func not in ("shift", "deck_toggle"):
            self._set_leds(c.led[:1], 31 if pressed else self._cached_level(c))

    def _pot(self, c: Control, m: Optional[dict], v: int):
        if m is None:
            return
        if m.get("invert"):
            v = 0xFFF - v
        if c.func == "tempo" and self.takeover.get(c.area) and not self._takeover_check(c.area, v >> 5):
            return   # still catching up with the deck's tempo
        ch = self._channel(c)
        num = m["num"]
        if m["type"] == "note":
            return
        if m.get("hires"):
            v14 = v << 2
            msb, lsb = v14 >> 7, v14 & 0x7F
            key = ("pot14", ch, num)
            if self._last_out.get(key) == (msb, lsb):
                return
            self._last_out[key] = (msb, lsb)
            self._send(0xB0 | ch, num, msb, c)
            self._send(0xB0 | ch, (num + 0x20) & 0x7F, lsb, c)
        else:
            self._send(0xB0 | ch, num, v >> 5, c, dedup=("pot", ch, num))

    def _wrap_delta(self, code: int, value: int, rng: int) -> int:
        prev = self._prev.get(code)
        self._prev[code] = value
        if prev is None:
            return 0
        d = (value - prev) % rng
        if d > rng // 2:
            d -= rng
        return d

    def _encoder(self, c: Control, m, code, value):
        d = self._wrap_delta(code, value, ENC_RANGE)
        if d == 0 or m is None:
            return
        self._send(0xB0 | self._channel(c), self._num(c, m), self._rel(d), c)

    def _jog(self, c: Control, m, code, value):
        d = self._wrap_delta(code, value, JOG_RANGE)
        if d == 0:
            return
        self.jog_ticks[c.area] += d
        if m is None:
            return
        self._jog_frac[c.area] += d * self.jog_norm * float(self.p.get("jog_scale", 1.0))
        out = int(self._jog_frac[c.area])
        if out == 0:
            return
        self._jog_frac[c.area] -= out
        ch, num = self._channel(c), self._num(c, m)
        while out:
            step = max(-63, min(63, out))
            self._send(0xB0 | ch, num, self._rel(step), c)
            out -= step

    def _touch_sensor(self, c: Control, m, v):
        th = int(self.p.get("touch_threshold", 3050))
        was = self._touch[c.area]
        now = v >= th if not was else v >= th - TOUCH_HYSTERESIS
        if now == was:
            return
        self._touch[c.area] = now
        self._emit({"t": "touch", "side": c.area, "on": now})
        if m is not None:
            self._send((0x90 if now else 0x80) | self._channel(c), self._num(c, m), 127 if now else 0, c)

    # ------------------------------------------------------------ decks
    def toggle_deck(self, side: str):
        with self.lock:
            a, b = SIDE_DECKS[side]
            self.active[side] = b if self.active[side] == a else a
            # forget pickup positions so the new deck's pots resend on first move
            self._last_out = {k: v for k, v in self._last_out.items() if not (isinstance(k, tuple) and k[0].startswith("pot"))}
            self.refresh_side(side)
            self._arm_takeover(side)
            self._emit({"t": "deck", "side": side, "deck": self.active[side]})

    # ------------------------------------------------------------ soft takeover
    def _fader7(self, side: str) -> Optional[int]:
        c = self.hw.controls.get(f"{side}.tempo")
        if c is None or c.code is None or c.code not in self.raw:
            return None
        v = self.raw[c.code]
        m = self.p["map"].get("deck.tempo") or {}
        if m.get("invert"):
            v = 0xFFF - v
        return v >> 5

    def _arm_takeover(self, side: str):
        fb, pos = self.tempo_fb[self.active[side]], self._fader7(side)
        if not self.p.get("soft_takeover", True) or fb is None or pos is None or abs(pos - fb) <= 2:
            self._release_takeover(side)
            return
        self.takeover[side] = True
        self._tk_prev[side] = pos - fb
        self._takeover_leds(side, fb - pos)

    def _takeover_check(self, side: str, pos: int) -> bool:
        """True once the fader has caught the deck's tempo."""
        fb = self.tempo_fb[self.active[side]]
        if fb is None:
            self._release_takeover(side)
            return True
        diff = pos - fb
        prev = self._tk_prev[side]
        self._tk_prev[side] = diff
        if abs(diff) <= 2 or (prev is not None and (prev < 0) != (diff < 0)):
            self._release_takeover(side)
            return True
        self._takeover_leds(side, -diff)
        return False

    def _release_takeover(self, side: str):
        was = self.takeover[side]
        self.takeover[side] = False
        self._tk_prev[side] = None
        if was:
            self._takeover_leds(side, 0)

    def _takeover_leds(self, side: str, need: int):
        """Light OFFSET up/down to show which way to push the fader (need > 0 = higher value)."""
        up = self.hw.controls[f"{side}.tempo_up"].led
        down = self.hw.controls[f"{side}.tempo_down"].led
        if need == 0:
            cache = self.deck_led[self.active[side]]
            self._set_leds(up, led_level(cache.get("tempo_up", 0)))
            self._set_leds(down, led_level(cache.get("tempo_down", 0)))
        else:
            inv = bool((self.p["map"].get("deck.tempo") or {}).get("invert"))
            raw_up = (need > 0) != inv          # moving the fader to a higher raw value
            self._set_leds(up, 31 if raw_up else 0)
            self._set_leds(down, 0 if raw_up else 31)
        self._emit({"t": "takeover", "side": side, "locked": self.takeover[side]})

    # ------------------------------------------------------------ LEDs
    def _set_leds(self, names, level: int):
        for n in names:
            self.device.set_led(n, level)

    def _cached_level(self, c: Control) -> int:
        if c.area in ("L", "R"):
            return led_level(self.deck_led[self.active[c.area]].get(c.func, 0))
        return 0

    def handle_midi(self, status: int, d1: int, d2: int):
        """MIDI from the DJ software -> LEDs."""
        if not self.p.get("led_feedback", True):
            return
        with self.lock:
            self.last_activity = time.time()
            kind, ch = status & 0xF0, status & 0x0F
            if kind == 0x80:
                kind, d2 = 0x90, 0
            targets = self._rev.get((kind, ch, d1), [])
            if targets and targets[0][2] == "rate_fb":
                deck = {v: k for k, v in self.p["deck_channels"].items()}.get(ch)
                if deck:
                    self.tempo_fb[deck] = d2
                    side = DECK_SIDE[deck]
                    if self.takeover[side] and self.active[side] == deck:
                        pos = self._fader7(side)
                        if pos is not None:
                            self._tk_prev[side] = None
                            self._takeover_check(side, pos)
                return
            self._emit({"t": "midi_in", "msg": (status, d1, d2), "time": time.time(),
                        "targets": [f"{d or s}.{f}" for s, d, f in targets if s != "deck" or d]})
            for scope, deck, func in targets:
                if scope == "deck":
                    self.deck_led[deck][func] = d2
                    side = DECK_SIDE[deck]
                    if self.active[side] == deck:
                        self._apply_deck_led(side, func, d2)
                elif scope == "strip":
                    self._apply_area_led(deck, func, d2)
                else:
                    self._apply_area_led(scope, func, d2)

    def _apply_deck_led(self, side: str, func: str, v: int):
        cid = f"{side}.{func}"
        if func.startswith("hotcue"):
            c = self.hw.controls.get(cid)
            blue, green = c.led
            # bands: 0 off, 1-42 blue, 43-85 green, 86-127 both
            self.device.set_led(blue, 31 if 0 < v <= 42 or v > 85 else 0)
            self.device.set_led(green, 31 if 42 < v else 0)
            return
        if func in ("display", "display_dot"):
            self._display(side)
            return
        if func in ("shift", "deck_toggle", "rate_fb"):
            return   # owned locally
        if func in ("tempo_up", "tempo_down") and self.takeover.get(side):
            return   # showing the takeover direction
        names = self._led_names(cid)
        self._set_leds(names, led_level(v))

    def _apply_area_led(self, area: str, func: str, v: int):
        cid = f"{area}.{func}"
        if func == "meter":
            ind = IND_BY_ID[cid]
            segs = 0 if v <= 0 else min(6, math.ceil(v * 6 / 126))
            for i, n in enumerate(ind.leds[:6]):
                self.device.set_led(n, 31 if i < segs else 0)
            self.device.set_led(ind.leds[6], 31 if v >= 127 else 0)
            return
        self._set_leds(self._led_names(cid), led_level(v))

    def _led_names(self, cid: str):
        c = self.hw.controls.get(cid)
        if c is not None:
            return c.led
        ind = IND_BY_ID.get(cid)
        return ind.leds if ind else ()

    def _display(self, side: str, v: Optional[int] = None):
        cache = self.deck_led[self.active[side]]
        if v is None:
            v = cache.get("display", 100)
        if v <= 99:
            text = f"{v:2d}"
        else:
            text = DISPLAY_WORDS.get(v, "  ")
        self.show_text(side, text, dot2=v <= 99 and cache.get("display_dot", 0) > 0)

    def show_text(self, side: str, text: str, dot2: bool = False):
        prefix = "LED: Deck A: " if side == "L" else "LED: Deck B: "
        text = (text + "  ")[:2]
        digits = (2, 1) if self.p.get("display_swap_digits") else (1, 2)
        for d, ch in zip(digits, text):
            lit = SEGMENTS.get(ch, "")
            for s in "ABCDEFG":
                self.device.set_led(f"{prefix}Digit {d} - {s}", 31 if s in lit else 0)
        self.device.set_led(f"{prefix}Digit {digits[0]} - dot", 0)
        self.device.set_led(f"{prefix}Digit {digits[1]} - dot", 31 if dot2 else 0)

    def refresh_side(self, side: str):
        deck = self.active[side]
        top, bottom = SIDE_DECKS[side]
        cache = self.deck_led[deck]
        for c in self.hw.controls.values():
            if c.area == side and c.led and c.func not in ("shift", "deck_toggle"):
                self._apply_deck_led(side, c.func, cache.get(c.func, 0))
        for ind in INDICATORS:
            if ind.area == side and ind.func not in ("ind_top", "ind_bottom"):
                self._apply_deck_led(side, ind.func, cache.get(ind.func, 0 if ind.func != "display" else 100))
        p = "LED: Deck A: " if side == "L" else "LED: Deck B: "
        self.device.set_led(f"{p}Deck {top}", 31 if deck == top else 0)
        self.device.set_led(f"{p}Deck {bottom}", 31 if deck == bottom else 0)
        tog = self.hw.controls[f"{side}.deck_toggle"].led
        self._set_leds(tog, 31 if deck == bottom else 4)
        self._set_leds(self.hw.controls[f"{side}.shift"].led, 31 if self.shift[side] else 4)

    def refresh_all(self):
        with self.lock:
            for side in ("L", "R"):
                self.refresh_side(side)
            for c in self.hw.controls.values():
                if c.area not in ("L", "R"):
                    for n in c.led:
                        self.device.set_led(n, self.device.led_state.get(n, 0))

    def all_off(self):
        for n in list(self.device.led_state) or []:
            self.device.set_led(n, 0)

    def boot_animation(self, names: list[str], stop: Optional[threading.Event] = None):
        """Quick left-to-right sweep so you can see the bridge took over."""
        by_x = sorted(
            [(c.x, c.led) for c in self.hw.controls.values() if c.led]
            + [(i.x, i.leds) for i in INDICATORS], key=lambda t: t[0])
        for x, leds in by_x:
            if stop and stop.is_set():
                break
            self._set_leds(leds, 31)
            time.sleep(0.006)
        time.sleep(0.12)
        for _, leds in by_x:
            self._set_leds(leds, 0)
        self.show_text("L", "S4")
        self.show_text("R", "br")
        time.sleep(0.6)
        self.refresh_all()
