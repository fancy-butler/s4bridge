# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""System tray icon, start-at-login, and single-instance handling."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import theme

AUTOSTART = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart" / "s4bridge.desktop"
SOCKET_NAME = f"s4bridge-{os.getuid()}"


# ------------------------------------------------------------------ autostart
def _exec_line() -> str:
    exe = shutil.which("s4bridge")
    if exe:
        return f"{exe} --minimized"
    return f"{sys.executable} -m s4bridge --minimized"


def autostart_enabled() -> bool:
    return AUTOSTART.exists()


def set_autostart(on: bool):
    if on:
        AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART.write_text(
            "[Desktop Entry]\nType=Application\nName=S4 Bridge\n"
            "Comment=Traktor Kontrol S4 MK1 to MIDI bridge\n"
            f"Exec={_exec_line()}\nIcon=s4bridge\nTerminal=false\n"
            "X-GNOME-Autostart-enabled=true\nX-KDE-autostart-after=panel\n")
    else:
        try:
            AUTOSTART.unlink()
        except FileNotFoundError:
            pass


# ------------------------------------------------------------------ single instance
class SingleInstance(QObject):
    """If S4 Bridge is already running, wake that one up instead of starting twice
    (two copies would fight over the controller)."""
    wake = Signal()

    def __init__(self):
        super().__init__()
        self.server = None

    def already_running(self) -> bool:
        sock = QLocalSocket()
        sock.connectToServer(SOCKET_NAME)
        if sock.waitForConnected(300):
            sock.write(b"show")
            sock.flush()
            sock.waitForBytesWritten(300)
            sock.disconnectFromServer()
            return True
        QLocalServer.removeServer(SOCKET_NAME)
        self.server = QLocalServer()
        self.server.newConnection.connect(self._on_conn)
        self.server.listen(SOCKET_NAME)
        return False

    def _on_conn(self):
        c = self.server.nextPendingConnection()
        if c:
            c.readyRead.connect(lambda: (c.readAll(), self.wake.emit()))


# ------------------------------------------------------------------ tray
class Tray(QSystemTrayIcon):
    @staticmethod
    def available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def __init__(self, win):
        super().__init__(theme.icon("disc-3", theme.MUTED, 64), win)
        self.win = win
        m = QMenu()
        self.status_act = QAction("Starting…", m)
        self.status_act.setEnabled(False)
        m.addAction(self.status_act)
        self.decks_act = QAction("", m)
        self.decks_act.setEnabled(False)
        m.addAction(self.decks_act)
        m.addSeparator()
        m.addAction(theme.icon("eye", theme.TEXT, 16), "Open S4 Bridge", win.show_window)
        m.addAction(theme.icon("zap", theme.TEXT, 16), "Set up Mixxx", win.mapping_page._setup_mixxx)
        m.addAction(theme.icon("heart-pulse", theme.TEXT, 16), "Health check",
                    lambda: (win.show_window(), win.go(3)))
        m.addAction(theme.icon("lightbulb", theme.TEXT, 16), "Test LEDs", win.core.test_leds)
        m.addSeparator()
        m.addAction(theme.icon("power", theme.TEXT, 16), "Quit S4 Bridge", win.quit_app)
        m.aboutToShow.connect(self._refresh_decks)
        self.setContextMenu(m)
        self.activated.connect(self._activated)
        self.setToolTip("S4 Bridge")
        self.show()

    def _refresh_decks(self):
        a = self.win.core.translator.active
        self.decks_act.setText(f"Left: Deck {a['L']}   ·   Right: Deck {a['R']}")

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.win.isVisible() and not self.win.isMinimized():
                self.win.hide()
            else:
                self.win.show_window()

    def set_state(self, state: str, detail: str):
        label = {"connected": "S4 connected", "waiting": "Waiting for the S4",
                 "error": "Problem: open Health check", "starting": "Starting…"}.get(state, state)
        if self.win.core.demo and state == "connected":
            label = "Demo mode"
        color = {"connected": theme.ACCENT, "error": theme.BAD}.get(state, theme.MUTED)
        self.setIcon(theme.icon("disc-3", color, 64))
        self.status_act.setText(label)
        self.setToolTip(f"S4 Bridge: {label}" + (f"\n{detail}" if detail else ""))
        prev = getattr(self, "_prev", None)
        self._prev = state
        # stay out of the way: only speak up when something is wrong
        if prev is not None and prev != state and state == "error" and not self.win.isVisible():
            self.showMessage("S4 Bridge", label, theme.icon("disc-3", color, 32), 3000)
