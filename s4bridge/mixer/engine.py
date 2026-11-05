# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Standalone mixer audio engine. Runs as its own process (python -m s4bridge.mixer.engine)
so nothing the GUI does can ever cause a dropout.

  stdin : JSON lines, parameter updates   {"strip": "A", "volume": 0.8} / {"xfader": 0.3} /
                                          {"sources": {"C": "<client>"}} / {"quit": 1}
  stdout: JSON lines, status + meters     {"status": ...} / {"m": {...}, "clip": bool}

Talks to PipeWire through its JACK interface (pipewire-jack). Creates two virtual sound
outputs, "S4 Deck A" and "S4 Deck B", that any app can play into.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time

os.environ.setdefault("PIPEWIRE_LATENCY", "256/48000")

DECK_SINKS = {"A": ("s4bridge_deck_a", "S4 Deck A"), "B": ("s4bridge_deck_b", "S4 Deck B")}


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


# ------------------------------------------------------------------ virtual sinks
def _pactl(*args) -> str:
    try:
        return subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def unload_deck_sinks():
    for line in _pactl("list", "short", "modules").splitlines():
        if "s4bridge_deck_" in line:
            _pactl("unload-module", line.split()[0])


def load_deck_sinks():
    unload_deck_sinks()                       # leftovers from a crash
    for name, desc in DECK_SINKS.values():
        # the whole property list is one module argument, so the value with spaces must be
        # quoted *inside* it, or PipeWire stops reading the description at the first space
        _pactl("load-module", "module-null-sink", f"sink_name={name}",
               f"sink_properties=\"device.description='{desc}'\"", "channel_map=front-left,front-right")


# ------------------------------------------------------------------ port discovery
def stereo_sources(client) -> dict[str, tuple[str, str]]:
    """Every stereo audio output in the graph: label -> (left port, right port)."""
    out: dict[str, list[str]] = {}
    for p in client.get_ports(is_audio=True, is_output=True):
        if p.name.startswith(client.name + ":"):
            continue
        # never offer the S4's own outputs as a source: the mixer would feed itself
        if "Kontrol S4" in p.name and ("Main Out" in p.name or "Headphones Out" in p.name):
            continue
        c, _, port = p.name.partition(":")
        out.setdefault(c, []).append(port)
    pairs = {}
    for c, ports in out.items():
        for l_name, r_name in (("monitor_FL", "monitor_FR"), ("capture_FL", "capture_FR"),
                               ("output_FL", "output_FR"), ("capture_1", "capture_2")):
            if l_name in ports and r_name in ports:
                pairs[c] = (f"{c}:{l_name}", f"{c}:{r_name}")
                break
    return pairs


def default_sources(pairs: dict) -> dict[str, str]:
    names = list(pairs)
    pick = {}
    for s, (_, desc) in DECK_SINKS.items():
        hit = next((n for n in names if n == desc), None)
        if hit:
            pick[s] = hit
    s4_caps = sorted(n for n in names if "Kontrol S4" in n and pairs[n][0].endswith("capture_FL"))
    for s, n in zip("CD", s4_caps):
        pick[s] = n
    return pick


def find_playback(client, needle: str):
    ports = [p.name for p in client.get_ports(is_audio=True, is_input=True)
             if needle in p.name and "Kontrol S4" in p.name]
    fl = next((p for p in ports if p.endswith("playback_FL")), None)
    fr = next((p for p in ports if p.endswith("playback_FR")), None)
    return (fl, fr) if fl and fr else None


# ------------------------------------------------------------------ main
def main():
    try:
        import jack
        import numpy as np
        from .dsp import STRIPS, Mixer
    except Exception as e:  # noqa: BLE001
        emit({"status": "error", "error": f"Missing component: {e}. Install python-jack-client, "
                                          "python-numpy, python-scipy and pipewire-jack."})
        return 1

    load_deck_sinks()
    time.sleep(0.4)                           # let PipeWire publish the new sinks
    try:
        client = jack.Client("S4 Bridge Mixer", no_start_server=True)
    except jack.JackError as e:
        unload_deck_sinks()
        emit({"status": "error", "error": f"Couldn't reach PipeWire's JACK interface ({e}). "
                                          "Is pipewire-jack installed?"})
        return 1

    fs = client.samplerate
    mixer = Mixer(fs)
    lock = threading.Lock()
    ins = {s: (client.inports.register(f"{s}_L"), client.inports.register(f"{s}_R")) for s in STRIPS}
    main_out = (client.outports.register("main_L"), client.outports.register("main_R"))
    phones_out = (client.outports.register("phones_L"), client.outports.register("phones_R"))
    connected = {s: False for s in STRIPS}
    xruns = [0]

    @client.set_process_callback
    def process(frames):
        bufs = {}
        for s, (l, r) in ins.items():
            if connected[s]:
                bufs[s] = np.vstack([l.get_array(), r.get_array()])
        with lock:
            m, ph = mixer.process(bufs, frames)
        main_out[0].get_array()[:] = m[0]
        main_out[1].get_array()[:] = m[1]
        phones_out[0].get_array()[:] = ph[0]
        phones_out[1].get_array()[:] = ph[1]

    @client.set_xrun_callback
    def xrun(delay):
        xruns[0] += 1

    client.activate()

    sources: dict[str, str] = {}

    def connect_sources(want: dict[str, str]):
        pairs = stereo_sources(client)
        for s in STRIPS:
            name = want.get(s)
            l, r = ins[s]
            for port in (l, r):
                for c in list(port.connections):
                    try:
                        client.disconnect(c, port)
                    except jack.JackError:
                        pass
            connected[s] = False
            if name and name in pairs:
                try:
                    client.connect(pairs[name][0], l)
                    client.connect(pairs[name][1], r)
                    connected[s] = True
                    sources[s] = name
                except jack.JackError:
                    pass
        return pairs

    pairs = connect_sources(default_sources(stereo_sources(client)))
    outs = {"main": find_playback(client, "Main"), "phones": find_playback(client, "Headphone")}
    for key, ports, pair in (("main", main_out, outs["main"]), ("phones", phones_out, outs["phones"])):
        if pair:
            for src, dst in zip(ports, pair):
                try:
                    client.connect(src, dst)
                except jack.JackError:
                    pass
    emit({"status": "running", "samplerate": fs, "blocksize": client.blocksize,
          "sources": sources, "available": sorted(pairs),
          "outputs": {k: bool(v) for k, v in outs.items()}})

    stop = threading.Event()

    def read_stdin():
        for line in sys.stdin:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("quit"):
                break
            if "sources" in msg:
                want = dict(sources)
                want.update(msg["sources"])
                p = connect_sources(want)
                emit({"status": "running", "samplerate": fs, "blocksize": client.blocksize,
                      "sources": sources, "available": sorted(p),
                      "outputs": {k: bool(v) for k, v in outs.items()}})
                continue
            if msg.get("refresh"):
                emit({"available": sorted(stereo_sources(client)), "sources": sources})
                continue
            with lock:
                mixer.set(msg)
        stop.set()

    threading.Thread(target=read_stdin, daemon=True).start()
    try:
        while not stop.wait(1 / 30):
            with lock:
                peaks = dict(mixer.peaks)
                clip = mixer.clipped
            emit({"m": {k: round(v, 3) for k, v in peaks.items()}, "clip": clip, "xruns": xruns[0]})
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    finally:
        client.deactivate()
        client.close()
        unload_deck_sinks()
    return 0


if __name__ == "__main__":
    sys.exit(main())
