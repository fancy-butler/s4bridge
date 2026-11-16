"""Built-in USB driver: protocol decoding and the exact bytes sent to the S4.

The decoder was also checked against the Linux kernel's own S4 code on 15,000 random reports
(zero differences); these tests pin the behaviour down without needing the kernel source.
"""
import pytest

from s4bridge.hw import usb_s4
from s4bridge.hw.controls import all_led_names
from s4bridge.hw.usb_s4 import ABS_HAT0X, BTN_MISC, LED_INDEX, S4Parser, UsbDevice


def block(bid, payload=b""):
    b = bytearray(16)
    b[0], b[1] = bid >> 8, bid & 0xFF
    b[2:2 + len(payload)] = payload
    return bytes(b)


def word_block(bid, words):
    """words: {word offset: 12-bit value}"""
    b = bytearray(block(bid))
    for off, v in words.items():
        b[off * 2], b[off * 2 + 1] = v >> 8, v & 0xFF
    return bytes(b)


def test_buttons_are_bits_from_byte_4():
    p = S4Parser()
    pkt = bytearray(block(0))
    pkt[4] = 0b0000_0101   # buttons 0 and 2
    pkt[15] = 0b1000_0000  # button 95, the last one
    ev = dict(p.feed(bytes(pkt)))
    assert ev[BTN_MISC + 0] == 1 and ev[BTN_MISC + 2] == 1 and ev[BTN_MISC + 95] == 1
    assert ev[BTN_MISC + 1] == 0
    assert len(ev) == 96


def test_only_changes_are_reported():
    p = S4Parser()
    p.feed(block(0))
    pkt = bytearray(block(0))
    pkt[5] = 0b10    # button 9
    assert p.feed(bytes(pkt)) == [(BTN_MISC + 9, 1)]
    assert p.feed(bytes(pkt)) == []


def test_jogs_and_encoders():
    p = S4Parser()
    b = bytearray(block(1))
    b[8], b[9] = 0x03, 0xFF      # left jog: 10 bits = 1023
    b[12], b[13] = 0x01, 0x02    # right jog = 0x102
    b[3] = 0x0A                  # encoder 0 (low nibble)
    b[4] = 0x5C                  # encoders 1 (hi) and 2 (lo)
    ev = dict(p.feed(bytes(b)))
    assert ev[ABS_HAT0X + 36] == 1023 and ev[ABS_HAT0X + 37] == 0x102
    assert ev[ABS_HAT0X + 38] == 0xA and ev[ABS_HAT0X + 39] == 0x5 and ev[ABS_HAT0X + 40] == 0xC


def test_faders_are_big_endian_words():
    p = S4Parser()
    ev = dict(p.feed(word_block(2, {7: 0xABC, 3: 0x123})))
    assert ev[ABS_HAT0X + 7] == 0xABC     # crossfader
    assert ev[ABS_HAT0X + 2] == 0x123     # channel A volume


def test_unknown_block_drops_rest_of_report_like_the_kernel():
    p = S4Parser()
    ev = p.feed(block(9) + word_block(2, {7: 100}))
    assert ev == []


def test_partial_trailing_block_ignored():
    p = S4Parser()
    p.feed(word_block(2, {}))   # first report: every fader is new
    assert p.feed(word_block(2, {7: 5}) + b"\x00\x02\x01") == [(ABS_HAT0X + 7, 5)]


def test_led_table_covers_every_led_the_app_uses():
    assert set(all_led_names()) <= set(LED_INDEX)
    idx = list(LED_INDEX.values())
    assert len(idx) == len(set(idx)) and all(0 <= i < 256 for i in idx)


# ------------------------------------------------------------------ talking to a fake S4
class FakeS4:
    def __init__(self, kernel_attached=True):
        self.log = []
        self.kernel = kernel_attached
        self.reports = []

    def is_kernel_driver_active(self, i):
        return self.kernel

    def detach_kernel_driver(self, i):
        self.kernel = False
        self.log.append("detach")

    def attach_kernel_driver(self, i):
        self.kernel = True
        self.log.append("attach")

    def set_configuration(self, c):
        self.log.append(("config", c))

    def set_interface_altsetting(self, interface, alternate_setting):
        self.log.append(("alt", interface, alternate_setting))

    def write(self, ep, data, timeout=None):
        self.log.append(("w", ep, bytes(data)))
        return len(data)

    def read(self, ep, n, timeout=None):
        if ep == usb_s4.EP1_IN:
            return bytes([1, 15, 0]) + bytes(14)   # device info, firmware 15
        raise AssertionError("unexpected read")


@pytest.fixture
def fake_usb_util(monkeypatch):
    pytest.importorskip("usb")
    import usb.util
    calls = []
    monkeypatch.setattr(usb.util, "claim_interface", lambda d, i: calls.append(("claim", i)))
    monkeypatch.setattr(usb.util, "release_interface", lambda d, i: calls.append(("release", i)))
    monkeypatch.setattr(usb.util, "dispose_resources", lambda d: None)
    return calls


def test_open_sequence_matches_the_kernel(fake_usb_util):
    d, s4 = UsbDevice(), FakeS4()
    d._open(s4)
    assert s4.log == [
        "detach",
        ("config", 1),
        ("alt", 0, 1),
        ("w", usb_s4.EP1_OUT, b"\x01"),               # GET_DEVICE_INFO
        ("w", usb_s4.EP1_OUT, b"\x0b\x01\x0a\x05"),   # AUTO_MSG digital=1 analog=10 erp=5
    ]
    assert d.firmware == 15
    assert ("claim", 0) in fake_usb_util


