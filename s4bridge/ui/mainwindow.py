# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Fancy Butler
from __future__ import annotations

import sys

import copy
import json
import math
import re
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QBoxLayout, QButtonGroup, QCheckBox, QComboBox,
                               QMenu, QScrollArea,
                               QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QSizePolicy, QSpinBox, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QToolButton, QVBoxLayout, QWidget)

from .. import __version__
from ..engine.profile import DEFAULT_PROFILE, PROFILE_DIR, area_key, list_profiles, load_profile
from ..hw.controls import BUTTON, CONTROLS, ENCODER, JOG, POT, TOUCH, friendly
from . import theme
from .surface import Surface

SOURCE_TXT = {
    "kernel": ("Kernel", theme.GOOD, "Named in the Linux snd-usb-caiaq driver source"),
    "tested": ("Tested", theme.ACCENT_2, "From a hardware-tested community map (blaxpot)"),
    "reported": ("Reported", theme.WARN, "Reported by one community driver; please confirm with Identify"),
    "unknown": ("Unknown", theme.BAD, "Event code not known yet: use Identify to capture it"),
    "user": ("Yours", theme.ACCENT, "Captured on your S4 with Identify"),
}
KIND_TXT = {BUTTON: "Button", POT: "Pot / fader", ENCODER: "Encoder", JOG: "Jog wheel", TOUCH: "Touch"}


def midi_text(msg) -> str:
    st, d1, d2 = msg
    kind, ch = st & 0xF0, (st & 0x0F) + 1
    name = {0x90: "Note On ", 0x80: "Note Off", 0xB0: "CC      "}.get(kind, hex(kind))
    return f"ch{ch:<2} {name}  {d1:#04x} ({d1:3d})  → {d2:3d}"


class Events(QObject):
    """Thread-safe hop from device/MIDI threads into the GUI thread."""
    event = Signal(object)
    status = Signal(str, str)


def card(title: str = "", subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(10)
    if title:
        t = QLabel(title)
        t.setStyleSheet("font-weight:700; font-size:14px;")
        lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("muted")
        s.setWordWrap(True)
        lay.addWidget(s)
    return f, lay


def page_header(title: str, sub: str) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 6)
    lay.setSpacing(2)
    h = QLabel(title)
    h.setObjectName("h1")
    s = QLabel(sub)
    s.setObjectName("muted")
    s.setWordWrap(True)
    lay.addWidget(h)
    lay.addWidget(s)
    return w


