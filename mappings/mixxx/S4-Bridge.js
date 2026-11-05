// S4 Bridge 0.3.3 - Mixxx mapping for the Traktor Kontrol S4 MK1
// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Fancy Butler
//
// Generated to match your S4 Bridge profile. Deck switching (A/C, B/D) and
// per-deck LED memory are done by S4 Bridge itself, so this script simply
// treats the S4 as four independent decks on MIDI channels.

var S4B = {};
S4B.cfg = {
  "deckChannels": {
    "A": 0,
    "B": 1,
    "C": 2,
    "D": 3
  },
  "globalChannel": 4,
  "relative": "offset",
  "ticksPerRev": 1024,
  "out": {
    "deck.load": {
      "type": "note",
      "num": 1
    },
    "deck.jog": {
      "type": "cc",
      "num": 2
    },
    "deck.touch": {
      "type": "note",
      "num": 3
    },
    "deck.tempo": {
      "type": "cc",
      "num": 4,
      "hires": true
    },
    "deck.tempo_down": {
      "type": "note",
      "num": 5
    },
    "deck.tempo_up": {
      "type": "note",
      "num": 6
    },
    "deck.shift": {
      "type": "note",
      "num": 7,
      "shiftable": false
    },
    "deck.sync": {
      "type": "note",
      "num": 8
    },
    "deck.cue": {
      "type": "note",
      "num": 9
    },
    "deck.play": {
      "type": "note",
      "num": 10
    },
    "deck.hotcue1": {
      "type": "note",
      "num": 11
    },
    "deck.hotcue2": {
      "type": "note",
      "num": 12
    },
    "deck.hotcue3": {
      "type": "note",
      "num": 13
    },
    "deck.hotcue4": {
      "type": "note",
      "num": 14
    },
    "deck.sample1": {
      "type": "note",
      "num": 15
    },
    "deck.sample2": {
      "type": "note",
      "num": 16
    },
    "deck.sample3": {
      "type": "note",
      "num": 17
    },
    "deck.sample4": {
      "type": "note",
      "num": 18
    },
    "deck.move": {
      "type": "cc",
      "num": 19
    },
    "deck.move_press": {
      "type": "note",
      "num": 19
    },
    "deck.size": {
      "type": "cc",
      "num": 21
    },
    "deck.size_press": {
      "type": "note",
      "num": 21
    },
    "deck.loop_in": {
      "type": "note",
      "num": 23
    },
    "deck.loop_out": {
      "type": "note",
      "num": 24
    },
    "deck.deck_toggle": {
      "type": "note",
      "num": 25,
      "shiftable": false
    },
    "strip.gain": {
      "type": "cc",
      "num": 60
    },
    "strip.gain_press": {
      "type": "note",
      "num": 61
    },
    "strip.fx1": {
      "type": "note",
      "num": 62
    },
    "strip.fx2": {
      "type": "note",
      "num": 63
    },
    "strip.hi": {
      "type": "cc",
      "num": 64
    },
    "strip.mid": {
      "type": "cc",
      "num": 65
    },
    "strip.low": {
      "type": "cc",
      "num": 66
    },
    "strip.filter": {
      "type": "cc",
      "num": 67
    },
    "strip.cue": {
      "type": "note",
      "num": 68
    },
    "strip.volume": {
      "type": "cc",
      "num": 69
    },
    "G.browse": {
      "type": "cc",
      "num": 2
    },
    "G.browse_press": {
      "type": "note",
      "num": 3
    },
    "G.loop_drywet": {
      "type": "cc",
      "num": 4
    },
    "G.loop_size": {
      "type": "note",
      "num": 5
    },
    "G.loop_undo": {
      "type": "note",
      "num": 6
    },
    "G.loop_rec": {
      "type": "note",
      "num": 7
    },
    "G.loop_play": {
      "type": "note",
      "num": 8
    },
    "G.browse_btn": {
      "type": "note",
      "num": 9
    },
    "G.crossfader": {
      "type": "cc",
      "num": 10
    },
    "G.snap": {
      "type": "note",
      "num": 11
    },
    "G.master": {
      "type": "note",
      "num": 12
    },
    "G.quant": {
      "type": "note",
      "num": 13
    },
    "G.mic_volume": {
      "type": "cc",
      "num": 14
    },
    "G.cue_mix": {
      "type": "cc",
      "num": 15
    },
    "FX1.drywet": {
      "type": "cc",
      "num": 20
    },
    "FX1.k1": {
      "type": "cc",
      "num": 21
    },
    "FX1.k2": {
      "type": "cc",
      "num": 22
    },
    "FX1.k3": {
      "type": "cc",
      "num": 23
    },
    "FX1.on": {
      "type": "note",
      "num": 24
    },
    "FX1.b1": {
      "type": "note",
      "num": 25
    },
    "FX1.b2": {
      "type": "note",
      "num": 26
    },
    "FX1.b3": {
      "type": "note",
      "num": 27
    },
    "FX1.mode": {
      "type": "note",
      "num": 28
    },
    "FX2.drywet": {
      "type": "cc",
      "num": 30
    },
    "FX2.k1": {
      "type": "cc",
      "num": 31
    },
    "FX2.k2": {
      "type": "cc",
      "num": 32
    },
    "FX2.k3": {
      "type": "cc",
      "num": 33
    },
    "FX2.on": {
      "type": "note",
      "num": 34
    },
    "FX2.b1": {
      "type": "note",
      "num": 35
    },
    "FX2.b2": {
      "type": "note",
      "num": 36
    },
    "FX2.b3": {
      "type": "note",
      "num": 37
    },
    "FX2.mode": {
      "type": "note",
      "num": 38
    },
    "deck.on_air": {
      "type": "note",
      "num": 96
    },
    "deck.samples": {
      "type": "note",
      "num": 97
    },
    "deck.keylock": {
      "type": "note",
      "num": 98
    },
    "deck.master_ind": {
      "type": "note",
      "num": 99
    },
    "deck.display": {
      "type": "cc",
      "num": 80
    },
    "deck.rate_fb": {
      "type": "cc",
      "num": 81
    },
    "deck.display_dot": {
      "type": "cc",
      "num": 84
    },
    "strip.meter": {
      "type": "cc",
      "num": 70
    },
    "strip.xf_left": {
      "type": "note",
      "num": 71
    },
    "strip.xf_right": {
      "type": "note",
      "num": 72
    },
    "strip.active": {
      "type": "note",
      "num": 73
    },
    "G.quant_ind": {
      "type": "note",
      "num": 112
    },
    "G.headphone_ind": {
      "type": "note",
      "num": 113
    },
    "G.master_ind": {
      "type": "note",
      "num": 114
    },
    "G.snap_ind": {
      "type": "note",
      "num": 115
    },
    "G.warning": {
      "type": "note",
      "num": 116
    }
  }
};
S4B.shifted = {};
S4B.connections = [];
S4B.tempoMsb = {};

