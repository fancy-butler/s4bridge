# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Built-in USB driver for the S4 MK1: works without the Linux kernel driver, so on Mac and Windows too.

The S4 speaks a small vendor protocol (documented by the GPL Linux driver, sound/usb/caiaq):

* interface 0, alternate setting 1
* EP1 OUT/IN: commands and replies (GET_DEVICE_INFO 0x01, AUTO_MSG 0x0b)
* EP4 IN:     control reports, a run of 16-byte blocks: [block id hi, lo, ...payload]
* EP8 OUT:    LEDs, two bytes: [LED number, brightness 0..31]

Events are reported with the same codes the kernel driver gives evdev (buttons BTN_MISC+n, axes
ABS_HAT0X+n), so everything above this layer (mapping, MIDI, mixer, surface) is unchanged.
"""
from __future__ import annotations

import sys
import threading
from typing import Optional

from .controls import USB_PRODUCT, USB_VENDOR
from .device import LED_MAX, BaseDevice

BTN_MISC = 0x100
ABS_HAT0X = 0x10
N_BUTTONS = 96
BLOCK = 16

EP1_OUT, EP1_IN, EP4_IN, EP8_OUT = 0x01, 0x81, 0x84, 0x08
CMD_GET_DEVICE_INFO = 0x01
CMD_AUTO_MSG = 0x0B

# block id -> [(axis index, 16-bit word offset in the block)]; from tks4_dispatch()
_ANALOG = {
    2: [(0, 1), (1, 2), (2, 3), (3, 4), (4, 6), (7, 7)],
    3: [(6, 3), (5, 4), (8, 6), (9, 7)],
    4: [(10, 1), (11, 2), (12, 3), (13, 4), (14, 5), (15, 6), (16, 7)],
    5: [(17, 1), (18, 2), (19, 3), (20, 4), (21, 5), (22, 6), (23, 7)],
    6: [(24, 1), (25, 2), (26, 3), (27, 4), (28, 5), (29, 6), (30, 7)],
    7: [(31, 1), (32, 2), (33, 3), (34, 4), (35, 5)],
}

# kernel's kontrols4_controller[]: ALSA control name -> LED number on EP8
LED_INDEX = {
    "LED: Master: Quant": 10,
    "LED: Master: Headphone": 11,
    "LED: Master: Master": 12,
    "LED: Master: Snap": 14,
    "LED: Master: Warning": 15,
    "LED: Master: Master button": 112,
    "LED: Master: Snap button": 113,
    "LED: Master: Rec": 118,
    "LED: Master: Size": 119,
    "LED: Master: Quant button": 120,
    "LED: Master: Browser button": 121,
    "LED: Master: Play button": 126,
    "LED: Master: Undo button": 127,
    "LED: Channel A: >": 4,
    "LED: Channel A: <": 5,
    "LED: Channel A: Meter 1": 97,
    "LED: Channel A: Meter 2": 98,
    "LED: Channel A: Meter 3": 99,
    "LED: Channel A: Meter 4": 100,
    "LED: Channel A: Meter 5": 101,
    "LED: Channel A: Meter 6": 102,
    "LED: Channel A: Meter clip": 103,
    "LED: Channel A: Active": 114,
    "LED: Channel A: Cue": 116,
    "LED: Channel A: FX1": 149,
    "LED: Channel A: FX2": 148,
    "LED: Channel B: >": 2,
    "LED: Channel B: <": 3,
    "LED: Channel B: Meter 1": 89,
    "LED: Channel B: Meter 2": 90,
    "LED: Channel B: Meter 3": 91,
    "LED: Channel B: Meter 4": 92,
    "LED: Channel B: Meter 5": 93,
    "LED: Channel B: Meter 6": 94,
    "LED: Channel B: Meter clip": 95,
    "LED: Channel B: Active": 122,
    "LED: Channel B: Cue": 125,
    "LED: Channel B: FX1": 147,
    "LED: Channel B: FX2": 146,
    "LED: Channel C: >": 6,
    "LED: Channel C: <": 7,
    "LED: Channel C: Meter 1": 105,
    "LED: Channel C: Meter 2": 106,
    "LED: Channel C: Meter 3": 107,
    "LED: Channel C: Meter 4": 108,
    "LED: Channel C: Meter 5": 109,
    "LED: Channel C: Meter 6": 110,
    "LED: Channel C: Meter clip": 111,
    "LED: Channel C: Active": 115,
    "LED: Channel C: Cue": 117,
    "LED: Channel C: FX1": 151,
    "LED: Channel C: FX2": 150,
    "LED: Channel D: >": 0,
    "LED: Channel D: <": 1,
    "LED: Channel D: Meter 1": 81,
    "LED: Channel D: Meter 2": 82,
    "LED: Channel D: Meter 3": 83,
    "LED: Channel D: Meter 4": 84,
    "LED: Channel D: Meter 5": 85,
    "LED: Channel D: Meter 6": 86,
    "LED: Channel D: Meter clip": 87,
    "LED: Channel D: Active": 123,
    "LED: Channel D: Cue": 124,
    "LED: Channel D: FX1": 145,
    "LED: Channel D: FX2": 144,
    "LED: Deck A: 1 (blue)": 22,
    "LED: Deck A: 1 (green)": 23,
    "LED: Deck A: 2 (blue)": 20,
    "LED: Deck A: 2 (green)": 21,
    "LED: Deck A: 3 (blue)": 18,
    "LED: Deck A: 3 (green)": 19,
    "LED: Deck A: 4 (blue)": 16,
    "LED: Deck A: 4 (green)": 17,
    "LED: Deck A: Load": 44,
    "LED: Deck A: Deck C button": 45,
    "LED: Deck A: In": 47,
    "LED: Deck A: Out": 46,
    "LED: Deck A: Shift": 24,
    "LED: Deck A: Sync": 27,
    "LED: Deck A: Cue": 26,
    "LED: Deck A: Play": 25,
    "LED: Deck A: Tempo up": 33,
    "LED: Deck A: Tempo down": 32,
    "LED: Deck A: Master": 34,
    "LED: Deck A: Keylock": 35,
    "LED: Deck A: Deck A": 37,
    "LED: Deck A: Deck C": 36,
    "LED: Deck A: Samples": 38,
    "LED: Deck A: On Air": 39,
    "LED: Deck A: Sample 1": 31,
    "LED: Deck A: Sample 2": 30,
    "LED: Deck A: Sample 3": 29,
    "LED: Deck A: Sample 4": 28,
    "LED: Deck A: Digit 1 - A": 55,
    "LED: Deck A: Digit 1 - B": 54,
    "LED: Deck A: Digit 1 - C": 53,
    "LED: Deck A: Digit 1 - D": 52,
    "LED: Deck A: Digit 1 - E": 51,
    "LED: Deck A: Digit 1 - F": 50,
    "LED: Deck A: Digit 1 - G": 49,
    "LED: Deck A: Digit 1 - dot": 48,
    "LED: Deck A: Digit 2 - A": 63,
    "LED: Deck A: Digit 2 - B": 62,
    "LED: Deck A: Digit 2 - C": 61,
    "LED: Deck A: Digit 2 - D": 60,
    "LED: Deck A: Digit 2 - E": 59,
    "LED: Deck A: Digit 2 - F": 58,
    "LED: Deck A: Digit 2 - G": 57,
    "LED: Deck A: Digit 2 - dot": 56,
    "LED: Deck B: 1 (blue)": 78,
    "LED: Deck B: 1 (green)": 79,
    "LED: Deck B: 2 (blue)": 76,
    "LED: Deck B: 2 (green)": 77,
    "LED: Deck B: 3 (blue)": 74,
    "LED: Deck B: 3 (green)": 75,
    "LED: Deck B: 4 (blue)": 72,
    "LED: Deck B: 4 (green)": 73,
    "LED: Deck B: Load": 180,
    "LED: Deck B: Deck D button": 181,
    "LED: Deck B: In": 183,
    "LED: Deck B: Out": 182,
    "LED: Deck B: Shift": 64,
    "LED: Deck B: Sync": 67,
    "LED: Deck B: Cue": 66,
    "LED: Deck B: Play": 65,
    "LED: Deck B: Tempo up": 185,
    "LED: Deck B: Tempo down": 184,
    "LED: Deck B: Master": 186,
    "LED: Deck B: Keylock": 187,
    "LED: Deck B: Deck B": 189,
    "LED: Deck B: Deck D": 188,
    "LED: Deck B: Samples": 190,
    "LED: Deck B: On Air": 191,
    "LED: Deck B: Sample 1": 71,
    "LED: Deck B: Sample 2": 70,
    "LED: Deck B: Sample 3": 69,
    "LED: Deck B: Sample 4": 68,
    "LED: Deck B: Digit 1 - A": 175,
    "LED: Deck B: Digit 1 - B": 174,
    "LED: Deck B: Digit 1 - C": 173,
    "LED: Deck B: Digit 1 - D": 172,
    "LED: Deck B: Digit 1 - E": 171,
    "LED: Deck B: Digit 1 - F": 170,
    "LED: Deck B: Digit 1 - G": 169,
    "LED: Deck B: Digit 1 - dot": 168,
    "LED: Deck B: Digit 2 - A": 167,
    "LED: Deck B: Digit 2 - B": 166,
    "LED: Deck B: Digit 2 - C": 165,
    "LED: Deck B: Digit 2 - D": 164,
    "LED: Deck B: Digit 2 - E": 163,
    "LED: Deck B: Digit 2 - F": 162,
    "LED: Deck B: Digit 2 - G": 161,
    "LED: Deck B: Digit 2 - dot": 160,
    "LED: FX1: dry/wet": 153,
    "LED: FX1: 1": 154,
    "LED: FX1: 2": 155,
    "LED: FX1: 3": 156,
    "LED: FX1: Mode": 157,
    "LED: FX2: dry/wet": 129,
    "LED: FX2: 1": 130,
    "LED: FX2: 2": 131,
    "LED: FX2: 3": 132,
    "LED: FX2: Mode": 133,
}


# Report bytes the kernel driver never reads. With extras on, they're reported as codes from
# EXTRA_BASE up, so anything the S4 sends there shows on the Monitor page as "unknown <code>".
EXTRA_BASE = 0x300
_EXTRA_BYTES = {0: (2, 3), 1: (2, 3, 10, 11, 14, 15)}          # block -> byte offsets
_EXTRA_WORDS = {2: (5,), 3: (1, 2, 5), 7: (6, 7)}              # block -> 16-bit word offsets
_EXTRA_CODES: dict[tuple, int] = {}
for _b, _offs in _EXTRA_BYTES.items():
    for _o in _offs:
        _EXTRA_CODES[("b", _b, _o)] = EXTRA_BASE + len(_EXTRA_CODES)
for _b, _offs in _EXTRA_WORDS.items():
    for _o in _offs:
        _EXTRA_CODES[("w", _b, _o)] = EXTRA_BASE + len(_EXTRA_CODES)
EXTRA_NAMES = {v: f"block {k[1]} {'byte' if k[0] == 'b' else 'word'} {k[2]}" for k, v in _EXTRA_CODES.items()}


class S4Parser:
    """Turns EP4 reports into (code, value) changes, like the kernel's input core does.

    extras=True also reports the bytes the kernel ignores (see EXTRA_BASE).
    """

    def __init__(self, extras: bool = False):
        self.state: dict[int, int] = {}
        self.extras = extras

    def _extra(self, out, b, bid):
        for o in _EXTRA_BYTES.get(bid, ()):
            self._put(out, _EXTRA_CODES[("b", bid, o)], b[o])
        for o in _EXTRA_WORDS.get(bid, ()):
            code, v = _EXTRA_CODES[("w", bid, o)], (b[o * 2] << 8) | b[o * 2 + 1]
            last = self.state.get(code)
            if last is None or abs(v - last) >= 4:      # analog: skip electrical noise
                self.state[code] = v
                out.append((code, v))

    def _put(self, out, code, value):
        if self.state.get(code) != value:
            self.state[code] = value
            out.append((code, value))

    def feed(self, buf: bytes) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        for start in range(0, len(buf) - BLOCK + 1, BLOCK):
            b = buf[start:start + BLOCK]
            bid = (b[0] << 8) | b[1]
            if bid == 0:
                for i in range(N_BUTTONS):
                    self._put(out, BTN_MISC + i, (b[4 + i // 8] >> (i % 8)) & 1)
            elif bid == 1:
                self._put(out, ABS_HAT0X + 36, b[9] | ((b[8] & 0x3) << 8))     # left jog
                self._put(out, ABS_HAT0X + 37, b[13] | ((b[12] & 0x3) << 8))   # right jog
                enc = [b[3] & 0xF, b[4] >> 4, b[4] & 0xF, b[5] >> 4, b[5] & 0xF,
                       b[6] >> 4, b[6] & 0xF, b[7] >> 4, b[7] & 0xF]
                for i, v in enumerate(enc):
                    self._put(out, ABS_HAT0X + 38 + i, v)
            elif bid in _ANALOG:
                for axis, off in _ANALOG[bid]:
                    self._put(out, ABS_HAT0X + axis, (b[off * 2] << 8) | b[off * 2 + 1])
            else:
                break   # unknown block: the kernel drops the rest of the report, so do we
            if self.extras:
                self._extra(out, b, bid)
        return out


def _backend():
    """libusb from the system, or the copy bundled by the libusb-package wheel (Mac/Windows)."""
    try:
        import libusb_package
        return libusb_package.get_libusb1_backend()
    except Exception:  # noqa: BLE001
        return None


class UsbDevice(BaseDevice):
    """The S4 opened directly over USB (pyusb + libusb)."""
    name = "Traktor Kontrol S4 MK1 (built-in USB driver)"

    def __init__(self):
        super().__init__()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._dev = None
        self._detached = False
        self._wlock = threading.Lock()
        self.evdev_path = ""
        self.card_id = ""
        self.firmware = None

    # ---------------------------------------------------------------- lifecycle
    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="s4bridge-usb", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    # ---------------------------------------------------------------- LEDs
    def _hw_level(self, value: int) -> int:
        if value <= 0:
            return 0
        return max(1, min(LED_MAX, round(value * self.brightness)))

    def _write_led(self, name: str, level: int):
        idx = LED_INDEX.get(name)
        dev = self._dev
        if idx is None or dev is None:
            return
        try:
            with self._wlock:
                dev.write(EP8_OUT, bytes((idx, level)), timeout=200)
        except Exception:  # noqa: BLE001  unplugged mid-write: the read loop notices
            pass

    def set_led(self, name: str, value: int):
        old = self.led_state.get(name)
        super().set_led(name, value)
        if old != value:
            self._write_led(name, self._hw_level(value))

    def apply_brightness(self):
        for n, v in list(self.led_state.items()):
            self._write_led(n, self._hw_level(v))

    # ---------------------------------------------------------------- USB
    def _find(self):
        import usb.core
        kw = {"idVendor": USB_VENDOR, "idProduct": USB_PRODUCT}
        be = _backend()
        if be is not None:
            kw["backend"] = be
        return usb.core.find(**kw)

    def _open(self, dev):
        import usb.core
        # Linux: take the S4 from snd-usb-caiaq for as long as we run; handed back on close
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
                self._detached = True
        except (NotImplementedError, usb.core.USBError):
            pass
        try:
            dev.set_configuration(1)
        except usb.core.USBError:
            pass   # already configured (normal on a replug)
        import usb.util
        usb.util.claim_interface(dev, 0)
        dev.set_interface_altsetting(interface=0, alternate_setting=1)
        dev.write(EP1_OUT, bytes((CMD_GET_DEVICE_INFO,)), timeout=500)
        try:
            reply = bytes(dev.read(EP1_IN, 64, timeout=1000))
            if reply and reply[0] == CMD_GET_DEVICE_INFO and len(reply) >= 3:
                self.firmware = reply[1] | (reply[2] << 8)
        except usb.core.USBTimeoutError:
            pass   # older firmware may not answer; controls still work
        # report digital inputs, analog inputs (every 10 ms), encoders: as the kernel does
        dev.write(EP1_OUT, bytes((CMD_AUTO_MSG, 1, 10, 5)), timeout=500)

    def _close(self, dev):
        import usb.util
        self._dev = None
        try:
            usb.util.release_interface(dev, 0)
        except Exception:  # noqa: BLE001
            pass
        if self._detached:
            try:
                dev.attach_kernel_driver(0)
            except Exception:  # noqa: BLE001
                pass
            self._detached = False
        try:
            usb.util.dispose_resources(dev)
        except Exception:  # noqa: BLE001
            pass

    def _run(self):
        try:
            import usb.core
        except ImportError:
            self._status("error", "The built-in USB driver needs pyusb (python-pyusb).")
            return
        waiting = False
        while not self._stop.is_set():
            try:
                dev = self._find()
            except usb.core.NoBackendError:
                self._status("error", "libusb isn't installed, so the built-in USB driver can't run.")
                return
            if dev is None:
                if not waiting:
                    self._status("waiting", "Plug in and power on the S4…")
                    waiting = True
                self._stop.wait(1.5)
                continue
            waiting = False
            try:
                self._open(dev)
            except usb.core.USBError as e:
                if getattr(e, "errno", None) in (13, 1):   # EACCES / EPERM
                    self._status("error", "No permission to open the S4 over USB. "
                                          "Use “Fix it” at the top of the window.")
                else:
                    self._status("error", f"Couldn't open the S4 over USB: {e}")
                self._close(dev)
                self._stop.wait(3)
                continue
            self._dev = dev
            fw = f" · firmware {self.firmware}" if self.firmware is not None else ""
            self._status("connected", f"Built-in USB driver{fw}")
            for n, v in list(self.led_state.items()):     # LEDs match after a reconnect
                self._write_led(n, self._hw_level(v))
            silent = False
            try:
                self._pump(dev)
            except usb.core.USBError:
                pass   # unplugged
            except self.Silent:
                silent = True
            finally:
                if silent:
                    try:
                        dev.reset()   # clean slate; we reconnect on the next pass
                    except Exception:  # noqa: BLE001
                        pass
                self._close(dev)
            if silent and not self._stop.is_set():
                self._status("waiting", "The S4 wasn't answering. Reconnecting…")
                self._stop.wait(1.0)
                continue
            if not self._stop.is_set():
                self._status("waiting", "S4 disconnected. Waiting for it to come back…")
                waiting = True

    WAKE_AFTER = 3.0   # seconds of total silence right after connecting before we nudge the S4

    class Silent(Exception):
        """Connected, but the S4 never started reporting (left half-configured by another driver)."""

    def _pump(self, dev):
        import time

        import usb.core
        parser = S4Parser(extras=True)
        heard = False
        nudged = False
        t0 = time.monotonic()
        while not self._stop.is_set():
            try:
                buf = bytes(dev.read(EP4_IN, 512, timeout=250))
            except usb.core.USBTimeoutError:
                # A healthy S4 sends its whole state the moment reporting starts. Total silence after
                # connecting means it's stuck; once it has spoken, quiet just means nobody's touching it.
                if not heard and time.monotonic() - t0 > self.WAKE_AFTER:
                    if nudged:
                        raise self.Silent()
                    nudged = True
                    t0 = time.monotonic()
                    self._status("connected", "Waking the S4…")
                    dev.write(EP1_OUT, bytes((CMD_AUTO_MSG, 1, 10, 5)), timeout=500)
                continue
            if not heard:
                heard = True
                if nudged:
                    fw = f" · firmware {self.firmware}" if self.firmware is not None else ""
                    self._status("connected", f"Built-in USB driver{fw}")
            for code, value in parser.feed(buf):
                if self.on_event:
                    self.on_event(code, value)


def available() -> bool:
    try:
        import usb.core  # noqa: F401
        return True
    except ImportError:
        return False


if __name__ == "__main__":   # quick hardware check: python -m s4bridge.hw.usb_s4
    d = UsbDevice()
    d.on_status = lambda s, t: print(f"[{s}] {t}")
    d.on_event = lambda c, v: print(f"code {c:#x} = {v}")
    d.start()
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        d.stop()
        sys.exit(0)
