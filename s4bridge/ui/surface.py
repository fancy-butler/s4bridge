# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
"""Live, interactive drawing of the S4 MK1.

Shows every control moving and every LED exactly as the bridge is driving
it.  It is also a virtual controller: click, drag and scroll to send the same
events the hardware would (that's how demo mode works).
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)
from PySide6.QtWidgets import QToolTip, QWidget

from ..hw.controls import (BUTTON, CANVAS_H, CANVAS_W, ENCODER, INDICATORS, JOG, JOG_RANGE, POT, TOUCH,
                           Control)
from . import theme

BLUE, GREEN, AMBER, WHITE, RED = (QColor("#3d9bff"), QColor("#3ddc84"), QColor("#ff8a1f"),
                                  QColor("#f2f4f8"), QColor("#ff4d3d"))

PAD_COLOR = {
    "play": GREEN, "loop_in": GREEN, "loop_out": GREEN, "cue": AMBER, "sync": AMBER,
    "shift": WHITE, "load": WHITE, "deck_toggle": WHITE, "tempo_up": AMBER, "tempo_down": AMBER,
    "loop_rec": BLUE, "loop_play": BLUE, "snap": WHITE, "master": WHITE, "quant": WHITE,
    "loop_size": WHITE, "loop_undo": WHITE, "browse_btn": WHITE,
}
DEFAULT_RAW = {"volume": 0}


def lit_color(c: Control) -> QColor:
    if c.func.startswith("sample"):
        return AMBER
    return PAD_COLOR.get(c.func, AMBER)


class Surface(QWidget):
    hovered = Signal(str)
    picked = Signal(str)

    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setMouseTracking(True)
        self.setMinimumSize(420, 270)
        self.selected: str | None = None
        self.hover: str | None = None
        self.activity: dict[str, float] = {}
        self._drag = None
        self._dirty = True
        self._sim_raw: dict[int, int] = {}
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(33)

    # ------------------------------------------------------------ geometry
    def _xf(self):
        s = min(self.width() / CANVAS_W, self.height() / CANVAS_H)
        ox = (self.width() - CANVAS_W * s) / 2
        oy = min(8.0, (self.height() - CANVAS_H * s) / 2)
        return s, ox, oy

    def _to_canvas(self, p: QPointF) -> QPointF:
        s, ox, oy = self._xf()
        return QPointF((p.x() - ox) / s, (p.y() - oy) / s)

    @staticmethod
    def _radius(c: Control) -> float:
        return {"knob": 15, "enc": 16, "small": 9, "jog": 132}.get(c.shape, 14)

    def _hit(self, p: QPointF) -> Control | None:
        best, bd = None, 1e9
        for c in self.core.hw.controls.values():
            if c.shape == "none":
                continue
            if c.shape in ("pad",):
                w, h = (52, 32) if c.area in "LR" else (40, 24)
                if abs(p.x() - c.x) <= w / 2 and abs(p.y() - c.y) <= h / 2:
                    return c
                continue
            if c.shape in ("fader", "hfader"):
                if abs(p.x() - c.x) <= max(c.w, 18) / 2 + 8 and abs(p.y() - c.y) <= max(c.h, 18) / 2 + 8:
                    return c
                continue
            d = math.hypot(p.x() - c.x, p.y() - c.y)
            r = self._radius(c) + 4
            if d <= r and d < bd:
                best, bd = c, d
        return best

    # ------------------------------------------------------------ state
    def mark(self, cid: str):
        self.activity[cid] = time.time()
        self._dirty = True

    def _tick(self):
        if self._dirty or self.activity or self.core.device.led_state:
            now = time.time()
            for k in [k for k, t in self.activity.items() if now - t > 0.8]:
                del self.activity[k]
            self.update()
            self._dirty = False

    def raw(self, c: Control) -> int:
        if c.code is None:
            return self._sim_raw.get(id(c), 0)
        v = self.core.translator.raw.get(c.code)
        if v is None:
            if c.kind == POT:
                return DEFAULT_RAW.get(c.func, 2048)
            return 0
        return v

    def led(self, name: str) -> float:
        v = self.core.device.led_state.get(name, 0) / 31.0
        return v * getattr(self.core.device, "brightness", 1.0) if v else 0.0

    def inject(self, c: Control, value: int):
        if c.code is None:
            return
        self.core.translator.handle_event(c.code, value)
        self.mark(c.cid)

    # ------------------------------------------------------------ painting
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s, ox, oy = self._xf()
        p.translate(ox, oy)
        p.scale(s, s)
        self._board(p)
        for ind in INDICATORS:
            self._indicator(p, ind)
        for c in self.core.hw.controls.values():
            self._control(p, c)
        p.end()

    def _board(self, p: QPainter):
        # chassis
        g = QLinearGradient(0, 0, 0, 680)
        g.setColorAt(0, QColor("#24262b"))
        g.setColorAt(1, QColor("#141518"))
        p.setPen(QPen(QColor("#33363d"), 1.5))
        p.setBrush(g)
        p.drawRoundedRect(QRectF(4, 4, CANVAS_W - 8, 668), 18, 18)
        # top FX/mixer-top strip
        p.setBrush(QColor("#1a1b1f"))
        p.setPen(QPen(QColor("#2c2f36"), 1))
        p.drawRoundedRect(QRectF(16, 18, CANVAS_W - 32, 82), 10, 10)
        for x in (397, 803):
            p.drawLine(QPointF(x, 22), QPointF(x, 96))
        # deck plates
        for x in (16, 805):
            dg = QLinearGradient(x, 108, x + 380, 660)
            dg.setColorAt(0, QColor("#202227"))
            dg.setColorAt(1, QColor("#17181c"))
            p.setBrush(dg)
            p.drawRoundedRect(QRectF(x, 108, 379, 552), 12, 12)
        # mixer well
        p.setBrush(QColor("#0d0e10"))
        p.drawRoundedRect(QRectF(403, 108, 394, 552), 12, 12)
        p.setPen(QPen(QColor("#22252b"), 1))
        for x in (476, 556, 646, 727):
            p.drawLine(QPointF(x, 116), QPointF(x, 600))
        # center column
        p.setBrush(QColor("#1b1e24"))
        p.setPen(QPen(QColor("#2c3038"), 1))
        p.drawRoundedRect(QRectF(560, 112, 84, 46), 8, 8)
        p.drawRoundedRect(QRectF(560, 226, 84, 142), 8, 8)
        # display panels & sample frames
        for dx in (0, 712):
            p.setBrush(QColor("#0b0c0e"))
            p.setPen(QPen(QColor("#2a2d33"), 1))
            p.drawRoundedRect(QRectF(130 + dx + (0 if dx == 0 else 1), 392 + (0 if dx == 0 else 5), 232, 36), 6, 6)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#a8432c"), 1.4))
            off = 731 if dx else 0
            p.drawRoundedRect(QRectF(112 + off, 496 + (4 if dx else 0), 248, 38), 7, 7)
        # front panel
        p.setPen(QPen(QColor("#2b2e34"), 1.5))
        p.setBrush(QColor("#121316"))
        p.drawRoundedRect(QRectF(4, 684, CANVAS_W - 8, 72), 12, 12)
        # labels
        self._label(p, 377, 82, "FX 1", 13, QColor("#555a64"), bold=True)
        self._label(p, 1106, 82, "FX 2", 13, QColor("#555a64"), bold=True)
        self._label(p, 602, 234, "LOOP RECORDER", 6)
        self._label(p, 602, 193, "MASTER", 5.5)
        self._label(p, 52, 652, "TEMPO", 8)
        self._label(p, 1146, 652, "TEMPO", 8)
        self._label(p, 78, 430, "OFFSET", 7)
        self._label(p, 1124, 434, "OFFSET", 7)
        for dx, dy in ((0, 0), (731, 4)):
            self._label(p, 240 + dx, 435 + dy, "LOOP", 6.5)
            self._label(p, 238 + dx, 489 + dy, "SAMPLES", 8, QColor("#c9563a"), bold=True)
        for ch, x in (("C", 435), ("A", 516), ("B", 686), ("D", 772)):
            self._label(p, x + 3, 24, "GAIN", 6)
            self._label(p, x + 22, 413, ch, 13, QColor("#c9ccd3"), bold=True)
        self._label(p, 600, 24, "LEVEL", 6)
        self._knob_body(p, 600, 48, 13, 0.75, QColor("#666b75"))
        for xx in (585, 615):
            for k in range(5):
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#22252c"))
                p.drawRect(QRectF(xx - 1.5 + (0 if xx < 600 else 0), 34 + k * 7, 3, 4))
        self._label(p, 40, 700, "TRAKTOR KONTROL S4 · MK1", 9, QColor("#666b75"), bold=True, align_left=True)
        self._label(p, 780, 750, "PHONES", 6.5)
        self._jack(p, 780, 734)
        self._label(p, 990, 750, "CUE VOL", 6.5)
        self._knob_body(p, 990, 720, 13, 0.6, QColor("#555a64"))

    def _jack(self, p, x, y):
        p.setPen(QPen(QColor("#3a3d44"), 2))
        p.setBrush(QColor("#050506"))
        p.drawEllipse(QPointF(x, y - 12), 8, 8)

    def _label(self, p, x, y, text, size=7, color=None, bold=False, align_left=False):
        f = QFont(p.font())
        f.setPointSizeF(size)
        f.setBold(bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 0.6)
        p.setFont(f)
        p.setPen(color or QColor("#7d828d"))
        if align_left:
            p.drawText(QPointF(x, y), text)
        else:
            p.drawText(QRectF(x - 80, y - 10, 160, 20), Qt.AlignCenter, text)

    def _knob_body(self, p, x, y, r, frac, ring=None):
        g = QRadialGradient(x - r * 0.3, y - r * 0.4, r * 1.6)
        g.setColorAt(0, QColor("#3a3c42"))
        g.setColorAt(1, QColor("#0e0f11"))
        p.setPen(QPen(QColor("#050506"), 1.5))
        p.setBrush(g)
        p.drawEllipse(QPointF(x, y), r, r)
        ang = math.radians(225 - 270 * frac)
        p.setPen(QPen(QColor("#f2f2f2"), 2.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x + math.cos(ang) * r * 0.35, y - math.sin(ang) * r * 0.35),
                   QPointF(x + math.cos(ang) * r * 0.9, y - math.sin(ang) * r * 0.9))

    def _focus_ring(self, p, c: Control, r):
        now = time.time()
        if c.cid in self.activity:
            a = max(0.0, 1 - (now - self.activity[c.cid]) / 0.8)
            col = QColor(theme.ACCENT)
            col.setAlphaF(0.85 * a)
            p.setPen(QPen(col, 3))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(c.x, c.y), r + 5, r + 5)
        if c.cid == self.selected:
            p.setPen(QPen(QColor(theme.ACCENT), 2, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(c.x, c.y), r + 9, r + 9)
        elif c.cid == self.hover:
            p.setPen(QPen(QColor(255, 255, 255, 70), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(c.x, c.y), r + 6, r + 6)

    def _control(self, p: QPainter, c: Control):
        sh = c.shape
        if sh == "none":
            return
        unknown = c.code is None
        if sh == "knob":
            r = 12 if c.area in "ABCD" else (13 if c.area in ("G", "FX1", "FX2") else 15)
            frac = self.raw(c) / 4095
            # value arc
            p.setPen(QPen(QColor("#2a2d34"), 3, Qt.SolidLine, Qt.RoundCap))
            a = r + 5
            p.drawArc(QRectF(c.x - a, c.y - a, 2 * a, 2 * a), -45 * 16, 270 * 16)
            col = QColor(theme.ACCENT_2 if c.area in "ABCD" else theme.ACCENT)
            p.setPen(QPen(col, 3, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRectF(c.x - a, c.y - a, 2 * a, 2 * a), 225 * 16, int(-270 * frac * 16))
            self._knob_body(p, c.x, c.y, r, frac)
            if c.area in "ABCD" or c.area == "G":
                self._label(p, c.x, c.y + r + 12, c.label, 6)
            elif c.area in ("FX1", "FX2"):
                self._label(p, c.x - (8 if c.func == "drywet" else 6), c.y + r + 13, c.label, 6)
            self._focus_ring(p, c, a)
        elif sh == "enc":
            r = 16 if c.func not in ("gain", "browse") else (12 if c.func == "gain" else 15)
            ang = self.raw(c) * 22.5
            p.setPen(QPen(QColor("#33363d"), 1))
            p.setBrush(Qt.NoBrush)
            for i in range(16):
                a = math.radians(i * 22.5)
                p.drawPoint(QPointF(c.x + math.cos(a) * (r + 6), c.y + math.sin(a) * (r + 6)))
            self._knob_body(p, c.x, c.y, r, 0.5)
            push = self._push_partner(c)
            if push is not None and self.raw(push):     # knob pushed in: the knob itself shows it
                p.setPen(QPen(QColor(theme.ACCENT), 2.5))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(c.x, c.y), r + 2.5, r + 2.5)
            p.save()
            p.translate(c.x, c.y)
            p.rotate(ang)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.ACCENT))
            p.drawEllipse(QPointF(0, -r + 4), 2.2, 2.2)
            p.restore()
            if c.area in ("L", "R"):
                self._label(p, c.x, c.y + r + 13, c.label, 6.5)
            self._focus_ring(p, c, r + 4)
        elif sh in ("pad", "small"):
            self._button(p, c, unknown)
        elif sh == "fader":
            self._fader(p, c, vertical=True)
        elif sh == "hfader":
            self._fader(p, c, vertical=False)
        elif sh == "jog":
            self._jog(p, c)

    def _button(self, p: QPainter, c: Control, unknown: bool):
        pressed = c.kind == BUTTON and c.code is not None and self.core.translator.raw.get(c.code, 0) != 0
        level = 0.0
        col = lit_color(c)
        if c.func.startswith("hotcue") and len(c.led) == 2:
            b, g = self.led(c.led[0]), self.led(c.led[1])
            level = max(b, g)
            if b and g:
                col = QColor("#5fe6ff")
            elif g:
                col = GREEN
            else:
                col = BLUE
        elif c.led:
            level = self.led(c.led[0])
        if c.shape == "pad":
            w, h = (52, 32) if c.area in "LR" else (40, 22)
            rect = QRectF(c.x - w / 2, c.y - h / 2, w, h)
            base = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            base.setColorAt(0, QColor("#2c2f35") if not pressed else QColor("#1d1f24"))
            base.setColorAt(1, QColor("#1b1c20"))
            p.setPen(QPen(QColor("#050506"), 1.5))
            p.setBrush(base)
            p.drawRoundedRect(rect, 6, 6)
            if level > 0:
                glow = QColor(col)
                glow.setAlphaF(0.25 + 0.7 * level)
                p.setBrush(glow)
                p.setPen(Qt.NoPen)
                if c.area in "LR":
                    p.drawRoundedRect(QRectF(rect.left() + 8, rect.bottom() - 7, w - 16, 3.5), 2, 2)
                    halo = QColor(col)
                    halo.setAlphaF(0.18 * level)
                    p.setBrush(halo)
                    p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)
                else:
                    p.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 5, 5)
            f = QFont(p.font())
            f.setPointSizeF(7.5 if len(c.label) > 2 else 9)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#1a1206") if (level > 0.5 and c.area not in "LR") else QColor("#e8eaee"))
            p.drawText(rect.adjusted(0, -2 if c.area in "LR" else 0, 0, 0), Qt.AlignCenter, c.label)
            r = max(w, h) / 2
        else:
            r = 9
            p.setPen(QPen(QColor("#050506"), 1.5))
            g = QRadialGradient(c.x - 3, c.y - 3, 14)
            g.setColorAt(0, QColor("#4a4d55") if not pressed else QColor("#2a2c31"))
            g.setColorAt(1, QColor("#1b1c20"))
            p.setBrush(g)
            p.drawEllipse(QPointF(c.x, c.y), r, r)
            if level > 0:
                glow = QColor(col)
                glow.setAlphaF(0.35 + 0.65 * level)
                p.setBrush(glow)
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(c.x, c.y), r - 2.5, r - 2.5)
                halo = QRadialGradient(c.x, c.y, r + 8)
                hc = QColor(col)
                hc.setAlphaF(0.35 * level)
                halo.setColorAt(0, hc)
                halo.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(halo)
                p.drawEllipse(QPointF(c.x, c.y), r + 8, r + 8)
            if c.area in ("FX1", "FX2") or c.area in "ABCD":
                f = QFont(p.font())
                f.setPointSizeF(6.5)
                f.setBold(True)
                p.setFont(f)
                p.setPen(QColor("#101114") if level > 0.5 else QColor("#bfc3cb"))
                if c.func != "mode":
                    p.drawText(QRectF(c.x - r, c.y - r, 2 * r, 2 * r), Qt.AlignCenter, c.label)
            if c.func in ("mode", "load", "deck_toggle") or c.area == "G":
                dy = r + 9
                if c.func in ("load", "deck_toggle"):
                    dx = 28 if (c.func == "deck_toggle") == (c.area == "L") else -26
                    self._label(p, c.x + dx, c.y, c.label, 7, bold=True)
                elif c.func not in ("snap", "master", "quant"):
                    self._label(p, c.x, c.y + dy, c.label, 6)
        if unknown:
            p.setPen(QPen(QColor(theme.WARN), 1.2, Qt.DotLine))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(c.x, c.y), r + 3, r + 3)
        self._focus_ring(p, c, r)

    def _fader(self, p: QPainter, c: Control, vertical: bool):
        frac = self.raw(c) / 4095
        if vertical:
            top, bot = c.y - c.h / 2, c.y + c.h / 2
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#050506"))
            p.drawRoundedRect(QRectF(c.x - 3, top, 6, c.h), 3, 3)
            p.setPen(QPen(QColor("#3a3d44"), 1))
            for i in range(9):
                yy = top + i * c.h / 8
                p.drawLine(QPointF(c.x - 16, yy), QPointF(c.x - 10, yy))
            y = bot - frac * c.h
            g = QLinearGradient(0, y - 9, 0, y + 9)
            g.setColorAt(0, QColor("#3b3e45"))
            g.setColorAt(1, QColor("#16171a"))
            p.setPen(QPen(QColor("#050506"), 1.5))
            p.setBrush(g)
            p.drawRoundedRect(QRectF(c.x - 15, y - 9, 30, 18), 3, 3)
            p.setPen(QPen(QColor("#e8e8e8"), 1.6))
            p.drawLine(QPointF(c.x - 12, y), QPointF(c.x + 12, y))
            tr = self.core.translator
            if c.func == "tempo" and tr.takeover.get(c.area):
                fb = tr.tempo_fb.get(tr.active[c.area])
                if fb is not None:
                    inv = bool((tr.p["map"].get("deck.tempo") or {}).get("invert"))
                    f2 = (127 - fb) / 127 if inv else fb / 127
                    gy = bot - f2 * c.h
                    p.setPen(QPen(QColor(theme.ACCENT), 2, Qt.DashLine))
                    p.setBrush(Qt.NoBrush)
                    p.drawRoundedRect(QRectF(c.x - 15, gy - 9, 30, 18), 3, 3)
                    self._label(p, c.x, gy - 16 if gy > top + 20 else gy + 18, "PICK UP", 5.5, QColor(theme.ACCENT), bold=True)
            if c.cid in self.activity or c.cid == self.selected:
                col = QColor(theme.ACCENT)
                p.setPen(QPen(col, 2, Qt.SolidLine if c.cid in self.activity else Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(QRectF(c.x - 20, top - 8, 40, c.h + 16), 8, 8)
        else:
            left, right = c.x - c.w / 2, c.x + c.w / 2
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#050506"))
            p.drawRoundedRect(QRectF(left, c.y - 3, c.w, 6), 3, 3)
            p.setPen(QPen(QColor("#5b5f68"), 1))
            for i in range(5):
                xx = left + i * c.w / 4
                p.drawLine(QPointF(xx, c.y - 16), QPointF(xx, c.y - 10))
            x = left + frac * c.w
            g = QLinearGradient(x - 9, 0, x + 9, 0)
            g.setColorAt(0, QColor("#3b3e45"))
            g.setColorAt(1, QColor("#16171a"))
            p.setPen(QPen(QColor("#050506"), 1.5))
            p.setBrush(g)
            p.drawRoundedRect(QRectF(x - 9, c.y - 15, 18, 30), 3, 3)
            p.setPen(QPen(QColor("#e8e8e8"), 1.6))
            p.drawLine(QPointF(x, c.y - 12), QPointF(x, c.y + 12))
            if c.cid in self.activity or c.cid == self.selected:
                p.setPen(QPen(QColor(theme.ACCENT), 2))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(QRectF(left - 14, c.y - 22, c.w + 28, 44), 8, 8)

    def _jog(self, p: QPainter, c: Control):
        r = 132
        touched = self.core.translator._touch.get(c.area, False)
        # outer ring
        g = QRadialGradient(c.x, c.y, r)
        g.setColorAt(0.80, QColor("#101113"))
        g.setColorAt(0.93, QColor("#2a2c31"))
        g.setColorAt(1.0, QColor("#0a0a0c"))
        p.setPen(QPen(QColor("#050506"), 2))
        p.setBrush(g)
        p.drawEllipse(QPointF(c.x, c.y), r, r)
        # grip ridges
        p.setPen(QPen(QColor("#1c1d21"), 3))
        for i in range(48):
            a = math.radians(i * 7.5)
            p.drawLine(QPointF(c.x + math.cos(a) * (r - 18), c.y + math.sin(a) * (r - 18)),
                       QPointF(c.x + math.cos(a) * (r - 4), c.y + math.sin(a) * (r - 4)))
        # platter
        pr = r - 24
        pg = QRadialGradient(c.x - 30, c.y - 40, pr * 1.4)
        pg.setColorAt(0, QColor("#2d2f35"))
        pg.setColorAt(1, QColor("#121316"))
        p.setPen(QPen(QColor(theme.ACCENT) if touched else QColor("#050506"), 3 if touched else 1.5))
        p.setBrush(pg)
        p.drawEllipse(QPointF(c.x, c.y), pr, pr)
        # rotating marker
        ang = self.raw(c) / JOG_RANGE * 360
        p.save()
        p.translate(c.x, c.y)
        p.rotate(ang)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.ACCENT) if touched else QColor("#d9dbe0"))
        p.drawRoundedRect(QRectF(-3, -pr + 8, 6, 22), 3, 3)
        # center logo-ish hub
        p.setBrush(QColor("#e9eaed"))
        p.drawEllipse(QPointF(0, 0), 28, 28)
        p.setBrush(QColor("#17181b"))
        p.drawEllipse(QPointF(0, 0), 18, 18)
        p.setBrush(QColor("#e9eaed"))
        p.drawRect(QRectF(-20, -2.5, 40, 5))
        p.restore()
        side = c.area
        deck = self.core.translator.active[side]
        f = QFont(p.font())
        f.setPointSizeF(10)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(theme.ACCENT))
        p.drawText(QRectF(c.x - 40, c.y + pr - 34, 80, 20), Qt.AlignCenter, f"DECK {deck}")
        if c.cid in self.activity or c.cid == self.selected:
            p.setPen(QPen(QColor(theme.ACCENT), 2, Qt.SolidLine if c.cid in self.activity else Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(c.x, c.y), r + 5, r + 5)

    def _indicator(self, p: QPainter, ind):
        if ind.shape == "seg":
            self._sevenseg(p, ind)
            return
        if ind.shape == "meter":
            for i, n in enumerate(reversed(ind.leds)):
                lv = self.led(n)
                col = RED if i == 0 else (AMBER if i == 1 else BLUE)
                rect = QRectF(ind.x - 3, ind.y - 46 + i * 13, 6, 9)
                p.setPen(Qt.NoPen)
                base = QColor("#1b1d22")
                p.setBrush(base)
                p.drawRoundedRect(rect, 1.5, 1.5)
                if lv:
                    cc = QColor(col)
                    cc.setAlphaF(0.3 + 0.7 * lv)
                    p.setBrush(cc)
                    p.drawRoundedRect(rect, 1.5, 1.5)
            return
        lv = self.led(ind.leds[0])
        if ind.shape == "bar":
            p.setPen(Qt.NoPen)
            col = QColor(BLUE)
            col.setAlphaF(0.2 + 0.8 * lv if lv else 0.18)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(ind.x - 22, ind.y - 2, 32, 4), 2, 2)
            return
        f = QFont(p.font())
        f.setPointSizeF(5.5 if ind.area == "G" and len(ind.label) > 2 else (6.5 if len(ind.label) > 2 else 8))
        f.setBold(True)
        p.setFont(f)
        if lv:
            col = BLUE if ind.func in ("xf_left", "xf_right") else (
                AMBER if ind.func in ("on_air", "samples", "warning") else WHITE)
            c2 = QColor(col)
            c2.setAlphaF(0.35 + 0.65 * lv)
            p.setPen(c2)
        else:
            p.setPen(QColor("#3c4048"))
        p.drawText(QRectF(ind.x - 32, ind.y - 8, 64, 16), Qt.AlignCenter, ind.label)

    def _sevenseg(self, p: QPainter, ind):
        prefix = ind.leds[0].split("Digit")[0]
        for d in (1, 2):
            ox = ind.x - 14 + (d - 1) * 15
            oy = ind.y - 12
            w, h = 10, 22
            segs = {
                "A": QRectF(ox + 1.5, oy, w - 3, 2.4), "G": QRectF(ox + 1.5, oy + h / 2 - 1.2, w - 3, 2.4),
                "D": QRectF(ox + 1.5, oy + h - 2.4, w - 3, 2.4),
                "F": QRectF(ox, oy + 1.5, 2.4, h / 2 - 2), "B": QRectF(ox + w - 2.4, oy + 1.5, 2.4, h / 2 - 2),
                "E": QRectF(ox, oy + h / 2 + 0.5, 2.4, h / 2 - 2), "C": QRectF(ox + w - 2.4, oy + h / 2 + 0.5, 2.4, h / 2 - 2),
            }
            for s, rect in segs.items():
                lv = self.led(f"{prefix}Digit {d} - {s}")
                p.setPen(Qt.NoPen)
                if lv:
                    cc = QColor("#ff7a3d")
                    cc.setAlphaF(0.4 + 0.6 * lv)
                else:
                    cc = QColor("#1e1612")
                p.setBrush(cc)
                p.drawRoundedRect(rect, 1, 1)

    # ------------------------------------------------------------ interaction
    def _push_partner(self, c: Control) -> Control | None:
        partner = {"move": "move_press", "size": "size_press", "gain": "gain_press", "browse": "browse_press"}.get(c.func)
        if partner:
            return self.core.hw.controls.get(f"{c.area}.{partner}")
        return None

    def mousePressEvent(self, e):
        pt = self._to_canvas(e.position())
        c = self._hit(pt)
        if c is None:
            return
        self.picked.emit(c.cid)
        self._drag = {"c": c, "start": pt, "last": pt, "moved": False, "raw": self.raw(c)}
        if c.kind == BUTTON:
            self.inject(c, 1)
        elif c.kind == JOG:
            touch = self.core.hw.controls.get(f"{c.area}.touch")
            if touch:
                self.inject(touch, 4000)
            self._drag["ang"] = math.atan2(pt.y() - c.y, pt.x() - c.x)
        elif c.kind == POT:
            self._set_pot_from_point(c, pt) if c.shape in ("fader", "hfader") else None

    def mouseMoveEvent(self, e):
        pt = self._to_canvas(e.position())
        if self._drag is None:
            c = self._hit(pt)
            cid = c.cid if c else None
            if cid != self.hover:
                self.hover = cid
                self._dirty = True
                self.setCursor(Qt.PointingHandCursor if c else Qt.ArrowCursor)
                if cid:
                    self.hovered.emit(cid)
            return
        d = self._drag
        c = d["c"]
        if (pt - d["start"]).manhattanLength() > 3:
            d["moved"] = True
        if c.kind == POT:
            if c.shape in ("fader", "hfader"):
                self._set_pot_from_point(c, pt)
            else:
                v = max(0, min(4095, int(d["raw"] - (pt.y() - d["start"].y()) * 22)))
                self.inject(c, v)
        elif c.kind == ENCODER:
            steps = int((d["start"].y() - pt.y()) / 8)
            if steps != d.get("steps", 0):
                diff = steps - d.get("steps", 0)
                d["steps"] = steps
                self.inject(c, (self.raw(c) + diff) % 16)
        elif c.kind == JOG:
            ang = math.atan2(pt.y() - c.y, pt.x() - c.x)
            da = (ang - d["ang"] + math.pi) % (2 * math.pi) - math.pi
            d["ang"] = ang
            ticks = int(round(da / (2 * math.pi) * JOG_RANGE))
            if ticks:
                self.inject(c, (self.raw(c) + ticks) % JOG_RANGE)

    def mouseReleaseEvent(self, e):
        d = self._drag
        self._drag = None
        if not d:
            return
        c = d["c"]
        if c.kind == BUTTON:
            self.inject(c, 0)
        elif c.kind == JOG:
            touch = self.core.hw.controls.get(f"{c.area}.touch")
            if touch:
                self.inject(touch, 0)
        elif c.kind == ENCODER and not d["moved"]:
            push = self._push_partner(c)
            if push and push.code is not None:
                self.inject(push, 1)
                self.inject(push, 0)

    def wheelEvent(self, e):
        pt = self._to_canvas(e.position())
        c = self._hit(pt)
        if c is None:
            return
        steps = 1 if e.angleDelta().y() > 0 else -1
        if c.kind == ENCODER:
            self.inject(c, (self.raw(c) + steps) % 16)
        elif c.kind == JOG:
            self.inject(c, (self.raw(c) + steps * 12) % JOG_RANGE)
        elif c.kind == POT:
            self.inject(c, max(0, min(4095, self.raw(c) + steps * 128)))

    def _set_pot_from_point(self, c: Control, pt: QPointF):
        if c.shape == "fader":
            frac = ((c.y + c.h / 2) - pt.y()) / c.h
        else:
            frac = (pt.x() - (c.x - c.w / 2)) / c.w
        self.inject(c, int(max(0.0, min(1.0, frac)) * 4095))

    def leaveEvent(self, e):
        self.hover = None
        self._dirty = True