var DECKS = {"[Channel1]": "A", "[Channel2]": "B", "[Channel3]": "C", "[Channel4]": "D"};
var GROUPS = {A: "[Channel1]", B: "[Channel2]", C: "[Channel3]", D: "[Channel4]"};
var NUM = {"[Channel1]": 1, "[Channel2]": 2, "[Channel3]": 3, "[Channel4]": 4};

S4B.rel = function(value) {
    if (S4B.cfg.relative === "twos") { return value < 64 ? value : value - 128; }
    return value - 64;
};

S4B.send = function(key, group, value) {
    var m = S4B.cfg.out[key];
    if (!m) { return; }
    var ch = key.indexOf("deck.") === 0 || key.indexOf("strip.") === 0
        ? S4B.cfg.deckChannels[DECKS[group]] : S4B.cfg.globalChannel;
    midi.sendShortMsg((m.type === "note" ? 0x90 : 0xB0) | ch, m.num, value);
};

S4B.toggle = function(group, key) { engine.setValue(group, key, !engine.getValue(group, key)); };
S4B.noop = function() {};
S4B.shifted.noop = S4B.noop;

// ---------------------------------------------------------------- platter safety
// The stopped-deck jog grabs the track like a platter (scratch). Mixxx treats a
// scratching deck as "not freely playing", so a grab that never let go would
// make PLAY/CUE misbehave. Every transport action lets go first, no matter what.
S4B.touching = {};
S4B.idleTimer = {};
S4B.releasePlatter = function(group) {
    var deck = NUM[group];
    if (!deck) { return; }
    if (S4B.idleTimer[deck]) { engine.stopTimer(S4B.idleTimer[deck]); S4B.idleTimer[deck] = 0; }
    if (!S4B.touching[deck] && engine.isScratching(deck)) { engine.scratchDisable(deck, false); }
};

// ---------------------------------------------------------------- transport
S4B.play = function(ch, ctl, value, status, group) {
    if (value) { S4B.releasePlatter(group); S4B.toggle(group, "play"); }
};
S4B.shifted.play = function(ch, ctl, value, status, group) { if (value) { S4B.toggle(group, "keylock"); } };
// Traktor-style CUE. Paused: the cue goes on the exact sample under the
// cursor (written directly, so Mixxx's quantize can't move it) unless the S4's
// SNAP button is lit (SNAP also governs loop IN/OUT and the auto loop), in which case it snaps to the beat grid like Traktor's
// Snap. Holding plays from the cue; release snaps back; PLAY while holding keeps
// it going. Playing: back to the cue and stop.
S4B.snapCue = false;
S4B.cue = function(ch, ctl, value, status, group) {
    if (value) { S4B.releasePlatter(group); }
    if (value && !engine.getValue(group, "play")) {
        if (S4B.snapCue) {
            engine.setValue(group, "cue_set", 1);
            engine.setValue(group, "cue_set", 0);
        } else {
            var samples = engine.getValue(group, "track_samples");
            var pos = Math.round(engine.getValue(group, "playposition") * samples);
            pos -= pos % 2;                                        // stereo frame boundary
            engine.setValue(group, "cue_point", Math.max(0, Math.min(samples, pos)));
        }
    }
    // cue_cdj = Pioneer/Traktor behaviour regardless of Mixxx's Cue mode preference
    engine.setValue(group, "cue_cdj", value ? 1 : 0);
};
S4B.shifted.cue = function(ch, ctl, value, status, group) { if (value) { engine.setValue(group, "start", 1); } };
S4B.sync = function(ch, ctl, value, status, group) { if (value) { S4B.toggle(group, "sync_enabled"); } };
S4B.shifted.sync = function(ch, ctl, value, status, group) { if (value) { S4B.toggle(group, "sync_leader"); } };
S4B.load = function(ch, ctl, value, status, group) {
    if (value) { S4B.releasePlatter(group); engine.setValue(group, "LoadSelectedTrack", 1); }
};
S4B.shifted.load = function(ch, ctl, value, status, group) { if (value) { engine.setValue(group, "eject", 1); } };

