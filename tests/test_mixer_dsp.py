import numpy as np
import pytest

dsp = pytest.importorskip("s4bridge.mixer.dsp")

FS = 48000
N = 4096


def tone(f, amp=0.5, n=N):
    t = np.arange(n) / FS
    s = amp * np.sin(2 * np.pi * f * t)
    return np.vstack([s, s])


def rms(x):
    return float(np.sqrt(np.mean(x[:, N // 2:] ** 2)))      # skip filter settling


def run(mixer, inputs, blocks=4):
    out = None
    for _ in range(blocks):
        out = mixer.process(inputs, N)
    return out


def test_flat_strip_passes_unchanged():
    m = dsp.Mixer(FS)
    m.set({"strip": "A", "volume": 1.0})
    main, _ = run(m, {"A": tone(1000)})
    assert abs(rms(main) - rms(tone(1000))) < 0.01


def test_low_kill_removes_bass_keeps_highs():
    m = dsp.Mixer(FS)
    m.set({"strip": "C", "volume": 1.0, "low": 0.0})
    bass, _ = run(m, {"C": tone(60)})
    m2 = dsp.Mixer(FS)
    m2.set({"strip": "C", "volume": 1.0, "low": 0.0})
    highs, _ = run(m2, {"C": tone(6000)})
    assert rms(bass) < rms(tone(60)) * 0.1          # at least -20 dB
    assert rms(highs) > rms(tone(6000)) * 0.9


def test_filter_left_is_lowpass_right_is_highpass():
    lp = dsp.Mixer(FS); lp.set({"strip": "A", "volume": 1.0, "filter": 0.0})
    hp = dsp.Mixer(FS); hp.set({"strip": "A", "volume": 1.0, "filter": 1.0})
    assert rms(run(lp, {"A": tone(5000)})[0]) < 0.02
    assert rms(run(hp, {"A": tone(100)})[0]) < 0.02
    off = dsp.Mixer(FS); off.set({"strip": "A", "volume": 1.0, "filter": 0.51})
    assert abs(rms(run(off, {"A": tone(5000)})[0]) - rms(tone(5000))) < 0.01


def test_crossfader_sides():
    m = dsp.Mixer(FS)
    for s in "AB":
        m.set({"strip": s, "volume": 1.0})
    m.set({"xfader": 0.0})                          # hard left: A plays, B silent
    main, _ = run(m, {"B": tone(1000)})
    assert rms(main) < 1e-3
    main, _ = run(m, {"A": tone(1000)})
    assert rms(main) > 0.3


def test_cue_goes_to_phones_not_main():
    m = dsp.Mixer(FS)
    m.set({"strip": "D", "volume": 0.0, "cue": True})
    m.set({"cue_mix": 0.0})
    main, phones = run(m, {"D": tone(1000)})
    assert rms(main) < 1e-3 and rms(phones) > 0.3


def test_limiter_never_exceeds_full_scale():
    m = dsp.Mixer(FS)
    for s in "ABCD":
        m.set({"strip": s, "volume": 1.0, "gain_db": 12})
    main, phones = run(m, {s: tone(200, amp=0.9) for s in "ABCD"})
    assert np.max(np.abs(main)) <= 1.0 and np.max(np.abs(phones)) <= 1.0
    assert m.clipped                                 # but it tells you it was driven too hard


def test_meters_report_levels():
    m = dsp.Mixer(FS)
    m.set({"strip": "B", "volume": 1.0})
    run(m, {"B": tone(1000, amp=0.5)})
    assert 0.4 < m.peaks["B"] < 0.6 and m.peaks["A"] == 0.0
