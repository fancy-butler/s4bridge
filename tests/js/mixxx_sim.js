// Minimal Mixxx engine simulation for the S4 Bridge mapping.
// Usage: node mixxx_sim.js <mapping.xml> <script.js>
// Exits non-zero (with a message) on the first failed check.
const fs = require("fs");
const [xmlPath, jsPath] = process.argv.slice(2);

function makeEngine() {
    const vals = {}, conns = {}, timers = {}, sent = [];
    const scratching = {};
    let timerId = 0;
    const fire = (g, k) => (conns[g + k] || []).forEach(f => f(vals[g + k] ?? 0, g, k));
    const engine = {
        vals, sent, timers, scratching,
        getValue: (g, k) => vals[g + k] ?? 0,
        setValue: (g, k, v) => { vals[g + k] = +v; engine.hook(g, k, +v); fire(g, k); },
        getParameter: (g, k) => vals[g + k] ?? 0.5,
        setParameter: (g, k, v) => { vals[g + k] = v; },
        makeConnection: (g, k, fn) => {
            (conns[g + k] = conns[g + k] || []).push(fn);
            return { trigger: () => fn(vals[g + k] ?? 0, g, k), disconnect() {} };
        },
        softTakeover() {},
        beginTimer: (ms, fn, once) => { timers[++timerId] = { fn, once: !!once }; return timerId; },
        stopTimer: id => { delete timers[id]; },
        runTimers() {
            Object.entries(timers).forEach(([id, t]) => { if (t.once) delete timers[id]; t.fn(); });
        },
        scratchEnable: d => { scratching[d] = true; },
        scratchDisable: d => { scratching[d] = false; },
        isScratching: d => !!scratching[d],
        scratchTick() {},
        hook() {},
    };
    return engine;
}

function load() {
    const engine = makeEngine();
    global.engine = engine;
    global.midi = { sendShortMsg: (a, b, c) => engine.sent.push([a, b, c]) };
    global.script = { absoluteLin: (v, lo, hi, mn, mx) => lo + (v - mn) / (mx - mn) * (hi - lo) };
    const S4B = new Function(fs.readFileSync(jsPath, "utf8") + "\nreturn S4B;")();
    S4B.init();
    return { engine, S4B };
}

let failures = 0;
function check(name, cond, extra) {
    if (!cond) { console.error("FAIL: " + name + (extra ? " -> " + extra : "")); failures++; }
    else { console.log("ok   " + name); }
}

// 1. every XML binding resolves to a callable function and survives being called
{
    const { S4B } = load();
    const xml = fs.readFileSync(xmlPath, "utf8");
    const re = /<group>(.*?)<\/group>\s*<key>(.*?)<\/key>\s*<status>(.*?)<\/status>\s*<midino>(.*?)<\/midino>/g;
    let m, n = 0, bad = [];
    while ((m = re.exec(xml))) {
        const [, group, key, st, no] = m;
        const fn = key.split(".").slice(1).reduce((o, p) => o && o[p], S4B);
        if (typeof fn !== "function") { bad.push(key); continue; }
        try { fn(+st & 15, +no, 127, +st, group); fn(+st & 15, +no, 0, +st, group); n++; }
        catch (e) { bad.push(key + " threw " + e); }
    }
    check(`all ${n} bindings callable`, bad.length === 0, bad.join(", "));
}

// 2. CUE: exact placement, mode-independent cue_cdj
{
    const { engine, S4B } = load();
    const G = "[Channel1]";
    Object.assign(engine.vals, { [G + "track_samples"]: 1e7, [G + "playposition"]: 0.4567891, [G + "quantize"]: 1 });
    S4B.cue(0, 9, 127, 0x90, G);
    check("cue lands on exact sample", engine.vals[G + "cue_point"] === 4567890, engine.vals[G + "cue_point"]);
    check("cue uses cue_cdj", engine.vals[G + "cue_cdj"] === 1);
}

// 3. platter grab can never freeze PLAY
{
    const { engine, S4B } = load();
    const G = "[Channel1]";
    S4B.jog(0, 2, 64 + 5, 0xB0, G);                    // stopped deck: grabs like a platter
    check("stopped jog grabs the platter", engine.isScratching(1));
    S4B.play(0, 0x0A, 127, 0x90, G);                   // timer never fired, user hits PLAY
    check("PLAY releases a stuck platter grab", !engine.isScratching(1));
    check("PLAY then starts the deck", engine.vals[G + "play"] === 1);
    S4B.touch(0, 3, 127, 0x90, G);                     // hand on platter while playing
    S4B.play(0, 0x0A, 127, 0x90, G);
    check("PLAY does not cancel a real (touched) scratch", engine.isScratching(1));
}

