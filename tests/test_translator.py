import copy
from collections import Counter

from s4bridge.hw.controls import CONTROLS, HardwareMap, BY_ID, all_led_names
from s4bridge.hw.device import SimDevice
from s4bridge.engine.profile import DEFAULT_PROFILE, area_key
from s4bridge.engine.translator import Translator
from s4bridge.hw import alsa


def make():
    out = []
    dev = SimDevice()
    t = Translator(HardwareMap(), copy.deepcopy(DEFAULT_PROFILE), dev, lambda *m: out.append(m))
    return t, dev, out


def test_codes_unique():
    codes = [c.code for c in CONTROLS if c.code is not None]
    assert len(codes) == len(set(codes)), [c for c, n in Counter(codes).items() if n > 1]


def test_every_control_has_mapping():
    for c in CONTROLS:
        assert area_key(c.area, c.func) in DEFAULT_PROFILE["map"], c.cid


def test_no_midi_collisions_per_channel():
    p = DEFAULT_PROFILE
    used = {}
    def claim(kind, ch, num, who):
        k = (kind, ch, num)
        assert k not in used, f"{who} collides with {used[k]}"
        used[k] = who
    for key, m in p["map"].items():
        scope = key.split(".")[0]
        chans = list(p["deck_channels"].values()) if scope in ("deck", "strip") else [p["global_channel"]]
        nums = [m["num"]]
        is_btn_like = m["type"] == "note" or key.endswith(("jog", "move", "size", "gain", "browse"))
        if m.get("shiftable", True) and is_btn_like:
            nums.append(m["num"] + (p["global_shift_offset"] if scope in ("G", "FX1", "FX2") else p["deck_shift_offset"]))
        if m.get("hires"):
            nums.append(m["num"] + 0x20)
        for ch in chans:
            for n in nums:
                claim(m["type"], ch, n, key)
    for key, m in p["leds"].items():
        scope = key.split(".")[0]
        chans = list(p["deck_channels"].values()) if scope in ("deck", "strip") else [p["global_channel"]]
        for ch in chans:
            claim(m["type"], ch, m["num"], key)


def test_play_button_and_deck_toggle():
    t, dev, out = make()
    play = BY_ID["L.play"].code
    t.handle_event(play, 1)
    t.handle_event(play, 0)
    assert out == [(0x90, 0x0A, 127), (0x80, 0x0A, 0)]
    out.clear()
    t.handle_event(BY_ID["L.deck_toggle"].code, 1)
    assert t.active["L"] == "C"
    t.handle_event(play, 1)
    assert out[-1] == (0x92, 0x0A, 127)          # deck C = channel 3
    assert dev.led_state["LED: Deck A: Deck C"] == 31
    assert dev.led_state["LED: Deck A: Deck A"] == 0


def test_shift_layer():
    t, dev, out = make()
    t.handle_event(BY_ID["R.shift"].code, 1)
    t.handle_event(BY_ID["R.cue"].code, 1)
    assert out[-1] == (0x91, 0x09 + 0x20, 127)
    t.handle_event(BY_ID["L.cue"].code, 1)       # other side not shifted
    assert out[-1] == (0x90, 0x09, 127)


def test_jog_wraps():
    t, dev, out = make()
    jog = BY_ID["L.jog"].code
    t.handle_event(jog, 1020)
    t.handle_event(jog, 4)        # +8 across the wrap
    assert out[-1] == (0xB0, 0x02, 64 + 8)
    t.handle_event(jog, 1022)     # -6 back across
    assert out[-1] == (0xB0, 0x02, 64 - 6)


def test_encoder_wraps():
    t, dev, out = make()
    enc = BY_ID["G.browse"].code
    t.handle_event(enc, 15)
    t.handle_event(enc, 0)
    assert out[-1] == (0xB4, 0x02, 65)


def test_hires_tempo():
    t, dev, out = make()
    t.handle_event(BY_ID["L.tempo"].code, 0xFFF)
    assert out[-2:] == [(0xB0, 0x04, 127), (0xB0, 0x24, 0x7C)]


def test_pot_dedup():
    t, dev, out = make()
    hi = BY_ID["A.hi"].code
    t.handle_event(hi, 100)
    t.handle_event(hi, 101)       # same 7-bit value
    assert len(out) == 1


def test_touch_hysteresis():
    t, dev, out = make()
    touch = BY_ID["R.touch"].code
    t.handle_event(touch, 3100)
    t.handle_event(touch, 3000)   # inside hysteresis, still touched
    t.handle_event(touch, 2800)
    assert out == [(0x91, 0x03, 127), (0x81, 0x03, 0)]


