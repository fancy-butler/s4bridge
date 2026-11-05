# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Tiny ctypes bindings to libasound: control elements (LEDs) and the
sequencer (virtual MIDI ports).  No compiled Python extensions needed, so the
app installs the same way on Arch, Fedora and Debian/Ubuntu.
"""
from __future__ import annotations

import ctypes as C
import ctypes.util
import os
import re
import select
import threading
from typing import Callable, Optional

_lib = None


def lib():
    global _lib
    if _lib is None:
        name = ctypes.util.find_library("asound") or "libasound.so.2"
        _lib = C.CDLL(name)
        _lib.snd_strerror.restype = C.c_char_p
        _lib.snd_seq_client_id.restype = C.c_int
    return _lib


class AlsaError(RuntimeError):
    pass


def _check(rc: int, what: str) -> int:
    if rc < 0:
        raise AlsaError(f"{what}: {lib().snd_strerror(rc).decode()}")
    return rc


# --------------------------------------------------------------------- cards
def find_card(driver: str = "snd-usb-caiaq", shortname: str = "Kontrol S4") -> Optional[str]:
    """Return the ALSA card id (e.g. 'TraktorKontrolS') for the S4, or None."""
    try:
        text = open("/proc/asound/cards").read()
    except OSError:
        return None
    for m in re.finditer(r"^\s*(\d+)\s+\[(\S+)\s*\]:\s*(\S+)\s+-\s+(.*)$", text, re.M):
        idx, cid, drv, name = m.groups()
        if drv == driver and shortname in name:
            return cid
    return None


# ------------------------------------------------------------ control (LEDs)
IFACE_HWDEP = 1   # snd-usb-caiaq registers its LED controls on the HWDEP iface


class LedWriter:
    """Writes integer values to named ALSA control elements of one card."""

    def __init__(self, card_id: str):
        self.card = card_id
        self._h = C.c_void_p()
        _check(lib().snd_ctl_open(C.byref(self._h), f"hw:{card_id}".encode(), 0), "snd_ctl_open")
        self._ids: dict[str, C.c_void_p] = {}
        self._val = C.c_void_p()
        _check(lib().snd_ctl_elem_value_malloc(C.byref(self._val)), "elem_value_malloc")
        self._lock = threading.Lock()
        self._last: dict[str, int] = {}
        self._failed: set[str] = set()

    def _id(self, name: str) -> C.c_void_p:
        eid = self._ids.get(name)
        if eid is None:
            eid = C.c_void_p()
            _check(lib().snd_ctl_elem_id_malloc(C.byref(eid)), "elem_id_malloc")
            lib().snd_ctl_elem_id_set_interface(eid, IFACE_HWDEP)
            lib().snd_ctl_elem_id_set_name(eid, name.encode())
            self._ids[name] = eid
        return eid

    def set(self, name: str, value: int, force: bool = False) -> bool:
        with self._lock:
            if not force and self._last.get(name) == value:
                return True
            L = lib()
            L.snd_ctl_elem_value_clear(self._val)
            L.snd_ctl_elem_value_set_id(self._val, self._id(name))
            L.snd_ctl_elem_value_set_integer(self._val, 0, C.c_long(value))
            rc = L.snd_ctl_elem_write(self._h, self._val)
            if rc < 0:
                if name not in self._failed:
                    self._failed.add(name)
                    import sys
                    print(f"[s4bridge] LED '{name}': {L.snd_strerror(rc).decode()}", file=sys.stderr)
                return False
            self._last[name] = value
            return True

    def close(self):
        if self._h:
            lib().snd_ctl_close(self._h)
            self._h = C.c_void_p()


# ---------------------------------------------------------------- sequencer
class _Addr(C.Structure):
    _fields_ = [("client", C.c_ubyte), ("port", C.c_ubyte)]


class SeqEvent(C.Structure):
    # snd_seq_event_t: 28 bytes (snd_seq_ev_ext is packed in the kernel ABI)
    _fields_ = [
        ("type", C.c_ubyte), ("flags", C.c_ubyte), ("tag", C.c_ubyte), ("queue", C.c_ubyte),
        ("time_a", C.c_uint), ("time_b", C.c_uint),
        ("source", _Addr), ("dest", _Addr),
        ("data", C.c_ubyte * 12),
    ]


assert C.sizeof(SeqEvent) == 28

EV_NOTEON, EV_NOTEOFF, EV_CONTROLLER, EV_PITCHBEND = 6, 7, 10, 13
ADDR_UNKNOWN, ADDR_SUBSCRIBERS = 253, 254
QUEUE_DIRECT = 253
CAP_READ, CAP_WRITE, CAP_SUBS_READ, CAP_SUBS_WRITE = 1, 2, 1 << 5, 1 << 6
TYPE_MIDI_GENERIC, TYPE_APPLICATION = 1 << 1, 1 << 20
OPEN_DUPLEX = 3
POLLIN = 1


def encode(status: int, d1: int, d2: int) -> Optional[SeqEvent]:
    """Raw MIDI short message -> seq event (note on/off, CC, pitchbend)."""
    ev = SeqEvent()
    kind, ch = status & 0xF0, status & 0x0F
    if kind in (0x90, 0x80):
        ev.type = EV_NOTEON if kind == 0x90 else EV_NOTEOFF
        ev.data[0], ev.data[1], ev.data[2] = ch, d1 & 0x7F, d2 & 0x7F
    elif kind == 0xB0:
        ev.type = EV_CONTROLLER
        ev.data[0] = ch
        C.memmove(C.addressof(ev.data) + 4, C.byref(C.c_uint(d1 & 0x7F)), 4)
        C.memmove(C.addressof(ev.data) + 8, C.byref(C.c_int(d2 & 0x7F)), 4)
    else:
        return None
    ev.queue = QUEUE_DIRECT
    ev.dest.client, ev.dest.port = ADDR_SUBSCRIBERS, ADDR_UNKNOWN
    return ev


def decode(ev: SeqEvent) -> Optional[tuple[int, int, int]]:
    """Seq event -> raw (status, d1, d2) for the types we care about."""
    ch = ev.data[0] & 0x0F
    if ev.type in (EV_NOTEON, EV_NOTEOFF):
        vel = ev.data[2] if ev.type == EV_NOTEON else 0
        return (0x90 | ch, ev.data[1], vel)
    if ev.type == EV_CONTROLLER:
        param = C.c_uint.from_buffer_copy(bytes(ev.data[4:8])).value
        value = C.c_int.from_buffer_copy(bytes(ev.data[8:12])).value
        return (0xB0 | ch, param & 0x7F, max(0, min(127, value)))
    return None


class VirtualMidi:
    """One ALSA sequencer client with a duplex port that other apps
    (Mixxx, Ardour, Bitwig, VirtualDJ via Wine, ...) see as a MIDI device."""

    def __init__(self, client_name: str = "S4 Bridge", port_name: str = "Kontrol S4 MK1",
                 on_message: Optional[Callable[[int, int, int], None]] = None):
        L = lib()
        self._seq = C.c_void_p()
        _check(L.snd_seq_open(C.byref(self._seq), b"default", OPEN_DUPLEX, 1), "snd_seq_open")
        L.snd_seq_set_client_name(self._seq, client_name.encode())
        self.port = _check(L.snd_seq_create_simple_port(
            self._seq, port_name.encode(),
            CAP_READ | CAP_WRITE | CAP_SUBS_READ | CAP_SUBS_WRITE,
            TYPE_MIDI_GENERIC | TYPE_APPLICATION), "create_simple_port")
        self.client = L.snd_seq_client_id(self._seq)
        self.on_message = on_message
        self._out_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._reader, name="s4bridge-midi-in", daemon=True)
        self._thread.start()

    @property
    def address(self) -> str:
        return f"{self.client}:{self.port}"

    def send(self, status: int, d1: int, d2: int):
        ev = encode(status, d1, d2)
        if ev is None:
            return
        ev.source.port = self.port
        with self._out_lock:
            lib().snd_seq_event_output_direct(self._seq, C.byref(ev))

    def _reader(self):
        L = lib()
        n = L.snd_seq_poll_descriptors_count(self._seq, POLLIN)
        pfds = (C.c_byte * (8 * max(1, n)))()
        L.snd_seq_poll_descriptors(self._seq, pfds, n, POLLIN)
        fds = [C.c_int.from_buffer_copy(bytes(pfds[i * 8:i * 8 + 4])).value for i in range(n)]
        poller = select.poll()
        for fd in fds:
            poller.register(fd, select.POLLIN)
        evp = C.POINTER(SeqEvent)()
        while not self._stop.is_set():
            if not poller.poll(200):
                continue
            while True:
                rc = L.snd_seq_event_input(self._seq, C.byref(evp))
                if rc < 0 or not evp:
                    break
                msg = decode(evp.contents)
                if msg and self.on_message:
                    try:
                        self.on_message(*msg)
                    except Exception:  # never let a handler kill the reader
                        import traceback
                        traceback.print_exc()
                if L.snd_seq_event_input_pending(self._seq, 0) <= 0:
                    break

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1)
        if self._seq:
            lib().snd_seq_close(self._seq)
            self._seq = C.c_void_p()


def seq_available() -> bool:
    return os.path.exists("/dev/snd/seq")