// 4. browse view: jogs scroll the library and never scratch
{
    const { engine, S4B } = load();
    let moved = 0;
    engine.hook = (g, k, v) => { if (k === "MoveVertical") moved += v; };
    engine.vals["[Master]maximize_library"] = 1;
    for (let i = 0; i < 10; i++) S4B.jog(1, 2, 64 + 43, 0xB1, "[Channel2]");
    S4B.touch(1, 3, 127, 0x91, "[Channel2]");
    check("browse jog scrolls 10 rows", moved === 10, moved);
    check("browse touch does not scratch", !engine.isScratching(2));
}

// 5. sample slots: load when empty, play when loaded, LEDs on both decks of the side
{
    const { engine, S4B } = load();
    engine.hook = (g, k) => {
        if (k === "LoadSelectedTrack") engine.setValue(g, "track_loaded", 1);
        if (k === "cue_gotoandplay") engine.setValue(g, "play_indicator", 1);
    };
    engine.sent.length = 0;
    S4B.sample2(2, 0x10, 127, 0x92, "[Channel3]");
    S4B.sample2(2, 0x10, 127, 0x92, "[Channel3]");
    check("left sample 2 = sampler 2 loaded", engine.vals["[Sampler2]track_loaded"] === 1);
    const lit = engine.sent.filter(m => m[1] === 0x10 && m[2] === 127).map(m => m[0]);
    check("sample LED lit on decks A and C", lit.includes(0x90) && lit.includes(0x92), JSON.stringify(lit));
}

// 6. exact loops and 4-beat auto loop
{
    const { engine, S4B } = load();
    const G = "[Channel1]";
    Object.assign(engine.vals, { [G + "track_samples"]: 1e7, [G + "loop_start_position"]: -1,
        [G + "loop_end_position"]: -1, [G + "file_bpm"]: 120, [G + "track_samplerate"]: 44100, [G + "beatloop_size"]: 4 });
    engine.hook = (g, k) => { if (k === "reloop_toggle") engine.vals[g + "loop_enabled"] = engine.vals[g + "loop_enabled"] ? 0 : 1; };
    engine.vals[G + "playposition"] = 0.1000003; S4B.loopIn(0, 0x17, 127, 0x90, G);
    engine.vals[G + "playposition"] = 0.1500007; S4B.loopOut(0, 0x18, 127, 0x90, G);
    check("loop in exact", engine.vals[G + "loop_start_position"] === 1000002);
    check("loop out exact and enabled", engine.vals[G + "loop_end_position"] === 1500006 && engine.vals[G + "loop_enabled"] === 1);
    engine.vals[G + "playposition"] = 0.3; S4B.beatloop(0, 0x15, 127, 0x90, G);
    check("auto loop is 4 beats", engine.vals[G + "loop_end_position"] - engine.vals[G + "loop_start_position"] === 176400);
}

// 7. tempo position is reported back for soft takeover
{
    const { engine } = load();
    engine.sent.length = 0;
    engine.setValue("[Channel3]", "rate", 0.5);
    check("rate feedback on deck C channel", engine.sent.some(m => m[0] === 0xB2 && m[1] === 0x51 && m[2] === 95),
          JSON.stringify(engine.sent));
}

