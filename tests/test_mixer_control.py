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