# ============================================================== Surface page
class SurfacePage(QWidget):
    def __init__(self, core, win):
        super().__init__()
        self.core, self.win = core, win
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(18)
        left = QVBoxLayout()
        left.addWidget(page_header("Live surface", "Everything you touch on the S4 shows up here, and every LED "
                                   "mirrors what the bridge is sending. Click, drag and scroll to play it "
                                   "from the screen."))
        self.surface = Surface(core)
        self.surface.hovered.connect(self._hover)
        left.addWidget(self.surface, 1)
        lay.addLayout(left, 1)

        side = QVBoxLayout()
        side.setSpacing(14)
        c1, l1 = card("Decks")
        row = QHBoxLayout()
        self.deck_btn = {}
        for s in ("L", "R"):
            b = QPushButton()
            b.setMinimumHeight(54)
            b.setStyleSheet("font-size:17px; font-weight:800; padding:4px 6px;")
            b.setToolTip("Flip this side's deck")
            b.clicked.connect(lambda _=False, s=s: core.translator.toggle_deck(s))
            self.deck_btn[s] = b
            row.addWidget(b)
        l1.addLayout(row)
        hint = QLabel("Left side flips A ↔ C, right side B ↔ D, just like the DECK C / DECK D buttons.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        l1.addWidget(hint)
        side.addWidget(c1)

        c2, l2 = card("MIDI port")
        self.port_lbl = QLabel()
        self.port_lbl.setWordWrap(True)
        self.port_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        l2.addWidget(self.port_lbl)
        side.addWidget(c2)

        c3, l3 = card("Inspector")
        self.insp = QLabel("Hover a control.")
        self.insp.setWordWrap(True)
        self.insp.setTextFormat(Qt.RichText)
        self.insp.setMinimumHeight(120)
        self.insp.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        l3.addWidget(self.insp)
        side.addWidget(c3)

        c4, l4 = card("Activity")
        self.last = QLabel("—")
        self.last.setStyleSheet("font-family: 'JetBrains Mono','Fira Code',monospace; font-size:12px;")
        self.last.setWordWrap(True)
        l4.addWidget(self.last)
        self.rate = QLabel("0 msg/s")
        self.rate.setObjectName("muted")
        l4.addWidget(self.rate)
        side.addWidget(c4)
        side.addStretch(1)
        wrap = QWidget()
        wrap.setLayout(side)
        wrap.setFixedWidth(270)
        self.side_wrap = wrap
        lay.addWidget(wrap)
        self.refresh()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # tight on space: the drawing wins; decks are still in the sidebar, the rest in Monitor/Mapping
        self.side_wrap.setVisible(self.width() >= 1050)

    def refresh(self):
        for s in ("L", "R"):
            d = self.core.translator.active[s]
            self.deck_btn[s].setText(f"Deck {d}")
        m = self.core.midi
        if self.core.midi_error:
            self.port_lbl.setText(f"<span style='color:{theme.BAD}'>Not available</span><br>"
                                  f"<span style='color:{theme.MUTED}'>{self.core.midi_error}</span>")
        else:
            self.port_lbl.setText(f"<b>S4 Bridge › Kontrol S4 MK1</b><br>"
                                  f"<span style='color:{theme.MUTED}'>ALSA seq {m.address} · in + out. "
                                  f"Select it in Mixxx or any DAW (via PipeWire / JACK too).</span>")

    def _hover(self, cid):
        self.win.describe(cid, self.insp)


# ============================================================== Mapping page
class MappingPage(QWidget):
    COLS = ["Control", "Area", "Kind", "Source", "Event", "MIDI", "Number", "Options"]

    def __init__(self, core, win):
        super().__init__()
        self.core, self.win = core, win
        self.identify_cid = None
        self._loading = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(page_header("Mapping", "What each control sends. Deck controls follow the deck their side "
                                  "is on (A–D = MIDI ch 1–4); mixer, browse, loop recorder and FX use the "
                                  "global channel. Shift adds an offset to buttons and encoders."))

        bar = QHBoxLayout()
        self.profile_box = QComboBox()
        self.profile_box.setMinimumWidth(170)
        self.profile_box.activated.connect(self._pick_profile)
        bar.addWidget(self.profile_box, 1)
        menu = QMenu(self)
        for text, ic, fn in (("Save", "save", self._save), ("Save as…", "copy", self._save_as),
                             ("Import…", "upload", self._import), ("Export…", "download", self._export),
                             (None, None, None),
                             ("Export Mixxx mapping files only…", "download", self._export_mixxx)):
            if text is None:
                menu.addSeparator()
                continue
            menu.addAction(theme.icon(ic, theme.TEXT, 16), text, fn)
        pb = QToolButton()
        pb.setText("Profile")
        pb.setIcon(theme.icon("folder-open", theme.TEXT, 16))
        pb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        pb.setPopupMode(QToolButton.InstantPopup)
        pb.setMenu(menu)
        pb.setStyleSheet(f"QToolButton {{ background:{theme.CARD}; border:1px solid {theme.LINE}; border-radius:9px;"
                         f" padding:7px 12px; }} QToolButton::menu-indicator {{ image:none; }}")
        bar.addWidget(pb)
        self.adv_btn = QToolButton()
        self.adv_btn.setText("Channels")
        self.adv_btn.setIcon(theme.icon("sliders-horizontal", theme.TEXT, 16))
        self.adv_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.adv_btn.setCheckable(True)
        self.adv_btn.setStyleSheet(pb.styleSheet())
        self.adv_btn.setToolTip("MIDI channels, shift offset and encoder style")
        bar.addWidget(self.adv_btn)
        mx = QPushButton(theme.icon("zap", "#1a0f03", 16), "Set up Mixxx")
        mx.setObjectName("primary")
        mx.setToolTip("One click: install the mapping, enable the S4 in Mixxx, and send Mixxx's "
                      "Main and Headphones to the S4's own outputs")
        mx.clicked.connect(self._setup_mixxx)
        bar.addWidget(mx)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter…")
        self.search.addAction(theme.icon("search", theme.MUTED, 16), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self._filter)
        self.search.setMinimumWidth(120)
        self.search.setMaximumWidth(220)
        bar.addWidget(self.search, 1)
        lay.addLayout(bar)

        self.adv = QFrame()
        self.adv.setObjectName("card")
        glob = QGridLayout(self.adv)
        glob.setContentsMargins(16, 12, 16, 12)
        glob.setHorizontalSpacing(10)
        glob.setVerticalSpacing(8)
        self.ch = {}
        for i, d in enumerate("ABCD"):
            sp = QSpinBox()
            sp.setRange(1, 16)
            sp.valueChanged.connect(lambda v, d=d: self._set_chan(d, v))
            self.ch[d] = sp
            glob.addWidget(QLabel(f"Deck {d} ch"), 0, i * 2)
            glob.addWidget(sp, 0, i * 2 + 1)
        self.gch = QSpinBox()
        self.gch.setRange(1, 16)
        self.gch.valueChanged.connect(lambda v: self._set_global("global_channel", v - 1))
        glob.addWidget(QLabel("Global ch"), 1, 0)
        glob.addWidget(self.gch, 1, 1)
        self.dshift = QSpinBox()
        self.dshift.setRange(0, 127)
        self.dshift.setDisplayIntegerBase(16)
        self.dshift.setPrefix("+0x")
        self.dshift.valueChanged.connect(lambda v: self._set_global("deck_shift_offset", v))
        glob.addWidget(QLabel("Shift offset"), 1, 2)
        glob.addWidget(self.dshift, 1, 3)
        self.enc = QComboBox()
        self.enc.addItems(["Relative: 64 ± n", "Relative: two's complement"])
        self.enc.currentIndexChanged.connect(
            lambda i: self._set_global("relative_encoding", "offset" if i == 0 else "twos"))
        glob.addWidget(self.enc, 1, 4, 1, 4)
        glob.setColumnStretch(8, 1)
        self.adv.setVisible(False)
        self.adv_btn.toggled.connect(self.adv.setVisible)
        lay.addWidget(self.adv)

        body = QBoxLayout(QBoxLayout.LeftToRight)
        self.body = body
        body.setSpacing(14)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, w in ((5, 92), (6, 92), (7, 200)):
            hh.setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, w)
        self.table.itemSelectionChanged.connect(self._selected)
        body.addWidget(self.table, 1)

        side, sl = card("Identify", "Pick a row, press Identify, then touch that control on your S4. "
                        "Its event code is saved to your hardware map, which fixes anything marked "
                        "Reported or Unknown for your unit.")
        self.id_btn = QPushButton(theme.icon("crosshair", "#1a0f03", 16), "Identify")
        self.id_btn.setObjectName("primary")
        self.id_btn.setToolTip("Pick a row, press Identify, then touch that control on your S4.")
        self.id_btn.clicked.connect(self._identify)
        sl.addWidget(self.id_btn)
        self.id_state = QLabel("")
        self.id_state.setWordWrap(True)
        sl.addWidget(self.id_state)
        rst = QPushButton("Reset hardware map")
        rst.clicked.connect(self._reset_hw)
        sl.addWidget(rst)
        legend = QLabel("<br>".join(
            f"<span style='color:{c}'>●</span> <b>{n}</b>: <span style='color:{theme.MUTED}'>{d}</span>"
            for n, c, d in SOURCE_TXT.values()))
        legend.setWordWrap(True)
        legend.setTextFormat(Qt.RichText)
        sl.addWidget(legend)
        sl.addStretch(1)
        self.id_card = side
        self.id_legend = legend
        self.id_help = [w for w in side.findChildren(QLabel) if w.objectName() == "muted"][:1]
        body.addWidget(side)
        lay.addLayout(body, 1)
        self.reload()
        self._narrow = None

    def resizeEvent(self, e):
        super().resizeEvent(e)
        narrow = self.width() < 1100
        if narrow == self._narrow:
            return
        self._narrow = narrow
        # narrow: Identify goes under the table and drops the legend (tooltips still explain it)
        self.body.setDirection(QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight)
        self.id_legend.setVisible(not narrow)
        for w in self.id_help:  # the instructions live in the Identify button's tooltip when space is tight
            w.setVisible(not narrow)
        # Area and Kind are the least useful columns; the control name matters more
        self.table.setColumnHidden(1, narrow)
        self.table.setColumnHidden(2, narrow)
        self.table.setColumnWidth(7, 150 if narrow else 200)
        self.id_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum if narrow else QSizePolicy.Preferred)
        self.id_card.setMaximumHeight(self.id_card.minimumSizeHint().height() if narrow else 16777215)
        if narrow:
            self.id_card.setMinimumWidth(0)
            self.id_card.setMaximumWidth(16777215)
        else:
            self.id_card.setFixedWidth(280)

    # ---------------------------------------------------------- data
    def reload(self):
        self._loading = True
        p = self.core.profile
        for d in "ABCD":
            self.ch[d].setValue(p["deck_channels"][d] + 1)
        self.gch.setValue(p["global_channel"] + 1)
        self.dshift.setValue(p["deck_shift_offset"])
        self.enc.setCurrentIndex(0 if p.get("relative_encoding", "offset") == "offset" else 1)
        self.profile_box.clear()
        self.profile_box.addItem("S4 Bridge Standard (built-in)", None)
        for path in list_profiles():
            self.profile_box.addItem(path.stem, str(path))
        idx = self.profile_box.findData(self.core.profile_path)
        self.profile_box.setCurrentIndex(max(0, idx))
        self._fill()
        self._loading = False

    def _fill(self):
        t = self.table
        t.setRowCount(0)
        self.rows = {}
        for c in self.core.hw.controls.values():
            if c.kind == TOUCH and c.code is None:
                continue
            r = t.rowCount()
            t.insertRow(r)
            self.rows[c.cid] = r
            key = area_key(c.area, c.func)
            m = self.core.profile["map"].get(key)
            item = QTableWidgetItem(friendly(c))
            item.setData(Qt.UserRole, c.cid)
            f = item.font()
            f.setWeight(QFont.DemiBold)
            item.setFont(f)
            t.setItem(r, 0, item)
            area = {"L": "Left deck", "R": "Right deck", "G": "Center"}.get(c.area, c.area if c.area.startswith("FX")
                                                                              else f"Mixer {c.area}")
            t.setItem(r, 1, QTableWidgetItem(area))
            t.setItem(r, 2, QTableWidgetItem(KIND_TXT[c.kind]))
            src_name, col, tip = SOURCE_TXT[c.source]
            si = QTableWidgetItem(f"● {src_name}")
            si.setForeground(QColor(col))
            si.setToolTip(tip + (f"\n{c.note}" if c.note else ""))
            t.setItem(r, 3, si)
            t.setItem(r, 4, QTableWidgetItem("—" if c.code is None else str(c.code)))
            if m is None:
                t.setItem(r, 5, QTableWidgetItem("—"))
                continue
            typ = QComboBox()
            typ.addItems(["Note", "CC"])
            typ.setCurrentIndex(0 if m["type"] == "note" else 1)
            typ.currentIndexChanged.connect(lambda i, k=key: self._edit(k, "type", "note" if i == 0 else "cc"))
            t.setCellWidget(r, 5, typ)
            num = QSpinBox()
            num.setRange(0, 127)
            num.setDisplayIntegerBase(16)
            num.setPrefix("0x")
            num.setValue(m["num"])
            num.valueChanged.connect(lambda v, k=key: self._edit(k, "num", v))
            t.setCellWidget(r, 6, num)
            opts = QWidget()
            ol = QHBoxLayout(opts)
            ol.setContentsMargins(4, 0, 4, 0)
            ol.setSpacing(10)
            if c.kind in (BUTTON, ENCODER, JOG, TOUCH):
                cb = QCheckBox("Shift layer")
                cb.setChecked(m.get("shiftable", True))
                cb.toggled.connect(lambda v, k=key: self._edit(k, "shiftable", v))
                ol.addWidget(cb)
            if c.kind == POT:
                hr = QCheckBox("14-bit")
                hr.setChecked(bool(m.get("hires")))
                hr.toggled.connect(lambda v, k=key: self._edit(k, "hires", v))
                inv = QCheckBox("Invert")
                inv.setChecked(bool(m.get("invert")))
                inv.toggled.connect(lambda v, k=key: self._edit(k, "invert", v))
                ol.addWidget(hr)
                ol.addWidget(inv)
            ol.addStretch(1)
            t.setCellWidget(r, 7, opts)
        self._filter(self.search.text())

    def _filter(self, text):
        text = text.lower()
        for r in range(self.table.rowCount()):
            row_txt = " ".join(self.table.item(r, c).text().lower() for c in range(5) if self.table.item(r, c))
            self.table.setRowHidden(r, bool(text) and text not in row_txt)

    def _edit(self, key, field, value):
        m = self.core.profile["map"].setdefault(key, {"type": "note", "num": 0})
        m[field] = value
        self.core.profile_changed()
        self.win.set_dirty(True)

    def _set_chan(self, d, v):
        if self._loading:
            return
        self.core.profile["deck_channels"][d] = v - 1
        self.core.profile_changed()
        self.win.set_dirty(True)

    def _set_global(self, k, v):
        if self._loading:
            return
        self.core.profile[k] = v
        self.core.profile_changed()
        self.win.set_dirty(True)

    # ---------------------------------------------------------- selection / identify
    def _selected(self):
        items = self.table.selectedItems()
        cid = self.table.item(items[0].row(), 0).data(Qt.UserRole) if items else None
        self.win.surface_page.surface.selected = cid
        self.win.surface_page.surface._dirty = True

    def select(self, cid):
        r = self.rows.get(cid)
        if r is not None and self.identify_cid is None:
            self.table.blockSignals(True)
            self.table.selectRow(r)
            self.table.blockSignals(False)
            self.table.scrollToItem(self.table.item(r, 0), QAbstractItemView.EnsureVisible)

    def _identify(self):
        items = self.table.selectedItems()
        if not items:
            self.id_state.setText("Select a row first.")
            return
        self.identify_cid = self.table.item(items[0].row(), 0).data(Qt.UserRole)
        c = self.core.hw.controls[self.identify_cid]
        self.id_state.setText(f"<span style='color:{theme.ACCENT}'>Listening…</span> "
                              f"{'press' if c.kind == BUTTON else 'move'} <b>{c.cid}</b> on the S4. "
                              f"Esc to cancel.")
        self._baseline = dict(self.core.translator.raw)

    def on_raw(self, ev):
        """Called for every input event while Identify is armed."""
        if self.identify_cid is None:
            return
        code, value = ev["code"], ev["value"]
        target = self.core.hw.controls[self.identify_cid]
        if target.kind == BUTTON and (code < 256 or value == 0):
            return
        if target.kind != BUTTON:
            if code >= 256:
                return
            before = self._baseline.get(code)
            if before is not None and abs(value - before) < (2 if target.kind == ENCODER else 200):
                return
        self.core.assign_code(self.identify_cid, code)
        self.id_state.setText(f"<span style='color:{theme.GOOD}'>Saved.</span> <b>{self.identify_cid}</b> "
                              f"= event {code}.")
        cid = self.identify_cid
        self.identify_cid = None
        self._fill()
        self.select(cid)

    def cancel_identify(self):
        if self.identify_cid:
            self.identify_cid = None
            self.id_state.setText("Cancelled.")

    def _reset_hw(self):
        if QMessageBox.question(self, "Reset hardware map",
                                "Forget every control you captured with Identify?") == QMessageBox.Yes:
            self.core.reset_hardware_overrides()
            self._fill()

    # ---------------------------------------------------------- profiles
    def _pick_profile(self, i):
        path = self.profile_box.itemData(i)
        try:
            prof = load_profile(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Profile", f"Couldn't load it: {e}")
            return
        self.core.set_profile(prof, path)
        self.win.set_dirty(False)
        self.reload()

    def _save(self):
        if self.core.profile_path is None:
            return self._save_as()
        self.core.save_profile()
        self.win.set_dirty(False)
        self.win.toast(f"Saved {Path(self.core.profile_path).name}")

    def _save_as(self):
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Save profile", str(PROFILE_DIR / "my-profile.json"),
                                              "S4 Bridge profile (*.json)")
        if path:
            self.core.profile["name"] = Path(path).stem
            self.core.save_profile(path)
            self.win.set_dirty(False)
            self.reload()

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import profile", str(Path.home()), "Profile (*.json)")
        if not path:
            return
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        dest = PROFILE_DIR / Path(path).name
        dest.write_text(Path(path).read_text())
        self.core.set_profile(load_profile(dest), str(dest))
        self.reload()

    def _setup_mixxx(self):
        from ..mixxx import MixxxSetupError, setup_mixxx
        try:
            r = setup_mixxx(self.core.profile)
        except MixxxSetupError as e:
            QMessageBox.warning(self, "Set up Mixxx", str(e))
            return
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Set up Mixxx", f"Couldn't write Mixxx's settings:\n{e}")
            return
        warn = "" if r["sinks_found"] else (
            "\n\nHeads up: the S4's outputs weren't found in PipeWire right now (is it switched on?), "
            "so the standard names were used. If Mixxx shows “---”, pick them once in Sound Hardware.")
        QMessageBox.information(
            self, "Mixxx is set up",
            f"Done. Start Mixxx and play.\n\n"
            f"• Mapping installed and the S4 controller enabled\n"
            f"• Main → {r['main']}\n• Headphones → {r['phones']}\n\n"
            f"Your previous Mixxx settings were backed up next to them as *.s4bridge-backup." + warn)

    def _export_mixxx(self):
        from ..mixxx import export, mixxx_controller_dirs
        start = str(mixxx_controller_dirs()[0])
        folder = QFileDialog.getExistingDirectory(self, "Mixxx controllers folder", start)
        if not folder:
            return
        files = export(self.core.profile, Path(folder), 1024)   # bridge normalises to 1024/turn
        QMessageBox.information(
            self, "Mixxx mapping exported",
            f"Wrote {files[0].name} and {files[1].name} to\n{folder}\n\n"
            "In Mixxx: Preferences › Controllers › “Kontrol S4 MK1” › Enabled, then pick "
            "“Traktor Kontrol S4 MK1 (S4 Bridge)” from Load Mapping. Keep S4 Bridge running first.")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export profile", str(Path.home() / "s4bridge-profile.json"),
                                              "Profile (*.json)")
        if path:
            Path(path).write_text(json.dumps(self.core.profile, indent=2))