def test_close_hands_the_s4_back_to_linux(fake_usb_util):
    d, s4 = UsbDevice(), FakeS4()
    d._open(s4)
    d._close(s4)
    assert s4.log[-1] == "attach" and s4.kernel
    s4b = FakeS4(kernel_attached=False)        # Mac/Windows: nothing to detach or reattach
    d._open(s4b)
    d._close(s4b)
    assert "attach" not in s4b.log and "detach" not in s4b.log


def test_led_writes_go_to_ep8_with_brightness():
    d, s4 = UsbDevice(), FakeS4()
    d._dev = s4
    d.set_led("LED: Master: Quant", 31)
    d.set_led("LED: Master: Quant", 31)      # unchanged: nothing sent
    d.brightness = 0.5
    d.set_led("LED: Master: Snap", 31)
    d.set_led("LED: Master: Master", 0)
    writes = [e for e in s4.log if e[0] == "w"]
    assert writes == [("w", usb_s4.EP8_OUT, bytes((10, 31))),
                      ("w", usb_s4.EP8_OUT, bytes((14, 16))),
                      ("w", usb_s4.EP8_OUT, bytes((12, 0)))]


def test_driver_choice(monkeypatch):
    from s4bridge.core import Core
    c = Core.__new__(Core)
    c.settings = {}
    monkeypatch.setattr("sys.platform", "linux")
    assert c.driver_choice() == "kernel"
    c.settings["driver"] = "usb"
    assert c.driver_choice() == "usb"
    for plat in ("darwin", "win32"):
        monkeypatch.setattr("sys.platform", plat)
        c.settings["driver"] = "kernel"          # can't exist there
        assert c.driver_choice() == "usb"
        c.settings.pop("driver")
        assert c.driver_choice() == "usb"


def test_extras_expose_bytes_the_kernel_ignores_without_changing_known_codes():
    from s4bridge.hw.usb_s4 import EXTRA_BASE, EXTRA_NAMES
    plain, extra = S4Parser(), S4Parser(extras=True)
    b = bytearray(word_block(2, {7: 300, 5: 1234}))      # word 5 is unread by the kernel
    known = plain.feed(bytes(b))
    both = extra.feed(bytes(b))
    assert [e for e in both if e[0] < EXTRA_BASE] == known
    extras = {c: v for c, v in both if c >= EXTRA_BASE}
    assert 1234 in extras.values()
    assert all(c in EXTRA_NAMES for c in extras)
    b0 = bytearray(block(0))
    b0[2] = 0x10                                            # a bit in a button byte the kernel skips
    assert any(c >= EXTRA_BASE and v == 0x10 for c, v in extra.feed(bytes(b0)))


class QuietS4(FakeS4):
    """Accepts the connection, then says nothing, until it's nudged `wake_on` times."""

    def __init__(self, wake_on=None):
        super().__init__(kernel_attached=False)
        self.wake_on, self.nudges = wake_on, 0

    def write(self, ep, data, timeout=None):
        if ep == usb_s4.EP1_OUT and bytes(data)[:1] == b"\x0b":
            self.nudges += 1
        return super().write(ep, data, timeout)

    def read(self, ep, n, timeout=None):
        import usb.core
        if ep == usb_s4.EP4_IN:
            if self.wake_on is not None and self.nudges >= self.wake_on:
                return block(0)
            raise usb.core.USBTimeoutError("quiet")
        return super().read(ep, n, timeout)


def _run_pump(dev, d, secs):
    import threading
    import time
    out = {}
    d._stop = threading.Event()

    def go():
        try:
            d._pump(dev)
            out["r"] = "stopped"
        except UsbDevice.Silent:
            out["r"] = "silent"
    t = threading.Thread(target=go)
    t.start()
    time.sleep(secs)
    d._stop.set()
    t.join(2)
    return out.get("r")


def test_stuck_s4_gets_nudged_and_wakes(monkeypatch):
    pytest.importorskip("usb")
    monkeypatch.setattr(UsbDevice, "WAKE_AFTER", 0.05)
    d, s4 = UsbDevice(), QuietS4(wake_on=1)     # nudge #1 = first re-send of AUTO_MSG
    events = []
    d.on_event = lambda c, v: events.append(c)
    assert _run_pump(s4, d, 0.5) == "stopped"
    assert s4.nudges == 1 and events


def test_s4_that_never_answers_triggers_reconnect(monkeypatch):
    pytest.importorskip("usb")
    monkeypatch.setattr(UsbDevice, "WAKE_AFTER", 0.05)
    assert _run_pump(QuietS4(), UsbDevice(), 0.6) == "silent"


def test_idle_s4_after_first_report_is_left_alone(monkeypatch):
    pytest.importorskip("usb")
    import usb.core
    monkeypatch.setattr(UsbDevice, "WAKE_AFTER", 0.05)

    class OnceThenIdle(FakeS4):
        sent = False

        def read(self, ep, n, timeout=None):
            if ep == usb_s4.EP4_IN:
                if not self.sent:
                    self.sent = True
                    return block(0)
                raise usb.core.USBTimeoutError("idle")
            return super().read(ep, n, timeout)
    s4 = OnceThenIdle(kernel_attached=False)
    assert _run_pump(s4, UsbDevice(), 0.5) == "stopped"
    assert not any(e[0] == "w" and e[2][:1] == b"\x0b" for e in s4.log)
