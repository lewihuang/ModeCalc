# ModeCalc

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![tests](https://github.com/lewihuang/ModeCalc/actions/workflows/tests.yml/badge.svg)](https://github.com/lewihuang/ModeCalc/actions/workflows/tests.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Platform: Windows / macOS](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey.svg)](#requirements)

[简体中文](README.md) | English

ModeCalc is a cross-platform desktop tool for real-time MIDI chord and mode detection. Connect a MIDI keyboard and it shows the current chord, matching modes, standard notation, an 88-key piano and a guitar fretboard — useful for practice, transcription and harmony analysis.

![ModeCalc UI](docs/images/modecalc.png)

- [Download](#download)
- [Features](#features)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Build](#build)
- [Test](#test)
- [Project layout](#project-layout)
- [License](#license)

## Download

Get the latest Windows build from [Releases](https://github.com/lewihuang/ModeCalc/releases):

- `ModeCalc-v1.0.1-win64.zip` — portable, unzip and run `ModeCalc.exe`;
- single-file exe, no Python installation required.

> The exe is not code-signed, so Windows SmartScreen may warn about an unrecognized app. Choose "More info → Run anyway", or verify the SHA256 published in the release.

macOS builds produce a standalone `ModeCalc.app`, available as Universal 2 (Intel and Apple Silicon) or Apple Silicon only. A public Mac release has not yet been published; follow the build instructions below. Extract the generated ZIP and drag the app to Applications; users do not need Python installed.

## Features

- **Two lenses**: switch between `Chord` and `Mode` analysis for the same notes.
- **Chord detection**: ~60 templates covering triads, seventh, ninth/eleventh/thirteenth, add and altered chords, with inversions and incomplete-match hints.
- **Mode detection**: 71 independent scales grouped into Natural Mode, Harmonic Major, Harmonic Minor, Melodic Minor, Jazz, Modes of limited transposition and World Music; shows tonic, rotation and missing-note count.
- **Editable scale library**: every scale is an independent row grouped into collapsible categories; enable/disable any row. Default rows are read-only (renaming/editing creates a Custom copy); custom rows can be edited and deleted. The Info column shows absolute equivalents (e.g. C Ionian ≡ A Aeolian) and aliases; cross-category duplicates are kept as alias rows, disabled by default.
- **Messiaen modes of limited transposition**: named by their minimal repeating interval cell (e.g. `Messiaen 211`, `Messiaen 1131`).
- **Pinned mode**: click any match to pin it; notes outside the pinned scale are highlighted in red `#FF5768` on the keyboard.
- **Derived modes**: while a mode is pinned, pressing multiple notes including out-of-scale notes lists modes anchored on the pinned tonic that contain all pressed notes; click one to re-pin.
- **Visualisation**: standard notation (VexFlow), 88-key piano (SVG), guitar fretboard.
- **Key signatures**: 15 keys, affecting enharmonic spelling and staff notation.
- **MIDI**: device selection (including "All inputs") and sustain pedal support.
- **Remembered scale library**: enabled states, custom scales and edited copies are saved locally and restored on startup.

## Requirements

- **Windows 10 / 11** with the WebView2 Runtime (included in Windows 11)
- **macOS** with the system WKWebView; tested on Apple Silicon / macOS 26.4.1. macOS 14 is the build target; Intel hardware and the minimum OS version still require validation.
- **Python 3.12** (only for running from source / building)
- A MIDI input device (optional; the UI still opens without one)

## Quick start

```powershell
git clone https://github.com/lewihuang/ModeCalc.git
cd ModeCalc

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
python app.py
```

Choose your device from the `MIDI Input` menu, then switch between `Chord` and `Mode` on the right.

## Build

Windows uses PyInstaller; macOS uses py2app. Both share the same application code.

```powershell
pip install -r requirements.txt
build.bat
```

The output is `dist\ModeCalc.exe` (single file, `static` assets bundled). The build uses PyInstaller; shared version metadata lives in `app_version.py` and generates `version_info.txt` during a Windows build.

macOS builds require a Python 3.12 framework build and Xcode Command Line Tools. To build the Apple Silicon version on an M-series Mac:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
bash scripts/build_macos.sh
```

For Universal 2, use a Python 3.12 framework containing both arm64 and x86_64 (such as the python.org Universal 2 installer):

```bash
MODECALC_PYTHON=/path/to/universal2/python3.12 bash scripts/build_macos_universal.sh
```

Replace the example path with your interpreter path. The script uses a separate virtual environment, merges the two RtMidi extension architectures and verifies all native dependencies.

| Version | Supported chips | Application path | ZIP filename |
| --- | --- | --- | --- |
| Universal 2 | Intel and Apple Silicon | `dist/macos-universal2/ModeCalc.app` | `ModeCalc-v<version>-macos-universal2.zip` |
| Apple Silicon only | M-series | `dist/macos-arm64/ModeCalc.app` | `ModeCalc-v<version>-macos-arm64.zip` |

ZIP archives and matching SHA256 files are written to `dist/`. Universal 2 runs natively on both architectures; the Apple Silicon package has the same features with a smaller download. On Intel, `build_macos.sh` can also produce a `macos-x86_64` package. Local builds use ad-hoc signing. Both Universal 2 slices have passed MIDI/UI smoke tests on Apple Silicon (x86_64 through Rosetta); macOS 14 and Intel hardware still require validation. See [macOS build and distribution](docs/MACOS_BUILD.md) for standalone verification, Developer ID signing and notarization.

## Test

```powershell
pytest -q
```

CI is configured to run the suite on Windows, macOS arm64 and Intel runners for every push and pull request, and to build and smoke-test Mac apps (see `.github/workflows/tests.yml`).

## Project layout

```
app.py               pywebview desktop entry and frontend bridge
desktop_runtime.py   MIDI worker lifecycle and state publishing
runtime_paths.py     bundled resources, settings and log paths
app_version.py       shared version metadata for both platforms
server.py            aiohttp + WebSocket browser debugging entry
chord_engine.py      chord recognition (templates / inversions / incomplete matches)
mode_engine.py       scale registry and mode detection (parents, rotations, sub_scales)
midi_handler.py      MIDI input (callback + queue, sustain pedal logic)
settings_store.py    user settings persistence
scale_library.py     editable scale library (defaults, overrides, custom scales)
static/              frontend: HTML / CSS / JS, VexFlow, fonts, fretboard library
tests/               pytest unit tests
docs/                design docs, ADRs and changelog
.github/             CI, issue and PR templates
version_info.txt     Windows executable version metadata
build.bat            PyInstaller build script
packaging/macos/     py2app configuration and signing entitlements
scripts/             Mac builds, architecture checks, signing, notarization and smoke tests
```

## Usage tips

- **Pinning a mode**: click any result in `Matches` to pin/unpin it; the keyboard highlights the scale.
- **Red notes**: when a mode is pinned, pressed notes outside the scale turn red; this is only a hint and does not affect chord recognition.
- **Derived modes**: red notes trigger candidate modes prefixed with `↳` and a red left border; click one to switch the pinned mode.
- **Local settings**: saved in `%APPDATA%\ModeCalc\settings.json` on Windows and `~/Library/Application Support/ModeCalc/settings.json` on Mac; delete the file to reset.
- **Scale settings**: open Settings from the right panel; scales are grouped into collapsible categories. Rename, edit notes on a one-octave keyboard, enable/disable, add/delete scales or restore defaults; group headers support tri-state select-all. Editing a default scale creates a custom copy and keeps the original (disabled); only the 7 Natural Mode modes are enabled by default.
- **Browser debugging**: run `python server.py` and open `http://localhost:8765`.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) (in Chinese) for the development and testing conventions.

## License

Licensed under the [MIT License](LICENSE).

Third-party components (VexFlow, traste, Bravura / Academico, Quicksand, etc.) are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); the full OFL text is in [LICENSES/OFL-1.1.txt](LICENSES/OFL-1.1.txt).