// ---------------------------------------------------------------- hot cues (pads 1-4)
[1, 2, 3, 4].forEach(function(n) {
    S4B["hotcue" + n] = function(ch, ctl, value, status, group) {
        if (value) { S4B.releasePlatter(group); }
        engine.setValue(group, "hotcue_" + n + "_activate", value ? 1 : 0);
    };
    S4B.shifted["hotcue" + n] = function(ch, ctl, value, status, group) {
        if (value) { engine.setValue(group, "hotcue_" + n + "_clear", 1); }
    };
});

// ---------------------------------------------------------------- the play-arrow row: pad modes
// SHIFT + push MOVE cycles each side through:
//   SAMPLES - Traktor-style sample slots (left = samplers 1-4, right = 5-8)
//   STEMS   - Mixxx 2.6+: mute/unmute drums, bass, other, vocals; hold a pad and
//             turn MOVE for that stem's volume; SHIFT + pad toggles its quick effect
//   ROLLS   - hold for a 1/8, 1/4, 1/2, 1 beat loop roll (snaps back on release)
// The SAMPLES lamp shows the mode: on = samples, off = stems, blinking = rolls.
S4B.MODES = ["samples", "stems", "rolls"];
S4B.MODE_WORD = {samples: 105, stems: 106, rolls: 107};
S4B.ROLLS = [0.125, 0.25, 0.5, 1];
S4B.padMode = {L: "samples", R: "samples"};
S4B.heldStem = {};
S4B.sideOf = function(group) { return (group === "[Channel1]" || group === "[Channel3]") ? "L" : "R"; };
S4B.sideGroups = function(side) { return side === "L" ? ["[Channel1]", "[Channel3]"] : ["[Channel2]", "[Channel4]"]; };
S4B.stemGroup = function(group, n) { return "[" + group.substring(1, group.length - 1) + "_Stem" + n + "]"; };

S4B.samplerGroup = function(group, n) {
    return "[Sampler" + (S4B.sideOf(group) === "L" ? n : n + 4) + "]";
};

S4B.cyclePadMode = function(group) {
    var side = S4B.sideOf(group);
    var i = S4B.MODES.indexOf(S4B.padMode[side]);
    S4B.padMode[side] = S4B.MODES[(i + 1) % S4B.MODES.length];
    S4B.sideGroups(side).forEach(function(g) {
        S4B.flashWord(g, S4B.MODE_WORD[S4B.padMode[side]]);
        S4B.padLeds(g);
    });
};

S4B.padLeds = function(group) {
    var side = S4B.sideOf(group), mode = S4B.padMode[side];
    for (var n = 1; n <= 4; n++) {
        var v = 0;
        if (mode === "samples") {
            var sg = S4B.samplerGroup(group, n);
            v = engine.getValue(sg, "play_indicator") ? 127 : (engine.getValue(sg, "track_loaded") ? 25 : 0);
        } else if (mode === "stems") {
            if (n <= engine.getValue(group, "stem_count")) {
                var st = S4B.stemGroup(group, n);
                v = engine.getValue(st, "mute") ? 8 : 127;
            }
        } else {
            v = (S4B.rollHeld[group] === n) ? 127 : 20;
        }
        S4B.send("deck.sample" + n, group, v);
    }
    S4B.samplesLamp(group);
};

S4B.samplesLamp = function(group) {
    var mode = S4B.padMode[S4B.sideOf(group)];
    var on = mode === "samples" || (mode === "rolls" && S4B.blink);
    S4B.send("deck.samples", group, on ? 127 : 0);
};

S4B.rollHeld = {};
[1, 2, 3, 4].forEach(function(n) {
    S4B["sample" + n] = function(ch, ctl, value, status, group) {
        var mode = S4B.padMode[S4B.sideOf(group)];
        if (mode === "samples") {
            if (!value) { return; }
            var s = S4B.samplerGroup(group, n);
            if (!engine.getValue(s, "track_loaded")) {
                engine.setValue(s, "LoadSelectedTrack", 1);
            } else {
                engine.setValue(s, "cue_gotoandplay", 1);
            }
        } else if (mode === "stems") {
            if (n > engine.getValue(group, "stem_count")) { return; }
            if (value) {
                S4B.heldStem[group] = {n: n, turned: false};
            } else if (S4B.heldStem[group] && S4B.heldStem[group].n === n) {
                if (!S4B.heldStem[group].turned) { S4B.toggle(S4B.stemGroup(group, n), "mute"); }
                S4B.heldStem[group] = null;
            }
        } else {
            S4B.rollHeld[group] = value ? n : 0;
            engine.setValue(group, "beatlooproll_" + S4B.ROLLS[n - 1] + "_activate", value ? 1 : 0);
            S4B.padLeds(group);
        }
    };
    S4B.shifted["sample" + n] = function(ch, ctl, value, status, group) {
        if (!value) { return; }
        var mode = S4B.padMode[S4B.sideOf(group)];
        if (mode === "samples") {
            var s = S4B.samplerGroup(group, n);
            if (engine.getValue(s, "play")) {
                engine.setValue(s, "cue_gotoandstop", 1);
            } else {
                engine.setValue(s, "eject", 1);
            }
        } else if (mode === "stems") {
            if (n <= engine.getValue(group, "stem_count")) {
                S4B.toggle("[QuickEffectRack1_" + S4B.stemGroup(group, n) + "]", "enabled");
            }
        }
    };
});