def test_led_feedback_cached_per_deck():
    t, dev, out = make()
    t.handle_midi(0x92, 0x0A, 127)         # deck C play LED while left shows A
    assert dev.led_state.get("LED: Deck A: Play", 0) == 0
    t.handle_midi(0x90, 0x0A, 127)
    assert dev.led_state["LED: Deck A: Play"] == 31
    t.toggle_deck("L")                     # now on C: still lit (C cached on)
    assert dev.led_state["LED: Deck A: Play"] == 31
    t.handle_midi(0x92, 0x0A, 0)
    assert dev.led_state["LED: Deck A: Play"] == 0
    t.toggle_deck("L")                     # back to A: lit again
    assert dev.led_state["LED: Deck A: Play"] == 31


def test_hotcue_colors_and_meter_and_display():
    t, dev, out = make()
    t.handle_midi(0x91, 0x0B, 20)
    assert dev.led_state["LED: Deck B: 1 (blue)"] == 31 and dev.led_state["LED: Deck B: 1 (green)"] == 0
    t.handle_midi(0x91, 0x0B, 60)
    assert dev.led_state["LED: Deck B: 1 (blue)"] == 0 and dev.led_state["LED: Deck B: 1 (green)"] == 31
    t.handle_midi(0xB2, 0x46, 64)          # channel C meter half
    lit = [dev.led_state[f"LED: Channel C: Meter {i}"] for i in range(1, 7)]
    assert lit == [31, 31, 31, 31, 0, 0]
    t.handle_midi(0xB0, 0x50, 16)          # loop size 16 on deck A display
    assert dev.led_state["LED: Deck A: Digit 1 - B"] == 31   # "1"
    assert dev.led_state["LED: Deck A: Digit 2 - E"] == 31   # "6"


def test_led_names_exist_in_kernel_list():
    # every LED we drive must be one the kernel driver registers
    import re, pathlib
    src = pathlib.Path(__file__).with_name("kernel_s4_leds.txt").read_text().splitlines()
    kernel = set(s.strip() for s in src if s.strip())
    missing = [n for n in all_led_names() if n not in kernel]
    assert not missing, missing


def test_seq_event_roundtrip():
    for msg in [(0x93, 10, 100), (0xB4, 0x46, 127), (0x90, 1, 0)]:
        assert alsa.decode(alsa.encode(*msg)) == msg
    assert alsa.decode(alsa.encode(0x81, 5, 0)) == (0x91, 5, 0)


def test_hardware_override_moves_code():
    hw = HardwareMap()
    hw.assign("B.gain_press", 293)
    assert hw.lookup(293).cid == "B.gain_press"
    hw.assign("A.gain_press", 293)    # moved
    assert hw.lookup(293).cid == "A.gain_press"
    assert hw.controls["B.gain_press"].code is None


def test_mixxx_mapping_binds_everything():
    import re
    from s4bridge.mixxx import build_xml, build_js
    xml, js = build_xml(DEFAULT_PROFILE), build_js(DEFAULT_PROFILE)
    keys = set(re.findall(r"<key>(.*?)</key>", xml))
    assert "S4B.tempoMSB" in keys and "S4B.tempoLSB" in keys and "S4B.jog" in keys
    for k in keys:
        name = k.split(".")[-1]
        dyn = name.startswith(("hotcue", "sample", "fxKnob", "fxButton"))
        pat = (r"S4B\.shifted\." if ".shifted." in k else r"S4B\.") + name + r"\s*="
        assert dyn or re.search(pat, js), k


def test_jog_normalised_to_1024_per_turn():
    t, dev, out = make()
    t.jog_norm = 1024 / 512          # a wheel that reports 512 ticks per turn
    jog = BY_ID["L.jog"].code
    t.handle_event(jog, 100)
    t.handle_event(jog, 110)         # 10 raw ticks -> 20 normalised
    assert out[-1] == (0xB0, 0x02, 64 + 20)


