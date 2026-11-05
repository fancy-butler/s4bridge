# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Wires device <-> translator <-> MIDI.  Usable with or without the GUI."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .engine.profile import CONFIG_DIR, PROFILE_DIR, load_profile, load_settings, save_profile, save_settings
from .engine.translator import Translator
from .hw import alsa
from .hw.controls import HardwareMap, all_led_names
from .hw.device import BaseDevice, CaiaqDevice, SimDevice

HW_OVERRIDES = CONFIG_DIR / "hardware.json"


class NullMidi:
    address = "—"

    def __init__(self, reason: str):
        self.reason = reason

    def send(self, *a):
        pass

    def close(self):
        pass


class Core:
    def __init__(self, demo: bool = False, profile_path: Optional[str] = None):
        self.settings = load_settings()
        self.demo = demo
        self.status = ("starting", "")
        self.status_listeners: list[Callable[[str, str], None]] = []
        overrides = {}
        try:
            overrides = {k: v for k, v in json.loads(HW_OVERRIDES.read_text()).items()}
        except (OSError, ValueError):
            pass
        self.hw = HardwareMap(overrides)
        self.profile_path = profile_path or self.settings.get("profile")
        try:
            self.profile = load_profile(self.profile_path)
        except (OSError, ValueError):
            self.profile_path = None
            self.profile = load_profile()

        self.midi_error = ""
        self.midi = self._open_midi()
        self.device: BaseDevice = SimDevice() if demo else CaiaqDevice(grab=self.settings.get("grab", True))
        self.translator = Translator(self.hw, self.profile, self.device, self.midi.send)
        self.device.brightness = float(self.settings.get("led_brightness", 100)) / 100
        self.set_ticks_per_rev(int(self.settings.get("jog_ticks_per_rev", 1000)))   # measured on a real S4 MK1
        self.device.on_event = self.translator.handle_event
        self.device.on_status = self._on_status
        if hasattr(self.midi, "on_message"):
            self.midi.on_message = self.translator.handle_midi
        self._anim_stop = threading.Event()

    def _open_midi(self):
        if not alsa.seq_available():
            self.midi_error = "ALSA sequencer (/dev/snd/seq) not available"
            return NullMidi(self.midi_error)
        try:
            return alsa.VirtualMidi()
        except Exception as e:  # noqa: BLE001
            self.midi_error = str(e)
            return NullMidi(str(e))

    # ------------------------------------------------------------ lifecycle
    def start(self):
        self.device.start()
        self.sync_mixxx()
        threading.Thread(target=self._idle_loop, name="s4bridge-idle", daemon=True).start()

    def set_brightness(self, pct: int):
        self.settings["led_brightness"] = int(pct)
        self.device.brightness = max(0.1, min(1.0, pct / 100))
        if hasattr(self.device, "apply_brightness"):
            self.device.apply_brightness()

    # ------------------------------------------------------------ idle light show
    def _idle_loop(self):
        """After a stretch of no knob-turning and no DJ software activity, slowly
        breathe the VU meters. Any touch or any MIDI from the software ends it."""
        import math
        from .hw.controls import INDICATORS
        meters = [i for i in INDICATORS if i.func == "meter"]
        showing = False
        t0 = 0.0
        while not self._anim_stop.is_set():
            minutes = float(self.settings.get("idle_minutes", 10))
            idle_for = time.time() - self.translator.last_activity
            want = (self.settings.get("idle_show", False) and self.device.connected
                    and idle_for > minutes * 60)
            if want and not showing:
                showing, t0 = True, time.time()
            elif showing and not want:
                showing = False
                self.translator.refresh_all()
            if showing:
                t = time.time() - t0
                for n, ind in enumerate(meters):
                    level = 0.5 + 0.5 * math.sin(t * 0.9 - n * 0.9)
                    lit = round(level * 6)
                    for i, name in enumerate(ind.leds[:6]):
                        self.device.set_led(name, 10 if i < lit else 0)
                self._anim_stop.wait(0.12)
            else:
                self._anim_stop.wait(1.0)
        if self.demo:
            from .demo import DemoHost
            self.demo_host = DemoHost(self)

    def stop(self):
        self._anim_stop.set()
        try:
            if self.device.connected:
                self.translator.all_off()
        except Exception:
            pass
        self.device.stop()
        self.midi.close()

    def _on_status(self, state: str, detail: str):
        self.status = (state, detail)
        if state == "connected":
            threading.Thread(target=self._welcome, daemon=True).start()
        for cb in list(self.status_listeners):
            cb(state, detail)

    def _welcome(self):
        if self.settings.get("boot_animation", True):
            self.translator.boot_animation(all_led_names(), self._anim_stop)
        else:
            self.translator.refresh_all()

    def test_leds(self):
        threading.Thread(target=self.translator.boot_animation, args=(all_led_names(), self._anim_stop),
                         daemon=True).start()

    # ------------------------------------------------------------ profile
    def set_profile(self, prof: dict, path: Optional[str] = None):
        self.profile = prof
        self.profile_path = path
        self.translator.set_profile(prof)
        self.settings["profile"] = path
        save_settings(self.settings)
        self.translator.refresh_all()
        self.sync_mixxx()

    def save_profile(self, path: Optional[str] = None) -> str:
        if path is None:
            path = self.profile_path or str(PROFILE_DIR / "my-profile.json")
        save_profile(self.profile, path)
        self.sync_mixxx()
        self.profile_path = path
        self.settings["profile"] = path
        save_settings(self.settings)
        return path

    def profile_changed(self):
        self.translator.set_profile(self.profile)

    def sync_mixxx(self) -> str:
        """Silently keep a previously set-up Mixxx mapping current."""
        try:
            from .mixxx import sync_mapping_if_installed
            return sync_mapping_if_installed(self.profile)
        except Exception:  # never let this get in the way
            return "error"

    # ------------------------------------------------------------ hardware map
    def assign_code(self, cid: str, code: int):
        self.hw.assign(cid, code)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HW_OVERRIDES.write_text(json.dumps(self.hw.overrides, indent=2))

    def reset_hardware_overrides(self):
        self.hw.overrides.clear()
        self.hw.rebuild()
        try:
            HW_OVERRIDES.unlink()
        except OSError:
            pass

    def set_ticks_per_rev(self, tpr: int):
        tpr = max(32, int(tpr))
        self.settings["jog_ticks_per_rev"] = tpr
        self.translator.jog_norm = 1024.0 / tpr

    def save_settings(self):
        save_settings(self.settings)