// ---------------------------------------------------------------- loops
// Loops follow the same rule as CUE: exact sample under the cursor, unless
// SNAP is lit, in which case Mixxx's beat-snapped loop_in/loop_out are used.
S4B.exactPos = function(group) {
    var samples = engine.getValue(group, "track_samples");
    var pos = Math.round(engine.getValue(group, "playposition") * samples);
    return Math.max(0, Math.min(samples, pos - (pos % 2)));
};
S4B.enableLoop = function(group) {
    if (!engine.getValue(group, "loop_enabled")) { engine.setValue(group, "reloop_toggle", 1); }
};
S4B.loopIn = function(ch, ctl, value, status, group) {
    if (S4B.snapCue) { engine.setValue(group, "loop_in", value ? 1 : 0); return; }
    if (!value) { return; }
    var pos = S4B.exactPos(group);
    if (!engine.getValue(group, "loop_enabled")) {
        engine.setValue(group, "loop_end_position", -1);       // fresh loop: forget the old out point
    }
    engine.setValue(group, "loop_start_position", pos);
};
S4B.loopOut = function(ch, ctl, value, status, group) {
    if (S4B.snapCue) { engine.setValue(group, "loop_out", value ? 1 : 0); return; }
    if (!value) { return; }
    var start = engine.getValue(group, "loop_start_position");
    var pos = S4B.exactPos(group);
    if (start < 0 || pos <= start) { return; }                 // need an IN point before the OUT
    engine.setValue(group, "loop_end_position", pos);
    S4B.enableLoop(group);
};
S4B.shifted.loopIn = function(ch, ctl, value, status, group) { if (value) { engine.setValue(group, "reloop_toggle", 1); } };
S4B.shifted.loopOut = function(ch, ctl, value, status, group) { if (value) { engine.setValue(group, "reloop_andstop", 1); } };
S4B.loopMove = function(ch, ctl, value, status, group) {
    var d = S4B.rel(value);
    var held = S4B.heldStem[group];
    if (held) {                                        // holding a stem pad: MOVE = that stem's volume
        held.turned = true;
        var st = S4B.stemGroup(group, held.n);
        engine.setParameter(st, "volume", Math.max(0, Math.min(1, engine.getParameter(st, "volume") + d * 0.04)));
        return;
    }
    engine.setValue(group, d > 0 ? "beatjump_forward" : "beatjump_backward", 1);
};
S4B.shifted.loopMove = function(ch, ctl, value, status, group) {
    var d = S4B.rel(value);
    engine.setValue(group, d > 0 ? "rate_perm_up_small" : "rate_perm_down_small", 1);
};
S4B.loopSize = function(ch, ctl, value, status, group) {
    engine.setValue(group, S4B.rel(value) > 0 ? "loop_double" : "loop_halve", 1);
};
S4B.shifted.loopSize = function(ch, ctl, value, status, group) {
    var s = engine.getValue(group, "beatjump_size");
    engine.setValue(group, "beatjump_size", S4B.rel(value) > 0 ? Math.min(512, s * 2) : Math.max(1 / 32, s / 2));
};
S4B.reloop = function(ch, ctl, value, status, group) { if (value) { engine.setValue(group, "reloop_toggle", 1); } };
S4B.beatloop = function(ch, ctl, value, status, group) {   // SIZE knob push: auto loop
    if (!value) { return; }
    if (S4B.snapCue) { engine.setValue(group, "beatloop_activate", 1); return; }
    var bpm = engine.getValue(group, "file_bpm"), rate = engine.getValue(group, "track_samplerate");
    if (!bpm || !rate) { engine.setValue(group, "beatloop_activate", 1); return; }
    var start = S4B.exactPos(group);
    var len = Math.round(engine.getValue(group, "beatloop_size") * (60 / bpm) * rate * 2);
    len -= len % 2;
    if (engine.getValue(group, "loop_enabled")) { engine.setValue(group, "reloop_toggle", 1); }
    engine.setValue(group, "loop_end_position", -1);
    engine.setValue(group, "loop_start_position", start);
    engine.setValue(group, "loop_end_position", start + len);
    S4B.enableLoop(group);
};
S4B.shifted.reloop = function(ch, ctl, value, status, group) { if (value) { S4B.cyclePadMode(group); } };
S4B.shifted.beatloop = function(ch, ctl, value, status, group) { if (value) { S4B.cycleDisplay(group); } };