# ============================================================== Monitor page
class MonitorPage(QWidget):
    def __init__(self, core):
        super().__init__()
        self.core = core
        self.buf: deque = deque(maxlen=4000)
        self.pending: list[str] = []
        self.paused = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        lay.addWidget(page_header("MIDI monitor", "Raw hardware events, the MIDI the bridge sends, and the LED "
                                  "feedback coming back from your DJ software."))
        bar = QHBoxLayout()
        self.show = {}
        for key, label in (("in", "Hardware"), ("out", "MIDI out"), ("midi_in", "LED feedback"),
                           ("unknown", "Unknown"), ("meters", "Meters")):
            cb = QCheckBox(label)
            cb.setChecked(key not in ("in", "meters"))
            self.show[key] = cb
            bar.addWidget(cb)
        bar.addStretch(1)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.toggled.connect(lambda v: setattr(self, "paused", v))
        clr = QPushButton(theme.icon("trash-2", theme.TEXT, 16), "Clear")
        bar.addWidget(self.pause_btn)
        bar.addWidget(clr)
        lay.addLayout(bar)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(4000)
        self.log.setStyleSheet("font-family:'JetBrains Mono','Fira Code','DejaVu Sans Mono',monospace; font-size:12px;"
                               "padding:8px;")
        clr.clicked.connect(self.log.clear)
        lay.addWidget(self.log, 1)
        t = QTimer(self)
        t.timeout.connect(self._flush)
        t.start(60)

    def push(self, ev):
        if self.paused:
            return
        k = ev["t"]
        if k not in self.show or not self.show[k].isChecked():
            return
        ts = time.strftime("%H:%M:%S")
        if k == "out":
            col, line = theme.ACCENT, f"{ts}  ⟶ OUT  {midi_text(ev['msg'])}   {ev.get('cid') or ''}"
        elif k == "midi_in":
            tg = ev.get("targets") or []
            if any(t.endswith(".meter") for t in tg) and not self.show["meters"].isChecked():
                return
            # deck targets come in four copies (one per deck); show the one this channel means
            ch = ev["msg"][0] & 0x0F
            decks = {v: k for k, v in self.core.profile["deck_channels"].items()}
            shown = [t for t in tg if t[0] not in "ABCD" or t[0] == decks.get(ch)]
            col, line = theme.ACCENT_2, f"{ts}  ⟵ IN   {midi_text(ev['msg'])}   {', '.join(shown) or '(no LED)'}"
        elif k == "in":
            col, line = theme.MUTED, f"{ts}  ◉ HW   {ev['cid']:<18} code {ev['code']:<4} value {ev['value']}"
        else:
            from ..hw.usb_s4 import EXTRA_NAMES
            where = EXTRA_NAMES.get(ev["code"])
            if where:   # a report byte the kernel driver ignores (built-in USB driver only)
                col, line = theme.WARN, (f"{ts}  ? HW   raw {where:<18} code {ev['code']:<4} value {ev['value']}"
                                         f"  ({ev['value']:#06x})")
            else:
                col, line = theme.WARN, f"{ts}  ? HW   unidentified code {ev['code']} value {ev['value']}  (Mapping › Identify)"
        line = line.replace("&", "&amp;").replace("<", "&lt;").replace(" ", "&nbsp;")
        self.pending.append(f"<span style='color:{col}'>{line}</span>")

    def _flush(self):
        if self.pending:
            self.log.appendHtml("<br>".join(self.pending[-300:]))
            self.pending.clear()


