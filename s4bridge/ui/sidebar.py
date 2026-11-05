# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Live mini deck panel for the bottom of the sidebar."""
from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import theme

SIDE_DECKS = {"L": ("A", "C"), "R": ("B", "D")}


class DeckMini(QWidget):
    """Two deck tiles (click to flip), live level, shift dot, MIDI in/out lights."""

    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setFixedHeight(150)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click a side to flip it between decks")
        self.last_in = 0.0
        self.last_out = 0.0
        self._level = {"L": 0.0, "R": 0.0}
        t = QTimer(self)
        t.timeout.connect(self.update)
        t.start(40)

    def ping(self, kind: str):
        if kind == "out":
            self.last_out = time.time()
        elif kind == "midi_in":
            self.last_in = time.time()

    def _meter(self, deck: str) -> float:
        st = self.core.device.led_state
        lit = sum(1 for i in range(1, 7) if st.get(f"LED: Channel {deck}: Meter {i}", 0))
        return lit / 6

    def _tile(self, side: str) -> QRectF:
        w = (self.width() - 10) / 2
        return QRectF(0 if side == "L" else w + 10, 0, w, 104)

    def mousePressEvent(self, e):
        for side in ("L", "R"):
            if self._tile(side).contains(e.position()):
                self.core.translator.toggle_deck(side)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tr = self.core.translator
        connected = self.core.device.connected
        for side in ("L", "R"):
            r = self._tile(side)
            deck = tr.active[side]
            other = [d for d in SIDE_DECKS[side] if d != deck][0]
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, QColor("#22252d"))
            g.setColorAt(1, QColor("#191b21"))
            p.setPen(QPen(QColor(theme.LINE), 1))
            p.setBrush(g)
            p.drawRoundedRect(r, 12, 12)
            # big deck letter
            f = QFont(self.font())
            f.setPixelSize(44)
            f.setWeight(QFont.Black)
            p.setFont(f)
            p.setPen(QColor(theme.ACCENT) if connected else QColor(theme.MUTED))
            p.drawText(r.adjusted(0, -6, 0, -20), Qt.AlignCenter, deck)
            # side label + the alternate deck
            f.setPixelSize(10)
            f.setWeight(QFont.DemiBold)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
            p.setFont(f)
            p.setPen(QColor(theme.MUTED))
            p.drawText(r.adjusted(10, 8, -10, 0), Qt.AlignLeft | Qt.AlignTop, "LEFT" if side == "L" else "RIGHT")
            p.drawText(r.adjusted(10, 8, -10, 0), Qt.AlignRight | Qt.AlignTop, f"↔ {other}")
            # shift dot
            if tr.shift.get(side):
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#f2f4f8"))
                p.drawEllipse(r.center().x() - 3, r.bottom() - 30, 6, 6)
            # live level (smoothed)
            target = self._meter(deck)
            self._level[side] += (target - self._level[side]) * (0.6 if target > self._level[side] else 0.15)
            bar = QRectF(r.left() + 12, r.bottom() - 16, r.width() - 24, 5)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#2a2e37"))
            p.drawRoundedRect(bar, 2.5, 2.5)
            if self._level[side] > 0.01:
                lg = QLinearGradient(bar.topLeft(), bar.topRight())
                lg.setColorAt(0, QColor(theme.ACCENT_2))
                lg.setColorAt(0.8, QColor(theme.ACCENT_2))
                lg.setColorAt(1, QColor(theme.ACCENT))
                p.setBrush(lg)
                p.drawRoundedRect(QRectF(bar.left(), bar.top(), bar.width() * self._level[side], bar.height()), 2.5, 2.5)
        # MIDI activity lights
        now = time.time()
        f = QFont(self.font())
        f.setPixelSize(10)
        f.setWeight(QFont.DemiBold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        p.setFont(f)
        y = 128
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(f)
        gap = 22
        widths = [14 + fm.horizontalAdvance(l) for l in ("MIDI IN", "MIDI OUT")]
        x = (self.width() - (sum(widths) + gap)) / 2
        for i, (label, t, col) in enumerate([("MIDI IN", self.last_in, theme.ACCENT_2), ("MIDI OUT", self.last_out, theme.ACCENT)]):
            a = max(0.0, 1 - (now - t) / 0.25)
            c = QColor(col)
            c.setAlphaF(0.25 + 0.75 * a)
            p.setPen(Qt.NoPen)
            p.setBrush(c if a > 0 else QColor("#2a2e37"))
            p.drawEllipse(QRectF(x, y - 4, 8, 8))
            p.setPen(QColor(theme.TEXT) if a > 0 else QColor(theme.MUTED))
            p.drawText(int(x + 14), y + 4, label)
            x += widths[i] + gap
        p.end()