// ---------------------------------------------------------------- tempo (14-bit, MSB then LSB)
S4B.tempoMSB = function(ch, ctl, value, status, group) { S4B.tempoMsb[group] = value; };
S4B.tempoLSB = function(ch, ctl, value, status, group) {
    var v = ((S4B.tempoMsb[group] || 0) << 7) | value;            // 0..16383
    engine.setValue(group, "rate", script.absoluteLin(v, -1, 1, 0, 16383));
};
S4B.nudgeUp = function(ch, ctl, value, status, group) { engine.setValue(group, "rate_temp_up", value ? 1 : 0); };
S4B.nudgeDown = function(ch, ctl, value, status, group) { engine.setValue(group, "rate_temp_down", value ? 1 : 0); };
S4B.shifted.nudgeUp = function(ch, ctl, value, status, group) { if (value) { engine.setValue(group, "rate_set_zero", 1); } };
// FLUX (slip mode, Traktor's signature): SHIFT + OFFSET down. Scratch, loop or
// roll, and the track keeps running underneath; let go and it carries on in time.
S4B.shifted.nudgeDown = function(ch, ctl, value, status, group) {
    if (value) {
        S4B.toggle(group, "slip_enabled");
        S4B.flashWord(group, engine.getValue(group, "slip_enabled") ? 108 : 101);
    }
};

// ---------------------------------------------------------------- jog wheels
S4B.startScratch = function(deck) {
    if (!engine.isScratching(deck)) {
        engine.scratchEnable(deck, S4B.cfg.ticksPerRev, 33 + 1 / 3, 1 / 8, (1 / 8) / 32, true);
    }
};
S4B.touch = function(ch, ctl, value, status, group) {
    var deck = NUM[group];
    if (value && S4B.isBrowsing()) { return; }
    S4B.touching[deck] = !!value;
    if (value) {
        S4B.startScratch(deck);
    } else {
        engine.scratchDisable(deck, true);
    }
};
S4B.shifted.touch = S4B.touch;
S4B.jog = function(ch, ctl, value, status, group) {
    if (S4B.isBrowsing()) { S4B.browseJog(group, value, 1); return; }
    var d = S4B.rel(value), deck = NUM[group];
    if (!engine.isScratching(deck) && !engine.getValue(group, "play")) {
        // stopped: the platter moves the track 1:1, touch or not (for finding cues)
        S4B.startScratch(deck);
    }
    if (engine.isScratching(deck)) {
        engine.scratchTick(deck, d);
        if (!S4B.touching[deck]) {
            // release the platter-scratch shortly after the wheel stops moving
            if (S4B.idleTimer[deck]) { engine.stopTimer(S4B.idleTimer[deck]); }
            S4B.idleTimer[deck] = engine.beginTimer(120, function() {
                S4B.idleTimer[deck] = 0;
                if (!S4B.touching[deck]) { engine.scratchDisable(deck, false); }
            }, true);
        }
    } else {
        // playing, platter edge: pitch-bend nudge
        engine.setValue(group, "jog", Math.max(-3, Math.min(3, d * 0.6)));
    }
};
S4B.shifted.jog = function(ch, ctl, value, status, group) {   // shift + jog = fast search
    if (S4B.isBrowsing()) { S4B.browseJog(group, value, 8); return; }
    var pos = engine.getValue(group, "playposition");
    engine.setValue(group, "playposition", Math.max(0, Math.min(1, pos + S4B.rel(value) / 3000)));
};

// ---------------------------------------------------------------- mixer
S4B.volume = function(ch, ctl, value, status, group) { engine.setParameter(group, "volume", value / 127); };
S4B.eq = function(group, param, value) {
    engine.setParameter("[EqualizerRack1_" + group + "_Effect1]", param, value / 127);
};
S4B.eqHi = function(ch, ctl, value, status, group) { S4B.eq(group, "parameter3", value); };
S4B.eqMid = function(ch, ctl, value, status, group) { S4B.eq(group, "parameter2", value); };
S4B.eqLow = function(ch, ctl, value, status, group) { S4B.eq(group, "parameter1", value); };
S4B.filter = function(ch, ctl, value, status, group) {
    engine.setParameter("[QuickEffectRack1_" + group + "]", "super1", value / 127);
};
S4B.pfl = function(ch, ctl, value, status, group) { if (value) { S4B.toggle(group, "pfl"); } };
// Mixer FX: SHIFT + a channel's CUE steps the FILTER knob's quick effect
// (filter -> other one-knob effects), like Traktor's Mixer FX selector.
S4B.shifted.pfl = function(ch, ctl, value, status, group) {
    if (value) { engine.setValue("[QuickEffectRack1_" + group + "]", "next_chain_preset", 1); }
};
S4B.gain = function(ch, ctl, value, status, group) {
    var g = engine.getParameter(group, "pregain");
    engine.setParameter(group, "pregain", Math.max(0, Math.min(1, g + S4B.rel(value) * 0.02)));
};
S4B.shifted.gain = function(ch, ctl, value, status, group) {   // shift + gain = filter
    var k = "[QuickEffectRack1_" + group + "]";
    var f = engine.getParameter(k, "super1");
    engine.setParameter(k, "super1", Math.max(0, Math.min(1, f + S4B.rel(value) * 0.02)));
};
S4B.gainReset = function(ch, ctl, value, status, group) { if (value) { engine.setValue(group, "pregain", 1); } };
S4B.shifted.gainReset = S4B.gainReset;
S4B.fxAssign = function(unit, group, value) {
    if (value) { S4B.toggle("[EffectRack1_EffectUnit" + unit + "]", "group_" + group + "_enable"); }
};
S4B.fxAssign1 = function(ch, ctl, value, status, group) { S4B.fxAssign(1, group, value); };
S4B.fxAssign2 = function(ch, ctl, value, status, group) { S4B.fxAssign(2, group, value); };
S4B.shifted.fxAssign1 = function(ch, ctl, value, status, group) { S4B.fxAssign(3, group, value); };
S4B.shifted.fxAssign2 = function(ch, ctl, value, status, group) { S4B.fxAssign(4, group, value); };