# ============================================================== Settings page
class SettingsPage(QWidget):
    def __init__(self, core, win):
        super().__init__()
        self.core, self.win = core, win
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)
        outer.addWidget(page_header("Settings", "Feel, feedback and hardware behaviour."))
        grid = QGridLayout()
        grid.setSpacing(14)

        # jog
        c1, l1 = card("Jog wheels", "Calibrate once: put a bit of tape on the left platter's edge, click Reset, "
                      "spin it exactly one full turn, then click Use measured. Scratching becomes 1:1 with the "
                      "platter, live. Output scale is extra speed on top, for taste.")
        row = QHBoxLayout()
        row.addWidget(QLabel("Output scale"))
        self.jog_scale = QDoubleSpinBox()
        self.jog_scale.setRange(0.05, 8.0)
        self.jog_scale.setSingleStep(0.05)
        self.jog_scale.valueChanged.connect(lambda v: self._p("jog_scale", v))
        row.addWidget(self.jog_scale)
        row.addStretch(1)
        l1.addLayout(row)
        self.ticks = QLabel()
        self.ticks.setStyleSheet("font-size:22px; font-weight:800;")
        l1.addWidget(self.ticks)
        rr = QHBoxLayout()
        rb = QPushButton(theme.icon("rotate-cw", theme.TEXT, 16), "Reset counters")
        rb.clicked.connect(self._reset_ticks)
        rr.addWidget(rb)
        rr.addSpacing(12)
        rr.addWidget(QLabel("Ticks per turn"))
        self.tpr = QSpinBox()
        self.tpr.setRange(32, 8192)
        self.tpr.valueChanged.connect(self._set_tpr)
        rr.addWidget(self.tpr)
        use = QPushButton("Use measured")
        use.clicked.connect(lambda: self.tpr.setValue(max(32, max(abs(self.core.translator.jog_ticks["L"]),
                                                                    abs(self.core.translator.jog_ticks["R"])))))
        use.setObjectName("primary")
        rr.addWidget(use)
        rr.addStretch(1)
        l1.addLayout(rr)
        grid.addWidget(c1, 0, 0)

        # touch
        c2, l2 = card("Jog touch", "The platter tops are capacitive distance sensors. Rest a hand on each and "
                      "set the threshold between the 'idle' and 'touched' readings.")
        self.touch_bars = {}
        for s, name in (("L", "Left"), ("R", "Right")):
            r = QHBoxLayout()
            r.addWidget(QLabel(name))
            bar = QProgressBar()
            bar.setRange(0, 4095)
            bar.setFormat("%v")
            self.touch_bars[s] = bar
            r.addWidget(bar, 1)
            l2.addLayout(r)
        r = QHBoxLayout()
        r.addWidget(QLabel("Threshold"))
        self.th = QSpinBox()
        self.th.setRange(100, 4095)
        self.th.setSingleStep(25)
        self.th.valueChanged.connect(lambda v: self._p("touch_threshold", v))
        r.addWidget(self.th)
        r.addStretch(1)
        l2.addLayout(r)
        grid.addWidget(c2, 0, 1)

        # LEDs
        c3, l3 = card("LEDs")
        self.led_fb = QCheckBox("LEDs follow the DJ software")
        self.led_fb.toggled.connect(lambda v: self._p("led_feedback", v))
        self.local_fb = QCheckBox("Light buttons while held")
        self.local_fb.toggled.connect(lambda v: self._p("local_press_feedback", v))
        self.swap = QCheckBox("Swap the display digits")
        self.swap.toggled.connect(lambda v: self._p("display_swap_digits", v))
        self.boot = QCheckBox("Startup light sweep")
        self.boot.toggled.connect(lambda v: self._s("boot_animation", v))
        for w in (self.led_fb, self.local_fb, self.swap, self.boot):
            l3.addWidget(w)
        br = QHBoxLayout()
        br.addWidget(QLabel("Brightness"))
        from PySide6.QtWidgets import QSlider
        self.bright = QSlider(Qt.Horizontal)
        self.bright.setRange(10, 100)
        self.bright.valueChanged.connect(self._bright)
        br.addWidget(self.bright, 1)
        self.bright_lbl = QLabel()
        self.bright_lbl.setMinimumWidth(40)
        br.addWidget(self.bright_lbl)
        l3.addLayout(br)
        idle = QHBoxLayout()
        self.idle = QCheckBox("Idle light show after")
        self.idle.toggled.connect(lambda v: self._s("idle_show", v))
        self.idle_min = QSpinBox()
        self.idle_min.setRange(1, 120)
        self.idle_min.setSuffix(" min")
        self.idle_min.valueChanged.connect(lambda v: self._s("idle_minutes", v))
        idle.addWidget(self.idle)
        idle.addWidget(self.idle_min)
        idle.addStretch(1)
        l3.addLayout(idle)
        self.takeover = QCheckBox("Soft takeover on the tempo faders")
        self.takeover.setToolTip("After a deck flip, the tempo fader waits until it reaches that deck's tempo; "
                                 "OFFSET ▲▼ show which way to push.")
        self.takeover.toggled.connect(lambda v: self._p("soft_takeover", v))
        l3.addWidget(self.takeover)
        tb = QPushButton(theme.icon("lightbulb", theme.TEXT, 16), "Test all LEDs")
        tb.clicked.connect(core.test_leds)
        l3.addWidget(tb, 0, Qt.AlignLeft)
        grid.addWidget(c3, 1, 0)

        # device
        c4, l4 = card("Device")
        drow = QHBoxLayout()
        drow.addWidget(QLabel("Connection"))
        self.driver = QComboBox()
        self.driver.addItem("Linux kernel driver", "kernel")
        self.driver.addItem("Built-in USB driver (beta)", "usb")
        self.driver.setToolTip("Kernel driver: controls, LEDs and the S4's sound card (Linux only).\n"
                               "Built-in USB driver: controls and LEDs on any system, but no S4 sound card yet. "
                               "This is what Mac and Windows use.")
        self.driver.activated.connect(lambda _i: self._set_driver(self.driver.currentData()))
        drow.addWidget(self.driver, 1)
        self.driver_row = QWidget()
        self.driver_row.setLayout(drow)
        drow.setContentsMargins(0, 0, 0, 0)
        self.driver_row.setVisible(sys.platform.startswith("linux"))   # elsewhere there's only one choice
        l4.addWidget(self.driver_row)
        self.grab = QCheckBox("Exclusive access to the S4")
        self.grab.setToolTip("Stops games and the desktop treating the S4 as a joystick.")
        self.grab.toggled.connect(lambda v: self._s("grab", v))
        l4.addWidget(self.grab)
        note = QLabel("Applies on next launch. Audio (4 outs / 4 ins) is a normal ALSA/PipeWire card "
                      "handled by the kernel, so pick “Traktor Kontrol S4” as your sound device in the DJ app.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        l4.addWidget(note)
        self.dev_info = QLabel()
        self.dev_info.setWordWrap(True)
        l4.addWidget(self.dev_info)
        grid.addWidget(c4, 1, 1)

        c5, l5 = card("App")
        self.autostart = QCheckBox("Start when I log in (in the tray)")
        self.autostart.toggled.connect(self._autostart)
        self.tray_close = QCheckBox("Keep running in the tray when closed")
        self.tray_close.toggled.connect(lambda v: self._s("close_to_tray", v))
        self.upd = QCheckBox("Tell me when there's a new version")
        self.upd.setToolTip("Once a day, asks GitHub for the latest release number. Nothing about you or "
                            "your setup is sent.")
        self.upd.toggled.connect(lambda v: self._s("check_updates", v))
        l5.addWidget(self.autostart)
        l5.addWidget(self.tray_close)
        l5.addWidget(self.upd)
        grid.addWidget(c5, 2, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.grid = grid
        self.cards = [c1, c2, c3, c4, c5]
        self._cols = 2
        outer.addLayout(grid)
        outer.addStretch(1)
        self.reload()
        t = QTimer(self)
        t.timeout.connect(self._live)
        t.start(50)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cols = 2 if self.width() >= 1150 else 1
        if cols == self._cols:
            return
        self._cols = cols
        for c in self.cards:
            self.grid.removeWidget(c)
        for i, c in enumerate(self.cards):
            if cols == 2:
                r, col = divmod(i, 2)
                self.grid.addWidget(c, r, col, 1, 2 if i == len(self.cards) - 1 else 1)
            else:
                self.grid.addWidget(c, i, 0, 1, 2)
        self.grid.setColumnStretch(1, 1 if cols == 2 else 0)

    def _set_driver(self, name):
        if name == "usb" and not self.core.demo:
            from ..hw.usb_s4 import available
            if not available():
                QMessageBox.warning(self, "Needs pyusb", "The built-in USB driver needs the pyusb package "
                                    "(python-pyusb on Arch, python3-pyusb on Fedora, python3-usb on Debian).")
                self.driver.setCurrentIndex(self.driver.findData("kernel"))
                return
        self.core.set_driver(name)
        self.grab.setEnabled(name == "kernel")
        self.win.toast("Using the built-in USB driver" if name == "usb" else "Using the Linux kernel driver")

    def reload(self):
        p, s = self.core.profile, self.core.settings
        from .tray import autostart_enabled
        for w in (self.jog_scale, self.th, self.led_fb, self.local_fb, self.swap, self.boot, self.grab, self.tpr,
                  self.autostart, self.tray_close, self.bright, self.idle, self.idle_min, self.takeover):
            w.blockSignals(True)
        self.bright.setValue(int(s.get("led_brightness", 100)))
        self.bright_lbl.setText(f"{self.bright.value()}%")
        self.idle.setChecked(s.get("idle_show", False))
        self.idle_min.setValue(int(s.get("idle_minutes", 10)))
        self.takeover.setChecked(p.get("soft_takeover", True))
        self.autostart.setChecked(autostart_enabled())
        self.tray_close.setChecked(s.get("close_to_tray", True))
        self.upd.setChecked(s.get("check_updates", True))
        self.tpr.setValue(int(s.get("jog_ticks_per_rev", 1000)))
        self.jog_scale.setValue(p.get("jog_scale", 1.0))
        self.th.setValue(p.get("touch_threshold", 3050))
        self.led_fb.setChecked(p.get("led_feedback", True))
        self.local_fb.setChecked(p.get("local_press_feedback", False))
        self.swap.setChecked(p.get("display_swap_digits", False))
        self.boot.setChecked(s.get("boot_animation", True))
        self.grab.setChecked(s.get("grab", True))
        cur = self.core.driver_choice()
        self.driver.setCurrentIndex(max(0, self.driver.findData(cur)))
        self.grab.setEnabled(cur == "kernel")
        for w in (self.jog_scale, self.th, self.led_fb, self.local_fb, self.swap, self.boot, self.grab, self.tpr,
                  self.autostart, self.tray_close, self.bright, self.idle, self.idle_min, self.takeover):
            w.blockSignals(False)

    def _p(self, k, v):
        self.core.profile[k] = v
        self.core.profile_changed()
        self.win.set_dirty(True)

    def _s(self, k, v):
        self.core.settings[k] = v
        self.core.save_settings()

    def _bright(self, v):
        self.bright_lbl.setText(f"{v}%")
        self.core.set_brightness(v)
        self.core.save_settings()

    def _autostart(self, v):
        from .tray import set_autostart
        set_autostart(v)
        self.win.toast("S4 Bridge will start when you log in" if v else "Start at login turned off")

    def _set_tpr(self, v):
        self.core.set_ticks_per_rev(v)
        self.core.save_settings()

    def _reset_ticks(self):
        self.core.translator.jog_ticks.update({"L": 0, "R": 0})

    def _live(self):
        t = self.core.translator
        jt = t.jog_ticks
        self.ticks.setText(f"L {jt['L']:+d}   ·   R {jt['R']:+d}  ticks")
        for s, bar in self.touch_bars.items():
            c = self.core.hw.controls.get(f"{s}.touch")
            bar.setValue(t.raw.get(c.code, 0) if c and c.code else 0)
        d = self.core.device
        info = getattr(d, "evdev_path", "") or "—"
        card_id = getattr(d, "card_id", "") or "—"
        self.dev_info.setText(f"<span style='color:{theme.MUTED}'>Input:</span> {info} &nbsp; "
                              f"<span style='color:{theme.MUTED}'>ALSA card:</span> {card_id}")


# ============================================================== Mixer page
class MixerPage(QWidget):
    LABELS = {"A": "Channel A", "B": "Channel B", "C": "Channel C", "D": "Channel D"}

    def __init__(self, core, win):
        super().__init__()
        self.core, self.win = core, win
        self.mixer = core.mixer
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)
        head = QHBoxLayout()
        head.addWidget(page_header(
            "Standalone mixer",
            "The S4 as a four-channel DJ mixer, no DJ software needed. Channels C and D play whatever is "
            "plugged into the S4's rear inputs (turntables: set the LINE/PHONO switch to PHONO). Channels A "
            "and B play apps on this computer: pick a deck for each one under “Playing now”."), 1)
        self.toggle = QPushButton()
        self.toggle.setMinimumWidth(140)
        self.toggle.setMinimumHeight(42)
        self.toggle.clicked.connect(self._toggle)
        head.addWidget(self.toggle, 0, Qt.AlignTop)
        lay.addLayout(head)

        self.state = QLabel()
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.RichText)
        lay.addWidget(self.state)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        self.src = {}
        self.bars = {}
        for i, sname in enumerate("CABD"):        # hardware order
            c, l = card(self.LABELS[sname])
            combo = QComboBox()
            combo.setMinimumWidth(130)
            combo.activated.connect(lambda _i, s=sname: self._pick(s))
            self.src[sname] = combo
            l.addWidget(QLabel("Plays"))
            l.addWidget(combo)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(10)
            self.bars[sname] = bar
            l.addWidget(bar)
            grid.addWidget(c, 0, i)
            self.chan_cards = getattr(self, "chan_cards", []) + [c]
        self.chan_grid = grid
        self._chan_cols = 4
        lay.addLayout(grid)

        pc, self.play_lay = card("Playing now", "Pick a deck for any app that's making sound. It moves "
                                 "instantly, and your system remembers it for next time.")
        self.play_rows = QVBoxLayout()
        self.play_rows.setSpacing(6)
        self.play_lay.addLayout(self.play_rows)
        self.play_empty = QLabel("Nothing is playing right now. Start a video or a song and it shows up here.")
        self.play_empty.setObjectName("muted")
        self.play_lay.addWidget(self.play_empty)
        lay.addWidget(pc)
        self._streams_sig = None
        self._play_timer = QTimer(self)
        self._play_timer.timeout.connect(self._refresh_streams)
        self._play_timer.start(2000)

        mc, ml = card("Main out")
        mrow = QHBoxLayout()
        self.bars["main"] = QProgressBar()
        self.bars["main"].setRange(0, 100)
        self.bars["main"].setTextVisible(False)
        self.bars["main"].setFixedHeight(12)
        mrow.addWidget(self.bars["main"], 1)
        self.clip = QLabel()
        mrow.addWidget(self.clip)
        ml.addLayout(mrow)
        self.info = QLabel()
        self.info.setObjectName("muted")
        self.info.setWordWrap(True)
        ml.addWidget(self.info)
        lay.addWidget(mc)
        tip = QLabel("Tip: nudge each fader and knob once after starting so the mixer picks up exactly where "
                     "the hardware is. Quit Mixxx first: the two would fight over the S4's outputs and lights.")
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        lay.addStretch(1)
        self._render()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cols = 4 if self.width() >= 1000 else 2
        if cols == self._chan_cols:
            return
        self._chan_cols = cols
        for c in self.chan_cards:
            self.chan_grid.removeWidget(c)
        for i, c in enumerate(self.chan_cards):
            self.chan_grid.addWidget(c, *divmod(i, cols))

    def _toggle(self):
        self.core.set_mixer(not self.mixer.running)
        self._render()

    def _refresh_streams(self):
        if not self.isVisible():
            return
        from ..mixer import routing
        running = self.mixer.status.get("state") == "running"
        streams = routing.list_streams() if running else []
        sig = tuple((st["id"], st["app"], st["title"], st["deck"]) for st in streams)
        if sig == self._streams_sig:
            return
        self._streams_sig = sig
        while self.play_rows.count():
            item = self.play_rows.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.play_empty.setVisible(not streams)
        if not running:
            self.play_empty.setText("Start the mixer to send apps to it.")
        else:
            self.play_empty.setText("Nothing is playing right now. Start a video or a song and it shows up here.")
        for st in streams:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            name = QLabel(f"<b>{st['app']}</b>" + (f" <span style='color:{theme.MUTED}'>· {st['title'][:60]}</span>"
                                                   if st["title"] else ""))
            name.setTextFormat(Qt.RichText)
            h.addWidget(name, 1)
            combo = QComboBox()
            combo.setMinimumWidth(150)
            for label, deck in (("Deck A", "A"), ("Deck B", "B"), ("Not in the mixer", "")):
                combo.addItem(label, deck)
            combo.setCurrentIndex(combo.findData(st["deck"]))
            combo.activated.connect(lambda _i, c=combo, sid=st["id"]: self._send(sid, c.currentData()))
            h.addWidget(combo)
            self.play_rows.addWidget(row)

    def _send(self, sid, deck):
        from ..mixer import routing
        routing.send(sid, deck)
        self._streams_sig = None
        QTimer.singleShot(300, self._refresh_streams)

    def showEvent(self, e):
        super().showEvent(e)
        self._streams_sig = None
        self._refresh_streams()

    @staticmethod
    def _pretty(name: str) -> str:
        m = re.match(r"Traktor Kontrol S4 Analog Stereo (?:Channel |Input )?([CD])$", name)
        if m:
            return f"S4 rear input {m.group(1)}"
        return name

    def _pick(self, strip):
        name = self.src[strip].currentData()
        if name:
            self.mixer.set_source(strip, name)

    def on_event(self, ev):
        if ev["t"] == "mixer_meters":
            for k, bar in self.bars.items():
                peak = ev["m"].get(k, 0.0)
                db = 20 * math.log10(peak) if peak > 1e-6 else -60
                bar.setValue(int(max(0, min(100, (db + 48) / 48 * 100))))
            self.clip.setText(f"<span style='color:{theme.BAD}; font-weight:700'>LIMITING</span>"
                              if ev.get("clip") else "")
            if ev.get("xruns"):
                self.info_xruns = ev["xruns"]
        else:
            self._render()

    def _render(self):
        st = self.mixer.status
        state = st.get("state", "off")
        on = state in ("running", "starting")
        self.toggle.setText("Stop mixer" if on else "Start mixer")
        self.toggle.setObjectName("" if on else "primary")
        self.toggle.style().unpolish(self.toggle)
        self.toggle.style().polish(self.toggle)
        if state == "running":
            outs = st.get("outputs", {})
            miss = [n for n, ok in (("main out", outs.get("main")), ("headphones", outs.get("phones"))) if not ok]
            self.state.setText(f"<span style='color:{theme.GOOD}; font-weight:700'>● Mixing</span> "
                               f"<span style='color:{theme.MUTED}'>{st.get('samplerate', 0) // 1000} kHz · "
                               f"{st.get('blocksize', 0)}-sample blocks ("
                               f"{st.get('blocksize', 0) / max(1, st.get('samplerate', 48000)) * 1000:.1f} ms)</span>"
                               + (f"<br><span style='color:{theme.WARN}'>Couldn't find the S4's "
                                  f"{' and '.join(miss)} in PipeWire. Check the Health page.</span>" if miss else ""))
        elif state == "starting":
            self.state.setText(f"<span style='color:{theme.WARN}'>Starting…</span>")
        elif state == "error":
            self.state.setText(f"<span style='color:{theme.BAD}; font-weight:700'>Not running.</span> "
                               f"{st.get('error', '')}")
        else:
            self.state.setText(f"<span style='color:{theme.MUTED}'>Off. Your DJ software has the S4 as usual.</span>")
        avail = st.get("available", [])
        cur = st.get("sources", {})
        for sname, combo in self.src.items():
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("— nothing —", "")
            for n in avail:
                if n.startswith("S4 Bridge Mixer"):
                    continue
                combo.addItem(self._pretty(n), n)
            idx = combo.findData(cur.get(sname, ""))
            combo.setCurrentIndex(max(0, idx))
            combo.setEnabled(state == "running")
            combo.blockSignals(False)
        if state != "running":
            for bar in self.bars.values():
                bar.setValue(0)
            self.clip.setText("")
        self.info.setText("The S4's LEVEL knob sets the final volume. A soft limiter keeps the main out from "
                          "ever hard-clipping; “LIMITING” means you're driving it. Ease off a GAIN.")


