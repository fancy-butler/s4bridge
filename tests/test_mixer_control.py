import types

from s4bridge.hw.controls import BY_ID
from s4bridge.mixer import engine
from s4bridge.mixer.control import MixerController


class FakePort:
    def __init__(self, name):
        self.name = name


class FakeClient:
    name = "S4 Bridge Mixer"

    def __init__(self, outs, ins=()):
        self._outs = [FakePort(n) for n in outs]
        self._ins = [FakePort(n) for n in ins]

    def get_ports(self, is_audio=True, is_output=False, is_input=False):
        return self._outs if is_output else self._ins


def test_source_discovery_and_defaults():
    c = FakeClient([
        "S4 Deck A:monitor_FL", "S4 Deck A:monitor_FR",
        "S4 Deck B:monitor_FL", "S4 Deck B:monitor_FR",
        "Traktor Kontrol S4 Analog Stereo Input C:capture_FL", "Traktor Kontrol S4 Analog Stereo Input C:capture_FR",
        "Traktor Kontrol S4 Analog Stereo Input D:capture_FL", "Traktor Kontrol S4 Analog Stereo Input D:capture_FR",
        "Mbox 3 Pro Pro:capture_AUX0",                                   # not a stereo pair: ignored
        "S4 Bridge Mixer:main_L",                                        # ourselves: ignored
    ], ins=["Traktor Kontrol S4 Analog Stereo Main Out:playback_FL", "Traktor Kontrol S4 Analog Stereo Main Out:playback_FR",
            "Traktor Kontrol S4 Analog Stereo Headphones Out:playback_FL",
            "Traktor Kontrol S4 Analog Stereo Headphones Out:playback_FR"])
    pairs = engine.stereo_sources(c)
    assert "Mbox 3 Pro Pro" not in pairs and "S4 Bridge Mixer" not in pairs
    d = engine.default_sources(pairs)
    assert d == {"A": "S4 Deck A", "B": "S4 Deck B",
                 "C": "Traktor Kontrol S4 Analog Stereo Input C", "D": "Traktor Kontrol S4 Analog Stereo Input D"}
    assert engine.find_playback(c, "Main")[0].endswith("Main Out:playback_FL")
    assert engine.find_playback(c, "Headphone")[1].endswith("Headphones Out:playback_FR")


def make_ctrl():
    import copy
    from s4bridge.engine.profile import DEFAULT_PROFILE
    from s4bridge.engine.translator import Translator
    from s4bridge.hw.controls import HardwareMap
    from s4bridge.hw.device import SimDevice
    dev = SimDevice()
    t = Translator(HardwareMap(), copy.deepcopy(DEFAULT_PROFILE), dev, lambda *a: None)
    core = types.SimpleNamespace(translator=t, device=dev, hw=t.hw, settings={}, save_settings=lambda: None)
    m = MixerController(core)
    sent = []
    m._send = sent.append
    t.listeners.append(m._on_event)
    return t, dev, m, sent


def test_knobs_and_buttons_drive_the_mixer():
    t, dev, m, sent = make_ctrl()
    t.handle_event(BY_ID["C.low"].code, 0)
    assert sent[-1] == {"strip": "C", "low": 0.0}
    t.handle_event(BY_ID["G.crossfader"].code, 4095)
    assert sent[-1] == {"xfader": 1.0}
    g = BY_ID["A.gain"].code
    t.handle_event(g, 15); t.handle_event(g, 1)          # +2 detents across the wrap
    assert sent[-1] == {"strip": "A", "gain_db": 1.5}
    t.handle_event(BY_ID["B.cue"].code, 1)
    assert sent[-1] == {"strip": "B", "cue": True}
    assert dev.led_state["LED: Channel B: Cue"] == 31


def test_meters_light_the_s4():
    t, dev, m, sent = make_ctrl()
    m.meters = {"A": 0.6, "B": 0.0, "C": 1.0, "D": 0.01, "main": 0.9}   # A = -4.4 dB
    m._meter_leds()
    lit = lambda s: sum(1 for i in range(1, 7) if dev.led_state.get(f"LED: Channel {s}: Meter {i}"))
    assert lit("A") == 4 and lit("B") == 0 and lit("C") == 6 and lit("D") == 0
    assert dev.led_state["LED: Channel C: Meter clip"] == 31


def _pw_args(s):
    """PipeWire's module_args_add_props (module-protocol-pulse/module.c), ported for the test."""
    out, p = {}, 0
    while p < len(s):
        while p < len(s) and s[p].isspace():
            p += 1
        e = s.find("=", p)
        if e < 0:
            break
        k, p = s[p:e], e + 1
        f = " "
        if p < len(s) and s[p] in "\"'":
            f = s[p]; p += 1
        v = ""
        while p < len(s) and s[p] != f:
            if s[p] == "\\":
                p += 1
                if p >= len(s):
                    break
            v += s[p]; p += 1
        p += 1
        out[k] = v
    return out


def test_virtual_sink_name_survives_pipewire_parsing(monkeypatch):
    calls = []
    monkeypatch.setattr(engine, "_pactl", lambda *a: calls.append(a) or "")
    engine.load_deck_sinks()
    loads = [c for c in calls if c[0] == "load-module"]
    assert len(loads) == 2
    for args, want in zip(loads, ("S4 Deck A", "S4 Deck B")):
        line = " ".join(args[2:])                     # pactl joins argv with spaces
        props = _pw_args(_pw_args(line)["sink_properties"])
        assert props["device.description"] == want


def test_s4_outputs_never_offered_as_sources():
    c = FakeClient(["Traktor Kontrol S4 Analog Stereo Main Out:monitor_FL",
                    "Traktor Kontrol S4 Analog Stereo Main Out:monitor_FR",
                    "S4 Deck A:monitor_FL", "S4 Deck A:monitor_FR"])
    assert list(engine.stereo_sources(c)) == ["S4 Deck A"]


SINK_INPUTS = """Sink Input #57
\tDriver: PipeWire
\tOwner Module: n/a
\tClient: 55
\tSink: 49
\tSample Specification: float32le 2ch 48000Hz
\tProperties:
\t\tapplication.name = "Firefox"
\t\tapplication.process.binary = "firefox"
\t\tmedia.name = "Never Gonna Give You Up - YouTube"
Sink Input #61
\tDriver: PipeWire
\tSink: 77
\tProperties:
\t\tapplication.name = "VLC media player (LibVLC 3.0.21)"
\t\tmedia.name = "VLC media player (LibVLC 3.0.21)"
"""
SINKS = "49\ts4bridge_deck_a\tPipeWire\tfloat32le 2ch 48000Hz\tRUNNING\n77\tSA-600\tPipeWire\ts32le 2ch 96000Hz\tRUNNING\n"


def test_playing_now_parsing():
    from s4bridge.mixer import routing
    streams = routing.parse_streams(SINK_INPUTS, routing.parse_sinks(SINKS))
    assert streams[0] == {"id": "57", "app": "Firefox", "title": "Never Gonna Give You Up - YouTube",
                          "sink": "s4bridge_deck_a", "deck": "A"}
    assert streams[1]["deck"] == "" and streams[1]["title"] == ""       # title same as app: hidden


def test_send_moves_stream(monkeypatch):
    from s4bridge.mixer import routing
    calls = []
    monkeypatch.setattr(routing, "_pactl", lambda *a: calls.append(a) or "SA-600\n")
    routing.send("61", "B")
    routing.send("57", "")
    assert calls[0] == ("move-sink-input", "61", "s4bridge_deck_b")
    assert calls[-1] == ("move-sink-input", "57", "SA-600")              # back to the normal output