// ---------------------------------------------------------------- center
S4B.crossfader = function(ch, ctl, value) { engine.setParameter("[Master]", "crossfader", value / 127); };
S4B.cueMix = function(ch, ctl, value) { engine.setParameter("[Master]", "headMix", value / 127); };
S4B.micVolume = function(ch, ctl, value) { engine.setParameter("[Microphone]", "volume", value / 127); };
S4B.browse = function(ch, ctl, value) { engine.setValue("[Library]", "MoveVertical", S4B.rel(value)); };
S4B.shifted.browse = function(ch, ctl, value) { engine.setValue("[Library]", "MoveFocus", S4B.rel(value) > 0 ? 1 : -1); };
S4B.browsePress = function(ch, ctl, value) { if (value) { engine.setValue("[Library]", "GoToItem", 1); } };
S4B.shifted.browsePress = S4B.browsePress;
// BROWSE button = big library, Traktor-style: while it's open the jog wheels
// scroll the track list (shift + jog pages faster) instead of scratching.
// The big-library control is created by the skin, which can load after this
// script starts, so never cache it: ask Mixxx every time.
S4B.browseAcc = {};
S4B.browseLed = -1;
S4B.isBrowsing = function() { return engine.getValue("[Master]", "maximize_library") > 0; };
S4B.syncBrowse = function() {
    var on = S4B.isBrowsing() ? 1 : 0;
    if (on !== S4B.browseLed) {
        S4B.browseLed = on;
        S4B.browseAcc = {};
        S4B.send("G.browse_btn", "[Master]", on ? 127 : 20);
    }
};
S4B.browseView = function(ch, ctl, value) {
    if (value) {
        S4B.toggle("[Master]", "maximize_library");
        S4B.syncBrowse();
    }
};
S4B.browseJog = function(group, value, rowsPerStep) {
    var stepTicks = Math.max(8, Math.round(S4B.cfg.ticksPerRev / 24));   // ~24 rows per full turn
    S4B.browseAcc[group] = (S4B.browseAcc[group] || 0) + S4B.rel(value);
    var rows = Math.trunc(S4B.browseAcc[group] / stepTicks);
    if (rows !== 0) {
        S4B.browseAcc[group] -= rows * stepTicks;
        engine.setValue("[Library]", "MoveVertical", rows * rowsPerStep);
    }
};
S4B.shifted.browseView = S4B.browseView;
S4B.quant = function(ch, ctl, value) {
    if (!value) { return; }
    var q = !engine.getValue("[Channel1]", "quantize");
    for (var g in DECKS) { engine.setValue(g, "quantize", q); }
};
S4B.shifted.quant = S4B.quant;
S4B.snap = function(ch, ctl, value) {
    if (!value) { return; }
    S4B.snapCue = !S4B.snapCue;
    S4B.send("G.snap", "[Master]", S4B.snapCue ? 127 : 20);
    S4B.send("G.snap_ind", "[Master]", S4B.snapCue ? 127 : 0);
};
S4B.shifted.snap = S4B.snap;
S4B.record = function(ch, ctl, value) { if (value) { engine.setValue("[Recording]", "toggle_recording", 1); } };
S4B.shifted.record = S4B.record;

// ---------------------------------------------------------------- FX units
S4B.fxMix = function(ch, ctl, value, status, group) { engine.setParameter(group, "mix", value / 127); };
[1, 2, 3].forEach(function(n) {
    S4B["fxKnob" + n] = function(ch, ctl, value, status, group) {
        engine.setParameter(group.replace("]", "_Effect" + n + "]"), "meta", value / 127);
    };
    S4B["fxButton" + n] = function(ch, ctl, value, status, group) {
        if (value) { S4B.toggle(group.replace("]", "_Effect" + n + "]"), "enabled"); }
    };
    S4B.shifted["fxButton" + n] = function(ch, ctl, value, status, group) {
        if (value) { engine.setValue(group.replace("]", "_Effect" + n + "]"), "next_effect", 1); }
    };
});
S4B.fxOn = function(ch, ctl, value, status, group) { if (value) { S4B.toggle(group, "enabled"); } };
S4B.shifted.fxOn = S4B.fxOn;
S4B.fxMode = function(ch, ctl, value, status, group) { if (value) { engine.setValue(group, "next_chain_preset", 1); } };
S4B.shifted.fxMode = function(ch, ctl, value, status, group) { if (value) { engine.setValue(group, "prev_chain_preset", 1); } };