# ============================================================== Health page
class HealthPage(QWidget):
    COLORS = {"ok": theme.GOOD, "warn": theme.WARN, "fail": theme.BAD, "info": theme.ACCENT_2}
    ICONS = {"ok": "circle-check", "warn": "circle-alert", "fail": "circle-x", "info": "info"}
    WORDS = {"ok": "Good", "warn": "Needs attention", "fail": "Not working", "info": "Note"}

    def __init__(self, core, win):
        super().__init__()
        self.core, self.win = core, win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(page_header("Health check", "Every link from the S4 to your speakers, checked in order. "
                                   "Anything that isn't green says what's wrong and how to fix it."), 1)
        rpt = QPushButton(theme.icon("clipboard-copy", theme.TEXT, 16), "Copy report")
        rpt.setToolTip("Copies your versions and these results, ready to paste into a GitHub issue. "
                       "No personal files or usernames are included.")
        rpt.clicked.connect(self._copy_report)
        head.addWidget(rpt, 0, Qt.AlignTop)
        again = QPushButton(theme.icon("rotate-cw", theme.TEXT, 16), "Check again")
        again.clicked.connect(self.refresh)
        head.addWidget(again, 0, Qt.AlignTop)
        lay.addLayout(head)
        self.summary = QLabel()
        self.summary.setStyleSheet("font-size:15px; font-weight:700;")
        lay.addWidget(self.summary)
        self.list = QVBoxLayout()
        self.list.setSpacing(10)
        lay.addLayout(self.list)
        lay.addStretch(1)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self):
        from ..health import run_checks
        while self.list.count():
            w = self.list.takeAt(0).widget()
            if w:
                w.deleteLater()
        checks = run_checks(self.core)
        bad = [c for c in checks if c.status in ("warn", "fail")]
        if not bad:
            self.summary.setText(f"<span style='color:{theme.GOOD}'>Everything checks out.</span>")
        else:
            self.summary.setText(f"<span style='color:{theme.WARN}'>{len(bad)} thing"
                                 f"{'s' if len(bad) > 1 else ''} to sort out.</span>")
        for c in checks:
            f = QFrame()
            f.setObjectName("card")
            row = QHBoxLayout(f)
            row.setContentsMargins(16, 12, 16, 12)
            row.setSpacing(14)
            ic = QLabel()
            ic.setPixmap(theme.icon(self.ICONS[c.status], self.COLORS[c.status], 26).pixmap(26, 26))
            row.addWidget(ic, 0, Qt.AlignTop)
            text = QVBoxLayout()
            text.setSpacing(3)
            t = QLabel(f"<b>{c.title}</b> &nbsp;<span style='color:{self.COLORS[c.status]}'>"
                       f"{self.WORDS[c.status]}</span>")
            d = QLabel(c.detail)
            d.setWordWrap(True)
            d.setObjectName("muted")
            text.addWidget(t)
            text.addWidget(d)
            if c.command:
                cmd = QLabel(f"<code>{c.command}</code>")
                cmd.setTextInteractionFlags(Qt.TextSelectableByMouse)
                cmd.setWordWrap(True)
                cmd.setStyleSheet("font-family:'JetBrains Mono','Fira Code',monospace; font-size:11px;"
                                  f"background:{theme.PANEL}; border-radius:6px; padding:6px;")
                text.addWidget(cmd)
            row.addLayout(text, 1)
            if c.command:
                cp = QPushButton(theme.icon("clipboard-copy", theme.TEXT, 16), "Copy command")
                cp.clicked.connect(lambda _=False, cmd=c.command: (QApplication.clipboard().setText(cmd),
                                                                    self.win.toast("Command copied")))
                row.addWidget(cp, 0, Qt.AlignVCenter)
            if c.fix:
                b = QPushButton(c.fix_label)
                if c.status != "ok":
                    b.setObjectName("primary")
                b.clicked.connect(lambda _=False, k=c.fix: self._fix(k))
                row.addWidget(b, 0, Qt.AlignVCenter)
            self.list.addWidget(f)

    def _copy_report(self):
        from ..system import build_report
        from ..updates import ISSUES_URL
        QApplication.clipboard().setText(build_report(self.core))
        box = QMessageBox(self)
        box.setWindowTitle("Report copied")
        box.setText("Your diagnostics report is on the clipboard.")
        box.setInformativeText("Open a new issue on GitHub, describe what went wrong, and paste the report "
                               "underneath.")
        open_btn = box.addButton("Open GitHub issue", QMessageBox.AcceptRole)
        box.addButton("Done", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl(ISSUES_URL))

    def _fix(self, key):
        if key == "udev":
            self.win.fix_permissions()
            return
        if key == "setup_mixxx":
            self.win.mapping_page._setup_mixxx()
        elif key == "test_leds":
            self.core.test_leds()
        self.refresh()


