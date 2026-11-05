# Changelog

All notable changes to S4 Bridge. Versions follow [Semantic Versioning](https://semver.org/).

## 0.4.1
### Added
- Shipping groundwork: git history, this changelog, AppStream metainfo (software centres), app icons
  at all sizes, README screenshots, AUR / Fedora / Debian packaging, GitHub CI and a release script.

## 0.4.0
### Added
- **Pad modes** for the ▶ row (SHIFT + push MOVE): Samples, Stems (Mixxx 2.6+: mute, per-stem
  volume on MOVE, per-stem quick effect) and Loop Rolls (1/8, 1/4, 1/2, 1 beat). The SAMPLES lamp
  shows the mode.
- **FLUX** (slip mode) on SHIFT + OFFSET ▼.
- **Mixer FX**: SHIFT + channel CUE steps the FILTER knob's quick effect.
- PLAY pulses on the beat and flashes with ON AIR near the end of a track.
- Hot cues show their Mixxx colour (green / blue / both).
- **Display modes** (SHIFT + push SIZE): loop size, time left, Camelot key. Decimal-point support
  and short words on the deck displays.

## 0.3.3
### Fixed
- PLAY, CUE, hot cues and LOAD always release a lingering stopped-deck jog grab first, so a deck
  can never be left frozen.
- CUE uses Mixxx's mode-independent CDJ cue, so it works whatever Mixxx's Cue mode setting is.
### Added
- The Mixxx mapping is tested against a simulated Mixxx engine on every build.

## 0.3.2
### Changed
- Sidebar badge centred with a deliberate line break; MIDI lights centred.

## 0.3.1
### Added
- Version shown next to the app name; live deck tiles (click to flip), MIDI IN/OUT lights and a
  badge in the sidebar.

## 0.3.0
### Added
- Soft takeover on the tempo faders after a deck flip, with OFFSET ▲/▼ pointing the way and a ghost
  marker on the surface. Works in any app that reports the tempo back (CC 0x51).
- LED brightness slider and optional idle light show.

## 0.2.1
### Changed
- Tray notifications only when something is wrong.
- The Mixxx mapping keeps itself up to date (only when Mixxx is closed; never touches sound settings).

## 0.2.0
### Added
- System tray icon, start at login, single instance.
- Health check page covering kernel driver, permissions, controls, MIDI, LEDs, the S4's PipeWire
  outputs and Mixxx.

## 0.1.7
### Added
- One-click **Set up Mixxx**: installs the mapping, enables the controller and routes Mixxx's Main
  and Headphones to the S4 (`s4bridge --setup-mixxx` from a terminal).

## 0.1.6
### Changed
- Loops (IN/OUT and auto loop) start exactly at the cursor unless SNAP is lit.
- Jog defaults to 1000 ticks per turn (measured on a real S4 MK1).

## 0.1.5
### Changed
- CUE writes the exact sample position; SNAP toggles beat-snapping like Traktor.
- Jog calibration lives in S4 Bridge and applies live.

## 0.1.4
### Changed
- Traktor-style CUE; jog moves the track like a platter when stopped; stronger nudge while playing.

## 0.1.3
### Fixed
- Jog wheels scroll the big library reliably.

## 0.1.2
### Fixed
- The ▶ row plays Mixxx samplers (4 per side) instead of hot cues 5–8.

## 0.1.1
### Fixed
- BROWSE opens Mixxx's big library; jogs scroll it.

## 0.1.0
- First release: snd-usb-caiaq bridge, virtual MIDI port, LED feedback, live surface, mapping
  editor with Identify, MIDI monitor, settings, Mixxx mapping export, demo and headless modes.
