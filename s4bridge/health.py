# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Hardware health check: every link in the chain, in plain words.

S4 -> kernel driver -> input device permissions -> S4 Bridge -> MIDI port
   -> LEDs -> S4 audio outputs in PipeWire -> Mixxx mapping / controller / audio
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field

from .hw import alsa

OK, WARN, FAIL, INFO = "ok", "warn", "fail", "info"
UDEV_CMD = ("sudo install -m644 /usr/lib/udev/rules.d/70-s4bridge.rules /etc/udev/rules.d/ 2>/dev/null; "
            "sudo udevadm control --reload; sudo udevadm trigger")


@dataclass
class Check:
    title: str
    status: str
    detail: str
    fix: str = ""            # action key the UI knows how to run
    fix_label: str = ""
    command: str = ""        # shell command to show/copy when we can't fix it ourselves


def _sinks_blocks() -> list[dict]:
    try:
        out = subprocess.run(["pactl", "list", "sinks"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    blocks = []
    for chunk in re.split(r"^Sink #", out, flags=re.M)[1:]:
        desc = re.search(r"^\s*Description:\s*(.+)$", chunk, re.M)
        mute = re.search(r"^\s*Mute:\s*(\w+)", chunk, re.M)
        vol = re.search(r"^\s*Volume:.*?(\d+)%", chunk, re.M)
        blocks.append({"desc": desc.group(1).strip() if desc else "",
                       "mute": bool(mute and mute.group(1) == "yes"),
                       "vol": int(vol.group(1)) if vol else 100})
    return blocks


def run_checks(core) -> list[Check]:
    from . import mixxx

    checks: list[Check] = []
    demo = getattr(core, "demo", False)

    # 1. kernel driver / card
    card = alsa.find_card()
    if demo:
        checks.append(Check("S4 detected", INFO, "Demo mode: hardware checks skipped."))
    elif card:
        checks.append(Check("S4 detected", OK, f"Kernel driver snd-usb-caiaq has the S4 as ALSA card “{card}”."))
    else:
        checks.append(Check("S4 detected", FAIL,
                            "The kernel doesn't see the S4. Check the USB cable, and that the S4 is switched "
                            "on (button next to the USB socket on the back)."))

    # 2/3. input device + permissions + bridge connection
    if not demo:
        state, detail = core.status
        if state == "connected":
            checks.append(Check("Controls", OK, "S4 Bridge is reading every knob, fader and button."))
        elif state == "error" and "permission" in detail.lower():
            checks.append(Check("Controls", FAIL,
                                "The S4 is there but your user isn't allowed to read its controls. Install the "
                                "udev rule, then switch the S4 off and on.", command=UDEV_CMD))
        elif card:
            checks.append(Check("Controls", WARN,
                                "The S4's audio is up but its control surface isn't connected yet. Switch it "
                                "off and on; if that doesn't help, the kernel may lack CONFIG_SND_USB_CAIAQ_INPUT."))
        else:
            checks.append(Check("Controls", FAIL, "Waiting for the S4."))

    # 4. MIDI port
    if core.midi_error:
        checks.append(Check("MIDI port", FAIL, f"Couldn't create the virtual MIDI port: {core.midi_error}"))
    else:
        checks.append(Check("MIDI port", OK,
                            f"“Kontrol S4 MK1” is live (ALSA seq {core.midi.address}); DJ software can see it."))

    # 5. LEDs
    if not demo:
        if getattr(core.device, "_leds", None):
            checks.append(Check("LEDs", OK, "LED control is working.", fix="test_leds", fix_label="Test LEDs"))
        elif core.device.connected:
            checks.append(Check("LEDs", WARN, "Controls work but the LEDs can't be driven (ALSA control access)."))

    # 6. S4 audio outputs in PipeWire
    blocks = [b for b in _sinks_blocks() if "Kontrol S4" in b["desc"]]
    if demo:
        pass
    elif not blocks:
        checks.append(Check("S4 audio outputs", WARN if card else FAIL,
                            "PipeWire isn't showing the S4's outputs. In pavucontrol › Configuration, set the "
                            "Traktor Kontrol S4 profile to “Analog Stereo Duplex”.",
                            command="pavucontrol --tab=5"))
    else:
        names = {b["desc"] for b in blocks}
        muted = [b["desc"] for b in blocks if b["mute"] or b["vol"] == 0]
        have = ("Main" in " ".join(names), "Headphone" in " ".join(names))
        if muted:
            checks.append(Check("S4 audio outputs", WARN, "Muted or at 0% in PipeWire: " + ", ".join(muted)))
        elif all(have):
            checks.append(Check("S4 audio outputs", OK, "Main Out and Headphones Out are available."))
        else:
            checks.append(Check("S4 audio outputs", WARN,
                                "Only some S4 outputs are visible: " + ", ".join(sorted(names))
                                + ". Use the “Analog Stereo Duplex” profile in pavucontrol."))

    # 7. standalone mixer
    mx = getattr(core, "mixer", None)
    if mx is not None and core.settings.get("mixer_enabled"):
        st = mx.status
        if st.get("state") == "running":
            outs = st.get("outputs", {})
            if not all(outs.values()):
                checks.append(Check("Standalone mixer", WARN, "Mixing, but the S4's main out or headphones "
                                    "weren't found in PipeWire (see S4 audio outputs above)."))
            elif mixxx.mixxx_running():
                checks.append(Check("Standalone mixer", WARN, "Mixxx is open too. The two will fight over the "
                                    "S4's outputs and lights; stop the mixer or quit Mixxx."))
            else:
                checks.append(Check("Standalone mixer", OK, "Mixing: the S4 is working as a hardware mixer."))
        else:
            checks.append(Check("Standalone mixer", FAIL, st.get("error") or "Turned on but not running."))

    # 8. Mixxx
    folder = mixxx.mixxx_dir()
    cfg, snd = folder / "mixxx.cfg", folder / "soundconfig.xml"
    xml_path = folder / "controllers" / "Traktor-Kontrol-S4-MK1-S4-Bridge.midi.xml"
    js_path = folder / "controllers" / "S4-Bridge.js"
    setup = dict(fix="setup_mixxx", fix_label="Set up Mixxx")
    if not cfg.exists():
        checks.append(Check("Mixxx", INFO, "Mixxx hasn't been run on this computer yet (no settings found).",
                            **setup))
        return checks
    problems = []
    if not xml_path.exists() or not js_path.exists():
        problems.append("the S4 mapping isn't installed")
    else:
        try:
            if (xml_path.read_text() != mixxx.build_xml(core.profile)
                    or js_path.read_text() != mixxx.build_js(core.profile, 1024)):
                problems.append("the mapping installed in Mixxx doesn't match S4 Bridge's current mapping (updated app or edited profile)")
        except OSError:
            problems.append("the installed mapping can't be read")
    text = cfg.read_text(errors="replace")
    key = mixxx.MIDI_PORT_NAME.replace(" ", "_")
    if not re.search(rf"^\[Controller\][^\[]*^{key} 1\s*$", text, re.M | re.S):
        problems.append("the S4 controller isn't enabled")
    if not re.search(rf"^\[ControllerPreset\][^\[]*^{key} .*S4-Bridge\.midi\.xml\s*$", text, re.M | re.S):
        problems.append("the controller isn't using the S4 Bridge mapping")
    snd_text = snd.read_text(errors="replace") if snd.exists() else ""
    m = re.search(r'<SoundDevice name="([^"]+)"[^>]*>\s*<output[^>]*type="Master"', snd_text)
    main_dev = m.group(1) if m else ""
    if "Kontrol S4" not in main_dev:
        problems.append(f"Mixxx's Main output goes to “{main_dev or 'nothing'}”, not the S4")
    if problems:
        checks.append(Check("Mixxx", WARN, "Mixxx needs attention: " + "; ".join(problems) + ".", **setup))
    else:
        checks.append(Check("Mixxx", OK, "Mapping is current, controller enabled, audio goes to the S4."))
    return checks