# ============================================================== About page
class AboutPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.addWidget(page_header("About S4 Bridge", f"Version {__version__}"))
        c, l = card()
        txt = QLabel(
            "<p>S4 Bridge turns the original (MK1) Traktor Kontrol S4 into a class-compliant-feeling MIDI "
            "controller with full LED feedback, so it works with Mixxx, DAWs and anything else that speaks MIDI.</p>"
            "<p>Copyright © 2026 Fancy Butler. Free software under the "
            "<b>GNU General Public License v3.0 or later</b>.</p>"
            "<p><b>Standing on the shoulders of</b><br>"
            "• Daniel Mack's <i>snd-usb-caiaq</i> Linux driver (controls, LEDs and audio)<br>"
            "• Conal Moloney's <i>traktor-s4-mk1-midify</i> hardware-tested control map (MIT)<br>"
            "• Javier Manera's <i>traktor-kontrol-s4-mk1-driver-linux</i> (extra button codes)<br>"
            "• Lucide icons (ISC)</p>"
            "<p style='color:#8b919e'>Not affiliated with Native Instruments. Traktor and Kontrol are "
            "trademarks of their respective owner.</p>")
        txt.setWordWrap(True)
        txt.setTextFormat(Qt.RichText)
        txt.setOpenExternalLinks(True)
        l.addWidget(txt)
        lay.addWidget(c)
        lay.addStretch(1)


