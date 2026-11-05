# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Device backends.

``CaiaqDevice`` talks to a real S4 MK1 through the kernel's snd-usb-caiaq
driver: controls arrive as evdev events, LEDs are ALSA control elements.
``SimDevice`` is a stand-in for demo mode and tests: the on-screen surface
injects events, and LED writes are just remembered.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from .controls import USB_PRODUCT, USB_VENDOR, all_led_names
from . import alsa

EventCb = Callable[[int, int], None]          # (code, value)
StatusCb = Callable[[str, str], None]          # (state, detail)

LED_MAX = 31   # snd-usb-caiaq reports 0..31 brightness for S4 LEDs


class BaseDevice:
    name = "device"

    def __init__(self):
        self.on_event: Optional[EventCb] = None
        self.on_status: Optional[StatusCb] = None
        self.connected = False
        self.led_state: dict[str, int] = {}
        self.brightness = 1.0       # 0.1 .. 1.0, applied to the hardware only

    def start(self): ...
    def stop(self): ...

    def set_led(self, name: str, value: int):
        self.led_state[name] = value

    def _status(self, state: str, detail: str = ""):
        self.connected = state == "connected"
        if self.on_status:
            self.on_status(state, detail)


class SimDevice(BaseDevice):
    name = "Simulated S4 (demo)"

    def start(self):
        self._status("connected", "Demo mode: drive the surface with your mouse")

    def inject(self, code: int, value: int):
        if self.on_event:
            self.on_event(code, value)


class CaiaqDevice(BaseDevice):
    name = "Traktor Kontrol S4 MK1"

    def __init__(self, grab: bool = True):
        super().__init__()
        self.grab = grab
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._leds: Optional[alsa.LedWriter] = None
        self.evdev_path = ""
        self.card_id = ""

    # -- discovery
    @staticmethod
    def find_evdev():
        import evdev
        for path in evdev.list_devices():
            try:
                d = evdev.InputDevice(path)
            except OSError:
                continue
            if d.info.vendor == USB_VENDOR and d.info.product == USB_PRODUCT:
                return d
            d.close()
        return None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="s4bridge-evdev", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._close_leds()

    def _close_leds(self):
        if self._leds:
            self._leds.close()
            self._leds = None

    def _hw_level(self, value: int) -> int:
        if value <= 0:
            return 0
        return max(1, min(LED_MAX, round(value * self.brightness)))

    def set_led(self, name: str, value: int):
        super().set_led(name, value)
        if self._leds:
            self._leds.set(name, self._hw_level(value))

    def apply_brightness(self):
        if self._leds:
            for n, v in list(self.led_state.items()):
                self._leds.set(n, self._hw_level(v))

    def _open_leds(self):
        self.card_id = alsa.find_card() or ""
        if not self.card_id:
            return "ALSA card for the S4 not found: LEDs disabled"
        try:
            self._leds = alsa.LedWriter(self.card_id)
        except alsa.AlsaError as e:
            return f"LEDs unavailable ({e})"
        # push the whole current state so LEDs match after a reconnect
        for n, v in self.led_state.items():
            self._leds.set(n, self._hw_level(v), force=True)
        return ""

    def _run(self):
        import evdev
        from evdev import ecodes
        waiting_reported = False
        while not self._stop.is_set():
            dev = None
            try:
                dev = self.find_evdev()
            except PermissionError:
                self._status("error", "No permission for /dev/input. Install the udev rule (see README).")
            if dev is None:
                if not waiting_reported:
                    self._status("waiting", "Plug in and power on the S4…")
                    waiting_reported = True
                self._stop.wait(1.5)
                continue
            waiting_reported = False
            self.evdev_path = dev.path
            warn = self._open_leds()
            if self.grab:
                try:
                    dev.grab()   # keep games/desktop from treating it as a joystick
                except OSError:
                    pass
            self._status("connected", warn or f"{dev.path} · ALSA card {self.card_id}")
            try:
                self._pump(dev, ecodes)
            except OSError:
                pass   # unplugged
            finally:
                try:
                    dev.close()
                except Exception:
                    pass
                self._close_leds()
            if not self._stop.is_set():
                self._status("waiting", "S4 disconnected. Waiting for it to come back…")
                waiting_reported = True

    def _pump(self, dev, ecodes):
        import select
        fd = dev.fd
        while not self._stop.is_set():
            r, _, _ = select.select([fd], [], [], 0.25)
            if not r:
                continue
            for ev in dev.read():
                if ev.type in (ecodes.EV_KEY, ecodes.EV_ABS) and self.on_event:
                    self.on_event(ev.code, ev.value)


def led_names():
    return all_led_names()