// ---------------------------------------------------------------- deck display modes
// SHIFT + push SIZE cycles: LOOP size -> TIME left (seconds; minutes with a dot
// past 99 s) -> CAmelot key (number, dot = B/major).
S4B.DISPLAYS = ["loop", "time", "key"];
S4B.DISPLAY_WORD = {loop: 102, time: 103, key: 104};
S4B.dispMode = {};
S4B.flashing = {};
S4B.CAMELOT = [0, 8, 3, 10, 5, 12, 7, 2, 9, 4, 11, 6, 1, 5, 12, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10];

S4B.flashWord = function(group, word) {
    if (S4B.flashing[group]) { engine.stopTimer(S4B.flashing[group]); }
    S4B.send("deck.display_dot", group, 0);
    S4B.send("deck.display", group, word);
    S4B.flashing[group] = engine.beginTimer(900, function() {
        S4B.flashing[group] = 0;
        S4B.renderDisplay(group, true);
    }, true);
};

S4B.cycleDisplay = function(group) {
    var i = S4B.DISPLAYS.indexOf(S4B.dispMode[group] || "loop");
    S4B.dispMode[group] = S4B.DISPLAYS[(i + 1) % S4B.DISPLAYS.length];
    S4B.flashWord(group, S4B.DISPLAY_WORD[S4B.dispMode[group]]);
};

S4B.lastDisplay = {};
S4B.renderDisplay = function(group, force) {
    if (S4B.flashing[group]) { return; }
    var mode = S4B.dispMode[group] || "loop", v = 100, dot = 0;
    if (!engine.getValue(group, "track_loaded")) {
        v = 100;
    } else if (mode === "loop") {
        var size = engine.getValue(group, "beatloop_size");
        v = size >= 1 && size <= 99 ? Math.round(size) : 101;
    } else if (mode === "time") {
        var left = engine.getValue(group, "duration") * (1 - engine.getValue(group, "playposition"));
        if (left >= 99.5) { v = Math.min(99, Math.floor(left / 60)); dot = 1; } else { v = Math.max(0, Math.round(left)); }
    } else {
        var k = Math.round(engine.getValue(group, "key"));
        if (k >= 1 && k <= 24) { v = S4B.CAMELOT[k]; dot = k <= 12 ? 1 : 0; } else { v = 101; }
    }
    var key = v + "/" + dot;
    if (!force && S4B.lastDisplay[group] === key) { return; }
    S4B.lastDisplay[group] = key;
    S4B.send("deck.display_dot", group, dot ? 127 : 0);
    S4B.send("deck.display", group, v);
};

// ---------------------------------------------------------------- PLAY light: beat pulse + end-of-track flash
S4B.eot = {};
S4B.blink = false;
S4B.playLed = function(group) {
    var playing = engine.getValue(group, "play_indicator");
    var v = 0;
    if (playing && S4B.eot[group]) {
        v = S4B.blink ? 127 : 0;                       // last seconds of the track: flash
    } else if (playing) {
        v = engine.getValue(group, "beat_active") ? 127 : 45;   // pulse on the beat
    }
    S4B.send("deck.play", group, v);
    S4B.send("deck.on_air", group, playing ? (S4B.eot[group] && !S4B.blink ? 0 : 127) : 0);
};

// hot cue colour -> the S4's two LED colours (blue, green, or both for warm colours)
S4B.cueVel = function(rgb) {
    var r = (rgb >> 16) & 255, g = (rgb >> 8) & 255, b = rgb & 255;
    if (g > r && g >= b) { return 70; }               // greens
    if (b > r && b > g) { return 20; }                // blues / purples
    return 110;                                       // reds, oranges, yellows, white: both
};

// ---------------------------------------------------------------- LED feedback
S4B.connect = function(group, key, fn) {
    var c = engine.makeConnection(group, key, fn);
    if (c) { c.trigger(); S4B.connections.push(c); }
};

S4B.samplerLeds = function(i) {
    // a sampler changed: redraw the pads of that side (if they're showing samples)
    S4B.sideGroups(i <= 4 ? "L" : "R").forEach(function(g) {
        if (S4B.padMode[S4B.sideOf(g)] === "samples") { S4B.padLeds(g); }
    });
};