# ============================================================== Window
class MainWindow(QMainWindow):
    def __init__(self, core):
        super().__init__()
        self.core = core
        self.setWindowTitle("S4 Bridge")
        self.setMinimumSize(*self.MIN_SIZE)
        self._fit_to_screen()
        self.setWindowIcon(theme.icon("disc-3", theme.ACCENT, 64))
        self.events = Events()
        self.events.event.connect(self._on_event)
        self.events.status.connect(self._on_status)
        core.translator.listeners.append(self.events.event.emit)
        core.status_listeners.append(self.events.status.emit)
        core.mixer.listeners.append(self.events.event.emit)
        self._dirty = False
        self._count = 0

        root = QWidget()
        root.setObjectName("root")
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        sb = QWidget()
        sb.setObjectName("sidebar")
        sb.setFixedWidth(230)
        self.sidebar = sb
        sl = QVBoxLayout(sb)
        sl.setContentsMargins(14, 18, 14, 14)
        sl.setSpacing(4)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(theme.icon("disc-3", theme.ACCENT, 30).pixmap(30, 30))
        brand.addWidget(logo)
        bt = QVBoxLayout()
        bt.setSpacing(0)
        b1 = QLabel(f"S4 Bridge <span style='color:{theme.MUTED}; font-weight:600'>{__version__}</span>")
        b1.setObjectName("brand")
        b1.setTextFormat(Qt.RichText)
        b2 = QLabel("Kontrol S4 MK1 → MIDI")
        b2.setObjectName("brandSub")
        bt.addWidget(b1)
        bt.addWidget(b2)
        self.brand_labels = (b1, b2)
        brand.addLayout(bt)
        brand.addStretch(1)
        sl.addLayout(brand)
        sl.addSpacing(18)

        self.stack = QStackedWidget()
        self.surface_page = SurfacePage(core, self)
        self.mapping_page = MappingPage(core, self)
        self.monitor_page = MonitorPage(core)
        self.settings_page = SettingsPage(core, self)
        self.health_page = HealthPage(core, self)
        self.mixer_page = MixerPage(core, self)
        pages = [("Surface", "layout-dashboard", self.surface_page),
                 ("Mapping", "sliders-horizontal", self.mapping_page),
                 ("Mixer", "sliders-vertical", self.mixer_page),
                 ("Monitor", "activity", self.monitor_page),
                 ("Health", "heart-pulse", self.health_page),
                 ("Settings", "settings-2", self.settings_page),
                 ("About", "info", AboutPage())]
        grp = QButtonGroup(self)
        grp.setExclusive(True)
        self.nav = []
        self._page_index = {}
        for i, (name, ic, page) in enumerate(pages):
            sa = QScrollArea()
            sa.setWidget(page)
            sa.setWidgetResizable(True)
            sa.setFrameShape(QFrame.NoFrame)
            sa.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")
            self.stack.addWidget(sa)
            self._page_index[page] = i
            b = QToolButton()
            b.setObjectName("nav")
            b.setText(f"  {name}")
            b.setIcon(theme.icon(ic, theme.MUTED, 18))
            b.setIconSize(QSize(18, 18))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setCheckable(True)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.clicked.connect(lambda _=False, i=i, ic=ic: self.go(i))
            b.setToolTip(name)
            b.setProperty("label", f"  {name}")
            grp.addButton(b)
            self.nav.append((b, ic))
            sl.addWidget(b)
        sl.addStretch(1)

        from .sidebar import DeckMini
        self.deck_mini = DeckMini(core)
        sl.addWidget(self.deck_mini)
        sl.addSpacing(10)
        badge_w = QWidget()
        badge = QVBoxLayout(badge_w)
        badge.setContentsMargins(0, 0, 0, 0)
        badge.setSpacing(2)
        self.badge = badge_w
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addStretch(1)
        bi = QLabel()
        bi.setPixmap(theme.icon("usb", theme.WARN, 20).pixmap(20, 20))
        top.addWidget(bi, 0, Qt.AlignVCenter)
        bt1 = QLabel("USB · NHL · unchained")
        bt1.setStyleSheet(f"color:{theme.WARN}; font-weight:700;")
        top.addWidget(bt1, 0, Qt.AlignVCenter)
        top.addStretch(1)
        badge.addLayout(top)
        bt2 = QLabel(f"<span style='color:{theme.MUTED}'>Traktor-only since 2010.</span><br>"
                     f"<span style='color:{theme.TEXT}; font-weight:700'>Not anymore.</span>")
        bt2.setTextFormat(Qt.RichText)
        bt2.setAlignment(Qt.AlignHCenter)
        bt2.setStyleSheet("font-size:11px;")
        badge.addWidget(bt2)
        self.update_link = QLabel()
        self.update_link.setTextFormat(Qt.RichText)
        self.update_link.setAlignment(Qt.AlignHCenter)
        self.update_link.setOpenExternalLinks(True)
        self.update_link.setStyleSheet("font-size:12px; padding-top:6px;")
        self.update_link.hide()
        badge.addWidget(self.update_link)
        sl.addWidget(badge_w)
        sl.addSpacing(10)

        sc, scl = card()
        scl.setContentsMargins(12, 12, 12, 12)
        self.pill = QLabel()
        self.pill.setObjectName("pill")
        scl.addWidget(self.pill, 0, Qt.AlignLeft)
        self.status_detail = QLabel()
        self.status_detail.setObjectName("muted")
        self.status_detail.setWordWrap(True)
        self.status_detail.setStyleSheet("font-size:11px;")
        scl.addWidget(self.status_detail)
        sl.addWidget(sc)
        self.status_card = sc
        self.status_lay = scl
        self._compact = None
        self._fixing = False

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        self.banner.setStyleSheet(f"QFrame#banner {{ background:#2a1a08; border-bottom:1px solid {theme.ACCENT}; }}")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(20, 10, 16, 10)
        bi = QLabel()
        bi.setPixmap(theme.icon("shield-alert", theme.ACCENT, 20).pixmap(20, 20))
        bl.addWidget(bi)
        self.banner_text = QLabel()
        self.banner_text.setWordWrap(True)
        bl.addWidget(self.banner_text, 1)
        self.banner_btn = QPushButton(theme.icon("wrench", "#1a0f03", 16), "Fix it")
        self.banner_btn.setObjectName("primary")
        self.banner_btn.clicked.connect(self.fix_permissions)
        bl.addWidget(self.banner_btn)
        self.banner.hide()
        rl.addWidget(self.banner)
        rl.addWidget(self.stack, 1)
        h.addWidget(sb)
        h.addWidget(right, 1)
        self.setCentralWidget(root)
        self.statusBar().clearMessage()  # quiet until there is something to say (toasts fade after 4 s)
        self.sb_version = QLabel()
        self.sb_version.setTextFormat(Qt.RichText)
        self.sb_version.setOpenExternalLinks(True)
        self.sb_version.setStyleSheet(f"color:{theme.MUTED}; padding-right:10px;")
        self.statusBar().addPermanentWidget(self.sb_version)
        self._update_sb_version()
        self.surface_page.surface.picked.connect(self.mapping_page.select)
        self.go(0)
        self._on_status(*core.status)

        t = QTimer(self)
        t.timeout.connect(self._rate)
        t.start(1000)
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self.core.sync_mixxx)
        self._sync_timer.start(30000)
        from .tray import Tray
        self.tray = Tray(self) if Tray.available() else None
        self._really_quit = False
        self._init_updates()
        esc = QAction(self)
        esc.setShortcut(QKeySequence(Qt.Key_Escape))
        esc.triggered.connect(self.mapping_page.cancel_identify)
        self.addAction(esc)

    MIN_SIZE = (900, 600)

    def go_page(self, page):
        self.go(self._page_index[page])

    # ------------------------------------------------------------ sizing
    def _fit_to_screen(self):
        from PySide6.QtCore import QByteArray
        geo = self.core.settings.get("window_geometry")
        if geo:
            try:
                if self.restoreGeometry(QByteArray.fromBase64(geo.encode())):
                    return
            except Exception:
                pass
        scr = QApplication.primaryScreen()
        avail = scr.availableGeometry() if scr else None
        w, h = 1480, 940
        if avail:
            w, h = min(w, int(avail.width() * 0.9)), min(h, int(avail.height() * 0.9))
        self.resize(max(900, w), max(600, h))

    def _save_geometry(self):
        self.core.settings["window_geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.core.save_settings()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        compact = self.width() < 1200
        if compact == self._compact:
            return
        self._compact = compact
        # narrow window: the sidebar folds into an icon rail
        self.sidebar.setFixedWidth(72 if compact else 230)
        for lbl in self.brand_labels:
            lbl.setVisible(not compact)
        for b, _ic in self.nav:
            b.setText("" if compact else b.property("label"))
            b.setToolButtonStyle(Qt.ToolButtonIconOnly if compact else Qt.ToolButtonTextBesideIcon)
        self.deck_mini.setVisible(not compact)
        self.badge.setVisible(not compact)
        self.status_detail.setVisible(not compact)
        m = 4 if compact else 12
        self.status_lay.setContentsMargins(m, m, m, m)
        self.status_lay.setAlignment(self.pill, Qt.AlignCenter if compact else Qt.AlignLeft)
        name = getattr(self, "_pill_name", "")
        if name:
            self.pill.setText("●" if compact else name)
        self._update_sb_version()

    def go(self, i):
        self.stack.setCurrentIndex(i)
        for j, (b, ic) in enumerate(self.nav):
            b.setChecked(i == j)
            b.setIcon(theme.icon(ic, theme.ACCENT if i == j else theme.MUTED, 18))

    def toast(self, msg):
        self.statusBar().showMessage(msg, 4000)

    def set_dirty(self, v):
        self._dirty = v
        self.setWindowTitle("S4 Bridge" + (" •  unsaved changes" if v else ""))

    def describe(self, cid, label: QLabel):
        c = self.core.hw.controls.get(cid)
        if not c:
            return
        m = self.core.profile["map"].get(area_key(c.area, c.func))
        src, col, tip = SOURCE_TXT[c.source]
        area = {"L": "Left deck", "R": "Right deck", "G": "Center"}.get(c.area, c.area if c.area.startswith("FX") else f"Mixer {c.area}")
        lines = [f"<b style='font-size:14px'>{friendly(c)}</b> <span style='color:{theme.MUTED}'>· {area}</span>",
                 f"<span style='color:{theme.MUTED}'>{KIND_TXT[c.kind]} · event "
                 f"{c.code if c.code is not None else '—'}</span>",
                 f"<span style='color:{col}'>● {src}</span> <span style='color:{theme.MUTED}'>{tip}</span>"]
        if m:
            ch = self.core.translator._channel(c) + 1
            lines.append(f"Sends <b>{'Note' if m['type'] == 'note' else 'CC'} {m['num']:#04x}</b> on ch {ch}"
                         + (f" (deck {self.core.translator.active[c.area]})" if c.area in 'LR' else ""))
        if c.note:
            lines.append(f"<span style='color:{theme.MUTED}'>{c.note}</span>")
        label.setText("<br>".join(lines))

    def _on_event(self, ev):
        k = ev["t"]
        if k.startswith("mixer_"):
            self.mixer_page.on_event(ev)
            if k == "mixer_status" and getattr(self, "tray", None):
                self.tray.mixer_act.setChecked(self.core.mixer.running)
            return
        self.deck_mini.ping(k)
        self.monitor_page.push(ev)
        if k in ("in", "unknown"):
            self.mapping_page.on_raw(ev)
        if k == "in":
            self.surface_page.surface.mark(ev["cid"])
        elif k == "out":
            self._count += 1
            self.surface_page.last.setText(midi_text(ev["msg"]) + f"\n{ev.get('cid') or ''}")
        elif k == "deck":
            self.surface_page.refresh()
        elif k == "unknown":
            from ..hw.usb_s4 import EXTRA_BASE
            told = self.__dict__.setdefault("_told_unknown", set())
            if ev["code"] < EXTRA_BASE and ev["code"] not in told:   # once per code; raw bytes stay on Monitor
                told.add(ev["code"])
                self.toast(f"Unidentified control (event {ev['code']}). Name it in Mapping › Identify.")

    def _rate(self):
        self.surface_page.rate.setText(f"{self._count} msg/s")
        self._count = 0

    # ------------------------------------------------------------ permissions
    def fix_permissions(self):
        from ..health import UDEV_CMD
        from ..system import can_elevate, udev_install_script
        if not can_elevate():
            QApplication.clipboard().setText(UDEV_CMD)
            QMessageBox.information(self, "Needs a terminal",
                                    "This system has no graphical password prompt (pkexec). The fix command "
                                    "is on your clipboard: paste it into a terminal, then switch the S4 off "
                                    "and on.")
            return
        self._fixing = True
        self.banner_btn.setEnabled(False)
        self.banner_text.setText("Waiting for your password…")
        self.banner.show()
        self._fix_proc = QProcess(self)
        self._fix_proc.finished.connect(self._fix_done)
        self._fix_proc.start("pkexec", ["/bin/sh", "-c", udev_install_script()])

    def _fix_done(self, code, _status=None):
        self._fixing = False
        self.banner_btn.setEnabled(True)
        if code == 0:
            self.banner.hide()
            self.toast("Permissions fixed. The S4 will connect in a moment.")
        else:
            self.banner_text.setText("That didn't go through (cancelled, or the password was wrong). Press "
                                     "Fix it to try again.")
            self.banner.show()
        if self.stack.currentIndex() == self._page_index[self.health_page]:
            self.health_page.refresh()

    # ------------------------------------------------------------ update check
    def _init_updates(self):
        from PySide6.QtNetwork import QNetworkAccessManager
        self._net = QNetworkAccessManager(self)
        latest = self.core.settings.get("update_latest")
        if latest:
            self._show_update(latest, self.core.settings.get("update_url"))
        self._upd_timer = QTimer(self)
        self._upd_timer.timeout.connect(self.check_updates)
        self._upd_timer.start(6 * 3600 * 1000)
        QTimer.singleShot(15000, self.check_updates)  # let startup settle first

    def check_updates(self, force=False):
        from PySide6.QtNetwork import QNetworkRequest
        from .. import updates
        if self.core.demo and not force:
            return
        if not force and not updates.due(self.core.settings):
            return
        req = QNetworkRequest(QUrl(updates.API_URL))
        req.setRawHeader(b"User-Agent", updates.USER_AGENT.encode())
        req.setRawHeader(b"Accept", b"application/vnd.github+json")
        reply = self._net.get(req)
        reply.finished.connect(lambda r=reply: self._update_reply(r))

    def _update_reply(self, reply):
        import time
        from PySide6.QtNetwork import QNetworkReply
        from .. import updates
        try:
            if reply.error() != QNetworkReply.NoError:
                return  # offline, rate-limited, repo not public yet: say nothing
            self.core.settings["update_checked_at"] = time.time()
            rel = updates.parse_release(bytes(reply.readAll()))
            if rel and updates.is_newer(rel[0], __version__):
                self.core.settings["update_latest"], self.core.settings["update_url"] = rel
                self._show_update(*rel)
            else:
                self.core.settings.pop("update_latest", None)
                self.update_link.hide()
                self._update_sb_version()
            self.core.save_settings()
        finally:
            reply.deleteLater()

    def _show_update(self, version, url):
        from .. import updates
        if not updates.is_newer(version, __version__):
            self.update_link.hide()
            self._update_sb_version()
            return
        self.update_link.setText(f"<a href='{url or updates.RELEASES_URL}' style='color:{theme.ACCENT};"
                                 f" text-decoration:none'>New version {version} ›</a>")
        self.update_link.setToolTip("Open the release page")
        self.update_link.show()
        self._update_sb_version()

    def _update_sb_version(self):
        """Folded sidebar hides the version and update link, so they move to the status bar."""
        if not hasattr(self, "sb_version"):
            return
        text = f"S4 Bridge {__version__}"
        if not self.update_link.isHidden():
            text += f" &nbsp;·&nbsp; {self.update_link.text()}"
        self.sb_version.setText(text)
        self.sb_version.setVisible(bool(self._compact))

    def _on_status(self, state, detail):
        colors = {"connected": (theme.GOOD, "#0f2a1b"), "waiting": (theme.WARN, "#2a230f"),
                  "error": (theme.BAD, "#2a1010"), "starting": (theme.MUTED, "#1c1f26")}
        fg, bg = colors.get(state, colors["starting"])
        name = {"connected": "● Demo" if self.core.demo else "● Connected", "waiting": "● Waiting",
                "error": "● Error", "starting": "● Starting"}[state]
        self._pill_name = name
        self.pill.setText("●" if self._compact else name)
        self.pill.setStyleSheet(f"color:{fg}; background:{bg};")
        self.status_detail.setText(detail or "")
        self.status_card.setToolTip(f"{name[2:]}: {detail}" if detail else name[2:])
        need = state == "error" and "permission" in (detail or "").lower()
        if need and not self._fixing:
            self.banner_text.setText("S4 Bridge isn't allowed to read the S4's controls yet. One-time fix: "
                                     "it asks for your password once.")
        self.banner.setVisible(need or self._fixing)
        self.surface_page.refresh()
        if getattr(self, "tray", None):
            self.tray.set_state(state, detail)

    def show_window(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self._really_quit = True
        self.close()

    def hideEvent(self, e):
        self._save_geometry()
        super().hideEvent(e)

    def closeEvent(self, e):
        self._save_geometry()
        if self.tray and not self._really_quit and self.core.settings.get("close_to_tray", True):
            e.ignore()
            self.hide()
            if not self.core.settings.get("tray_hint_shown"):
                self.tray.showMessage("S4 Bridge is still running",
                                      "Your S4 keeps working. Click the tray icon to open S4 Bridge, "
                                      "or right-click › Quit.", theme.icon("disc-3", theme.ACCENT, 32), 6000)
                self.core.settings["tray_hint_shown"] = True
                self.core.save_settings()
            return
        if self._dirty:
            r = QMessageBox.question(self, "Unsaved mapping", "Save your mapping changes before quitting?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Cancel:
                e.ignore()
                return
            if r == QMessageBox.Save:
                self.mapping_page._save()
        if self.tray:
            self.tray.hide()
        self.core.stop()
        e.accept()
        QApplication.quit()
