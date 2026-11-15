# Changelog

All notable changes to S4 Bridge. Versions follow [Semantic Versioning](https://semver.org/).

## 0.6.0
### Added
- **Built-in USB driver (beta).** S4 Bridge can now talk to the S4 directly over USB instead of going
  through the Linux kernel driver. This is the groundwork for the Mac and Windows versions: no NI driver
  and no MIDI-mode workaround, with full-resolution jogs and every LED.
  - On Linux, pick it under **Settings › Device › Connection**. Switching is live; switching back
    hands the S4 back to the kernel.
  - Controls and LEDs only for now: the S4's own sound card isn't available while this driver has it.
  - Its decoder matches the kernel driver exactly (checked against the kernel's own code on 15,000
    random reports).
### Changed
- The udev rule also covers the S4's raw USB device. Older installs get the **Fix it** prompt once.
- New dependency: pyusb (python-pyusb / python3-pyusb / python3-usb).

## 0.5.8
### Changed
- Home is now **github.com/fancy-butler/s4bridge**. The app ID is `io.github.fancy_butler.s4bridge`
  (app IDs can't contain hyphens, so the hyphen becomes an underscore).
- README: clone step, laptop-size screenshots including the mixer, and an honest list of what's
  confirmed on hardware and what isn't.
### Fixed
- The Deck A / Deck B buttons on the Surface page were clipped on narrower windows.

## 0.5.7
### Changed
- The status bar no longer says "Ready" all the time. It stays blank until there's something to report
  (saved, copied, fixed), and that message fades after a few seconds.

## 0.5.6
### Changed
- When the window is narrow enough that the sidebar folds, the version (and any "New version" link)
  shows in the bottom-right corner of the status bar instead of disappearing.

## 0.5.5
### Added
- **Fix it, no terminal.** If S4 Bridge isn't allowed to read the S4's controls, a bar across the top of
  the window says so with a **Fix it** button. It asks for your password once (polkit), installs the
  udev rule, and the S4 connects a couple of seconds later. Health has the same button.
- **Copy report** on the Health page: versions, distro, kernel, audio server, Mixxx and every health
  result as a ready-to-paste GitHub issue block. Your home folder path is scrubbed out.
- **Update notice.** Once a day S4 Bridge asks GitHub for the latest release number; if there's a newer
  one, a small "New version" link appears in the sidebar. Nothing about you is sent. Off switch in
  Settings › App.

## 0.5.4
### Changed
- **Fits ordinary screens.** The window now goes down to 900 × 600 and opens at a size that fits your
  display (it used to need about 1650 px of width).
  - Under 1200 px wide the sidebar folds into an icon rail; hover an icon for its name.
  - Surface: the side panel tucks away when space is tight, leaving the S4 drawing.
  - Mapping: Save / Save as / Import / Export live in a **Profile** menu; MIDI channels and shift offset
    sit behind a **Channels** button; on narrow windows Identify moves under the table.
  - Mixer: channel cards go 2 × 2 when narrow. Settings: one column when narrow, shorter labels with
    the detail in tooltips.
  - Every page scrolls instead of forcing the window wider.
- The window remembers its size and position.
### Tests
- A layout test fails the build if any page needs sideways scrolling at 900 × 600, 1280 × 720,
  1366 × 768 or 1920 × 1080.

## 0.5.3
### Added
- **Playing now** on the Mixer page: every app making sound, each with a Deck A / Deck B / Not in the
  mixer dropdown. No pavucontrol needed.
### Changed
- Mixer source names: the S4's rear inputs show as "S4 rear input C/D".

## 0.5.2
### Fixed
- The virtual sound outputs were named "S4" and "S4-216" instead of "S4 Deck A" / "S4 Deck B"
  (argument quoting), so they weren't connected to channels A/B automatically.
- The S4's own Main/Headphones outputs are no longer offered as mixer sources (feedback loop).
### Changed
- The mixer's components (numpy, scipy, python-jack-client, pipewire-jack) are regular dependencies,
  so updating installs them automatically.

## 0.5.1
### Fixed
- Package build: the mixer's optional dependencies section in pyproject.toml swallowed the
  classifiers, which made makepkg fail. The test suite now builds the real package every run.

## 0.5.0
### Added
- **Standalone mixer mode**: the S4 as a four-channel mixer with no DJ software. Channels C/D play the
  rear inputs; channels A/B are new "S4 Deck A/B" sound outputs any app can play into. Gain, 3-band
  EQ with kill, DJ filter, faders, crossfader, headphone cue and cue mix, VU meters on the S4's LEDs,
  soft limiter with a warning lamp. Separate audio process (PipeWire via JACK) so the UI can't cause
  dropouts. Mixer page, tray toggle and health check line.

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