// 8. pad modes: samples -> stems -> rolls on SHIFT + MOVE push, per side
{
    const { engine, S4B } = load();
    const G = "[Channel1]";
    engine.vals[G + "stem_count"] = 4;
    S4B.shifted.reloop(0, 0x33, 127, 0x90, G);
    check("pad mode -> stems", S4B.padMode.L === "stems" && S4B.padMode.R === "samples");
    S4B.sample2(0, 0x10, 127, 0x90, G); S4B.sample2(0, 0x10, 0, 0x80, G);
    check("stem pad tap mutes bass", engine.vals["[Channel1_Stem2]mute"] === 1);
    S4B.sample3(0, 0x11, 127, 0x90, G);
    S4B.loopMove(0, 0x13, 64 + 3, 0xB0, G);
    S4B.sample3(0, 0x11, 0, 0x80, G);
    check("hold stem + MOVE = volume, no mute", engine.vals["[Channel1_Stem3]volume"] > 0.5 && !engine.vals["[Channel1_Stem3]mute"],
          engine.vals["[Channel1_Stem3]volume"]);
    S4B.shifted.sample1(0, 0x2F, 127, 0x90, G);
    check("SHIFT + stem pad = stem quick effect", engine.vals["[QuickEffectRack1_[Channel1_Stem1]]enabled"] === 1);
    S4B.shifted.reloop(0, 0x33, 127, 0x90, G);
    check("pad mode -> rolls", S4B.padMode.L === "rolls");
    S4B.sample2(0, 0x10, 127, 0x90, G);
    check("roll pad 2 = 1/4 beat roll held", engine.vals[G + "beatlooproll_0.25_activate"] === 1);
    S4B.sample2(0, 0x10, 0, 0x80, G);
    check("roll released", engine.vals[G + "beatlooproll_0.25_activate"] === 0);
}

// 9. FLUX and Mixer FX
{
    const { engine, S4B } = load();
    S4B.shifted.nudgeDown(0, 0x25, 127, 0x90, "[Channel2]");
    check("SHIFT + OFFSET down = slip (FLUX)", engine.vals["[Channel2]slip_enabled"] === 1);
    S4B.shifted.pfl(0, 0x64, 127, 0x90, "[Channel3]");
    check("SHIFT + channel CUE = next mixer FX", engine.vals["[QuickEffectRack1_[Channel3]]next_chain_preset"] === 1);
}

// 10. PLAY pulses on the beat and flashes near the end of the track
{
    const { engine, S4B } = load();
    const G = "[Channel1]";
    const playLed = () => engine.sent.filter(m => m[0] === 0x90 && m[1] === 0x0A).map(m => m[2]).pop();
    engine.setValue(G, "play_indicator", 1);
    engine.setValue(G, "beat_active", 1); const onBeat = playLed();
    engine.setValue(G, "beat_active", 0); const offBeat = playLed();
    check("PLAY pulses with the beat", onBeat === 127 && offBeat === 45, onBeat + "/" + offBeat);
    engine.setValue(G, "end_of_track", 1);
    const seen = new Set(); for (let i = 0; i < 4; i++) { engine.runTimers(); seen.add(playLed()); }
    check("PLAY flashes at end of track", seen.has(0) && seen.has(127), [...seen].join(","));
}

// 11. hot cue colours
{
    const { engine } = load();
    const G = "[Channel2]";
    const vel = () => engine.sent.filter(m => m[0] === 0x91 && m[1] === 0x0B).map(m => m[2]).pop();
    engine.setValue(G, "hotcue_1_color", 0x00ff00); engine.setValue(G, "hotcue_1_status", 1);
    const green = vel();
    engine.setValue(G, "hotcue_1_color", 0x0044ff); const blue = vel();
    engine.setValue(G, "hotcue_1_color", 0xff8800); const warm = vel();
    check("hot cue colours map to green / blue / both", green === 70 && blue === 20 && warm === 110, [green, blue, warm]);
}

// 12. display modes: loop -> time -> Camelot key
{
    const { engine, S4B } = load();
    const G = "[Channel1]";
    Object.assign(engine.vals, { [G + "track_loaded"]: 1, [G + "duration"]: 300, [G + "playposition"]: 0.5, [G + "key"]: 22 });
    const disp = () => { const d = engine.sent.filter(m => m[0] === 0xB0 && m[1] === 0x50).map(m => m[2]).pop();
                         const dot = engine.sent.filter(m => m[0] === 0xB0 && m[1] === 0x54).map(m => m[2]).pop();
                         return d + (dot ? "." : ""); };
    S4B.shifted.beatloop(0, 0x35, 127, 0x90, G);
    check("SHIFT + SIZE push flashes 'tL'", disp() === "103");
    engine.runTimers();
    check("time left: 150 s -> '2.' minutes", disp() === "2.", disp());
    S4B.shifted.beatloop(0, 0x35, 127, 0x90, G); engine.runTimers();
    check("A minor -> Camelot 8A", disp() === "8", disp());
    engine.setValue(G, "key", 1);
    check("C major -> Camelot 8B (dot)", disp() === "8.", disp());
}

process.exit(failures ? 1 : 0);