S4B.init = function() {
    // make sure 8 samplers exist (Mixxx 2.4+: [App]; older: [Master])
    if (engine.getValue("[App]", "num_samplers") < 8) { engine.setValue("[App]", "num_samplers", 8); }
    for (var i = 1; i <= 8; i++) {
        (function(i) {
            S4B.connect("[Sampler" + i + "]", "play_indicator", function() { S4B.samplerLeds(i); });
            S4B.connect("[Sampler" + i + "]", "track_loaded", function() { S4B.samplerLeds(i); });
        })(i);
    }
    for (var group in DECKS) {
        (function(group) {
            var n = NUM[group];
            engine.softTakeover(group, "rate", true);
            S4B.connect(group, "rate", function(v) {                 // for S4 Bridge's soft takeover
                S4B.send("deck.rate_fb", group, Math.max(0, Math.min(127, Math.round((v + 1) / 2 * 127))));
            });
            S4B.connect(group, "play_indicator", function() { S4B.playLed(group); });
            S4B.connect(group, "beat_active", function() { S4B.playLed(group); });
            S4B.connect(group, "end_of_track", function(v) { S4B.eot[group] = v > 0; S4B.playLed(group); });
            S4B.connect(group, "slip_enabled", function(v) { S4B.send("deck.tempo_down", group, v ? 127 : 0); });
            ["beatloop_size", "key", "track_loaded", "duration"].forEach(function(k) {
                S4B.connect(group, k, function() { S4B.renderDisplay(group); });
            });
            S4B.connect(group, "playposition", function() {
                if ((S4B.dispMode[group] || "loop") === "time") { S4B.renderDisplay(group); }
            });
            S4B.connect(group, "stem_count", function() { S4B.padLeds(group); });
            for (var st = 1; st <= 4; st++) {
                S4B.connect(S4B.stemGroup(group, st), "mute", function() { S4B.padLeds(group); });
            }
            S4B.connect(group, "cue_indicator", function(v) { S4B.send("deck.cue", group, v ? 127 : 0); });
            S4B.connect(group, "sync_enabled", function(v) { S4B.send("deck.sync", group, v ? 127 : 0); });
            S4B.connect(group, "sync_leader", function(v) { S4B.send("deck.master_ind", group, v ? 127 : 0); });
            S4B.connect(group, "keylock", function(v) { S4B.send("deck.keylock", group, v ? 127 : 0); });
            S4B.connect(group, "loop_enabled", function(v) {
                S4B.send("deck.loop_in", group, v ? 127 : 20);
                S4B.send("deck.loop_out", group, v ? 127 : 20);
            });
            S4B.connect(group, "track_loaded", function(v) {
                S4B.send("deck.load", group, v ? 40 : 0);
                S4B.send("strip.active", group, v ? 127 : 0);
            });
            [1, 2, 3, 4].forEach(function(h) {
                var update = function() {
                    var status = engine.getValue(group, "hotcue_" + h + "_status");
                    S4B.send("deck.hotcue" + h, group, status ? S4B.cueVel(engine.getValue(group, "hotcue_" + h + "_color")) : 0);
                };
                S4B.connect(group, "hotcue_" + h + "_status", update);
                S4B.connect(group, "hotcue_" + h + "_color", update);
            });
            S4B.connect(group, "pfl", function(v) { S4B.send("strip.cue", group, v ? 127 : 0); });
            S4B.connect(group, "orientation", function(v) {
                S4B.send("strip.xf_left", group, v === 0 ? 127 : 0);
                S4B.send("strip.xf_right", group, v === 2 ? 127 : 0);
            });
            S4B.connect(group, "vu_meter", function(v) {
                S4B.send("strip.meter", group, Math.min(126, Math.round(v * 126)));
            });
            S4B.connect(group, "peak_indicator", function(v) { if (v) { S4B.send("strip.meter", group, 127); } });
            [1, 2].forEach(function(u) {
                S4B.connect("[EffectRack1_EffectUnit" + u + "]", "group_" + group + "_enable", function(v) {
                    S4B.send("strip.fx" + u, group, v ? 127 : 0);
                });
            });
            S4B.connect(group, "quantize", function(v) {
                if (n === 1) { S4B.send("G.quant", "[Master]", v ? 127 : 0); S4B.send("G.quant_ind", "[Master]", v ? 127 : 0); }
            });
        })(group);
    }
    [1, 2].forEach(function(u) {
        var unit = "[EffectRack1_EffectUnit" + u + "]";
        S4B.connect(unit, "enabled", function(v) { S4B.send("FX" + u + ".on", unit, v ? 127 : 0); });
        [1, 2, 3].forEach(function(e) {
            S4B.connect(unit.replace("]", "_Effect" + e + "]"), "enabled", function(v) {
                S4B.send("FX" + u + ".b" + e, unit, v ? 127 : 0);
            });
        });
        S4B.send("FX" + u + ".mode", unit, 20);
    });
    S4B.connect("[Recording]", "status", function(v) { S4B.send("G.loop_rec", "[Master]", v ? 127 : 0); });
    S4B.send("G.snap", "[Master]", 20);
    S4B.send("G.snap_ind", "[Master]", 0);
    S4B.syncBrowse();
    S4B.browseTimer = engine.beginTimer(200, S4B.syncBrowse);   // also catches mouse/keyboard toggles
    S4B.blinkTimer = engine.beginTimer(250, function() {
        S4B.blink = !S4B.blink;
        for (var g in DECKS) {
            if (S4B.eot[g]) { S4B.playLed(g); }
            if (S4B.padMode[S4B.sideOf(g)] === "rolls") { S4B.samplesLamp(g); }
        }
    });
    for (var g2 in DECKS) { S4B.padLeds(g2); S4B.renderDisplay(g2, true); }
};

S4B.shutdown = function() {
    if (S4B.browseTimer) { engine.stopTimer(S4B.browseTimer); }
    if (S4B.blinkTimer) { engine.stopTimer(S4B.blinkTimer); }
    S4B.connections.forEach(function(c) { c.disconnect(); });
};