def test_setup_mixxx_writes_controller_and_audio(tmp_path, monkeypatch):
    import xml.etree.ElementTree as ET
    from s4bridge import mixxx
    monkeypatch.setattr(mixxx, "mixxx_running", lambda: False)
    monkeypatch.setattr(mixxx, "s4_sinks", lambda: (mixxx.DEFAULT_MAIN, mixxx.DEFAULT_PHONES, True))
    (tmp_path / "mixxx.cfg").write_text("[Config]\nVersion 2.5.6\n\n[Controller]\nOther_Thing 1\n\n[Skin]\nshow_mixer 1\n")
    (tmp_path / "soundconfig.xml").write_text(
        '<!DOCTYPE SoundManagerConfig>\n<SoundManagerConfig api="ALSA" deck_count="2" latency="5" samplerate="96000">'
        '<SoundDevice name="Mbox 3 Pro Pro" portAudioIndex="3"><output channel="0" channel_count="2" index="0" type="Master"/>'
        '<input channel="2" channel_count="2" index="0" type="Vinyl Control"/></SoundDevice></SoundManagerConfig>')
    r = mixxx.setup_mixxx(DEFAULT_PROFILE, tmp_path)
    cfg = (tmp_path / "mixxx.cfg").read_text()
    assert "Kontrol_S4_MK1 1" in cfg and "Other_Thing 1" in cfg and "show_mixer 1" in cfg
    assert f"Kontrol_S4_MK1 {r['mapping']}" in cfg
    root = ET.parse(tmp_path / "soundconfig.xml").getroot()
    assert root.get("api") == "JACK Audio Connection Kit" and root.get("samplerate") == "96000"
    outs = {(d.get("name"), o.get("type")) for d in root for o in d.findall("output")}
    assert outs == {(mixxx.DEFAULT_MAIN, "Master"), (mixxx.DEFAULT_PHONES, "Headphones")}
    assert root.find("SoundDevice[@name='Mbox 3 Pro Pro']/input") is not None   # vinyl input kept
    assert (tmp_path / "mixxx.cfg.s4bridge-backup").exists()
    assert (tmp_path / "controllers" / "S4-Bridge.js").exists()


def test_silent_mixxx_sync(tmp_path, monkeypatch):
    from s4bridge import mixxx
    monkeypatch.setattr(mixxx, "mixxx_dir", lambda: tmp_path)
    monkeypatch.setattr(mixxx, "mixxx_running", lambda: False)
    (tmp_path / "mixxx.cfg").write_text("[Config]\nVersion 2.5.6\n")
    assert mixxx.sync_mapping_if_installed(DEFAULT_PROFILE) == "not-installed"     # never set up: hands off
    monkeypatch.setattr(mixxx, "s4_sinks", lambda: (mixxx.DEFAULT_MAIN, mixxx.DEFAULT_PHONES, True))
    mixxx.setup_mixxx(DEFAULT_PROFILE, tmp_path)
    snd_before = (tmp_path / "soundconfig.xml").read_text()
    assert mixxx.sync_mapping_if_installed(DEFAULT_PROFILE) == "current"
    p = copy.deepcopy(DEFAULT_PROFILE); p["map"]["deck.play"]["num"] = 0x55
    monkeypatch.setattr(mixxx, "mixxx_running", lambda: True)
    assert mixxx.sync_mapping_if_installed(p) == "mixxx-running"                  # won't touch a running Mixxx
    monkeypatch.setattr(mixxx, "mixxx_running", lambda: False)
    assert mixxx.sync_mapping_if_installed(p) == "updated"
    assert (tmp_path / "soundconfig.xml").read_text() == snd_before                # sound settings untouched


def test_soft_takeover_after_deck_flip():
    t, dev, out = make()
    L = BY_ID["L.tempo"].code
    t.handle_event(L, 100 << 5)              # deck A fader at 100
    t.handle_midi(0xB2, 0x51, 40)            # Mixxx says deck C's tempo is at 40
    t.toggle_deck("L")                       # flip to C: fader (100) != C (40)
    assert t.takeover["L"]
    assert dev.led_state["LED: Deck A: Tempo down"] == 31 and dev.led_state["LED: Deck A: Tempo up"] == 0
    out.clear()
    t.handle_event(L, 80 << 5)               # moving toward it: silent
    assert out == []
    t.handle_event(L, 39 << 5)               # crossed: picks up and sends
    assert not t.takeover["L"] and out and out[0][0] == 0xB2
    assert dev.led_state["LED: Deck A: Tempo down"] == 0


def test_brightness_scales_hardware_only():
    from s4bridge.hw.device import CaiaqDevice
    d = CaiaqDevice()
    written = {}
    d._leds = type("W", (), {"set": lambda self, n, v, force=False: written.__setitem__(n, v)})()
    d.brightness = 0.5
    d.set_led("x", 31)
    assert d.led_state["x"] == 31 and written["x"] == 16


def test_display_words_and_dot():
    t, dev, out = make()
    t.handle_midi(0xB0, 0x50, 106)              # "St" (stems)
    assert dev.led_state["LED: Deck A: Digit 1 - A"] == 31          # S
    assert dev.led_state["LED: Deck A: Digit 2 - G"] == 31          # t
    t.handle_midi(0xB0, 0x50, 8)
    t.handle_midi(0xB0, 0x54, 127)              # 8.  (Camelot 8B)
    assert dev.led_state["LED: Deck A: Digit 2 - dot"] == 31
    t.toggle_deck("L"); t.toggle_deck("L")      # flipping away and back keeps it
    assert dev.led_state["LED: Deck A: Digit 2 - dot"] == 31
