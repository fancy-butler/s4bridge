# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Things that touch the system outside our own config: the udev rule, and a diagnostics report."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

UDEV_RULE = (
    "# S4 Bridge: let the logged-in user read the Traktor Kontrol S4 MK1's\n"
    "# control events (snd-usb-caiaq input device) without root, and stop it\n"
    "# being treated as a game controller.\n"
    'SUBSYSTEM=="input", ATTRS{idVendor}=="17cc", ATTRS{idProduct}=="baff", TAG+="uaccess", '
    'ENV{ID_INPUT_JOYSTICK}=""\n'
)
RULE_NAME = "70-s4bridge.rules"
RULE_DIRS = (Path("/etc/udev/rules.d"), Path("/usr/lib/udev/rules.d"), Path("/lib/udev/rules.d"))


def udev_rule_installed() -> bool:
    return any((d / RULE_NAME).exists() for d in RULE_DIRS)


def udev_install_script() -> str:
    """Shell run as root: write the rule, reload, re-apply to the S4 that's already plugged in."""
    return ("set -e\n"
            f"cat > /etc/udev/rules.d/{RULE_NAME} <<'S4RULE'\n{UDEV_RULE}S4RULE\n"
            f"chmod 644 /etc/udev/rules.d/{RULE_NAME}\n"
            "udevadm control --reload\n"
            "udevadm trigger --subsystem-match=input --action=change\n")


def can_elevate() -> bool:
    return shutil.which("pkexec") is not None


def install_udev_rule(timeout: float = 120) -> tuple[bool, str]:
    """Ask for the admin password (polkit) and install the rule. Returns (ok, message)."""
    if not can_elevate():
        return False, "pkexec isn't installed, so this needs a terminal (see the command on the Health page)."
    try:
        r = subprocess.run(["pkexec", "/bin/sh", "-c", udev_install_script()],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "Timed out waiting for the password prompt."
    except OSError as e:
        return False, str(e)
    if r.returncode == 0:
        return True, "Done. The S4 should connect within a couple of seconds."
    if r.returncode in (126, 127):  # dismissed / not authorised
        return False, "Cancelled."
    return False, (r.stderr or r.stdout or f"pkexec exited with {r.returncode}").strip()


# ------------------------------------------------------------------ diagnostics report
def _run(cmd: list[str], timeout: float = 3) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _os_name() -> str:
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    return platform.system()


def _audio_server() -> str:
    for line in _run(["pactl", "info"]).splitlines():
        if line.startswith("Server Name:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def _mixxx_version() -> str:
    out = _run(["mixxx", "--version"], timeout=4) if shutil.which("mixxx") else ""
    for line in out.splitlines():
        if "mixxx" in line.lower():
            return line.strip()
    return "installed" if shutil.which("mixxx") else "not installed"


def build_report(core) -> str:
    """Markdown block for a GitHub issue. No personal data: no paths with usernames, no file contents."""
    from . import __version__
    from .health import run_checks
    try:
        from PySide6 import __version__ as qt
    except Exception:  # noqa: BLE001
        qt = "?"
    state, detail = getattr(core, "status", ("?", ""))
    lines = [
        "### S4 Bridge diagnostics",
        "",
        "| | |",
        "|---|---|",
        f"| S4 Bridge | {__version__}{' (demo mode)' if getattr(core, 'demo', False) else ''} |",
        f"| OS | {_os_name()} |",
        f"| Kernel | {platform.release()} |",
        f"| Desktop | {os.environ.get('XDG_CURRENT_DESKTOP', '?')} / {os.environ.get('XDG_SESSION_TYPE', '?')} |",
        f"| Python / PySide6 | {platform.python_version()} / {qt} |",
        f"| Audio server | {_audio_server()} |",
        f"| Mixxx | {_mixxx_version()} |",
        f"| snd-usb-caiaq loaded | {'yes' if Path('/sys/module/snd_usb_caiaq').exists() else 'no'} |",
        f"| udev rule | {'installed' if udev_rule_installed() else 'missing'} |",
        f"| Connection | {state}{(': ' + detail) if detail else ''} |",
        f"| Standalone mixer | {'on' if core.settings.get('mixer_enabled') else 'off'} |",
        "",
        "**Health check**",
        "",
    ]
    icon = {"ok": "✅", "warn": "⚠️", "fail": "❌", "info": "ℹ️"}
    try:
        for c in run_checks(core):
            lines.append(f"- {icon.get(c.status, '•')} **{c.title}**: {c.detail}")
    except Exception as e:  # noqa: BLE001
        lines.append(f"- health check crashed: {e!r}")
    home = str(Path.home())
    return "\n".join(lines).replace(home, "~") + "\n"
