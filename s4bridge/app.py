# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Entry point: `s4bridge` (GUI), `s4bridge --headless` (background service)."""
from __future__ import annotations

import argparse
import signal
import sys
import threading

from . import __version__


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="s4bridge", description="Traktor Kontrol S4 MK1 → MIDI bridge")
    ap.add_argument("--demo", action="store_true", help="no hardware: drive a simulated S4 from the screen")
    ap.add_argument("--headless", action="store_true", help="run without a window (for a systemd user service)")
    ap.add_argument("--profile", help="mapping profile JSON to load")
    ap.add_argument("--setup-mixxx", action="store_true",
                    help="install the Mixxx mapping, enable the S4 and route Mixxx audio to it, then exit")
    ap.add_argument("--minimized", action="store_true", help="start hidden in the system tray")
    ap.add_argument("--screenshot", help=argparse.SUPPRESS)
    ap.add_argument("--page", type=int, default=0, help=argparse.SUPPRESS)
    ap.add_argument("--version", action="version", version=f"S4 Bridge {__version__}")
    args = ap.parse_args(argv)

    if args.setup_mixxx:
        from .engine.profile import load_profile, load_settings
        from .mixxx import MixxxSetupError, setup_mixxx
        path = args.profile or load_settings().get("profile")
        try:
            r = setup_mixxx(load_profile(path))
        except MixxxSetupError as e:
            print(f"s4bridge: {e}", file=sys.stderr)
            return 1
        print(f"Mixxx set up in {r['folder']}\n  Main       -> {r['main']}\n  Headphones -> {r['phones']}")
        return 0

    if not args.headless:
        from PySide6.QtWidgets import QApplication
        app = QApplication(sys.argv[:1])
        from .ui.tray import SingleInstance
        single = SingleInstance()
        if not args.screenshot and single.already_running():
            print("S4 Bridge is already running; showing it.")
            return 0

    from .core import Core
    core = Core(demo=args.demo, profile_path=args.profile)

    if args.headless:
        def log(state, detail):
            print(f"[s4bridge] {state}: {detail}", flush=True)
        core.status_listeners.append(log)
        if core.midi_error:
            print(f"[s4bridge] MIDI unavailable: {core.midi_error}", file=sys.stderr)
        else:
            print(f"[s4bridge] MIDI port S4 Bridge:Kontrol S4 MK1 at {core.midi.address}", flush=True)
        done = threading.Event()
        signal.signal(signal.SIGINT, lambda *_: done.set())
        signal.signal(signal.SIGTERM, lambda *_: done.set())
        core.start()
        done.wait()
        core.stop()
        return 0

    from PySide6.QtCore import QTimer
    from .ui import theme
    from .ui.mainwindow import MainWindow

    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("S4 Bridge")
    app.setDesktopFileName("s4bridge")
    app.setStyle("Fusion")
    app.setStyleSheet(theme.QSS)
    win = MainWindow(core)
    single.wake.connect(win.show_window)
    if not (args.minimized and win.tray):
        win.show()
    core.start()
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    if args.screenshot:
        win.go(args.page)
        def shoot():
            win.grab().save(args.screenshot)
            app.quit()
        QTimer.singleShot(1800, shoot)
    rc = app.exec()
    core.stop()
    return rc
