# DF-Recoil v2.0 (C++ Native Rebuild)

A high-performance, standalone Win32/C++ recoil compensator and weapon profile manager for **Delta Force**.

Re-engineered from the ground up as a native C++ executable without Python or OpenCV runtime dependencies. Features an **Apple macOS Dark Mode inspired interface**, responsive monitor adaptation, Bézier-interpolated mouse movement, and machine vision dot calibration.

---

## What's New in v2.0 (Apple macOS Dark Mode & Compact Layout)

- **Apple macOS Dark Mode Aesthetic**:
  - Sleek dark graphite surfaces (`#1C1C1E`) with elevated secondary card containers (`#2C2C2E`) and subtle borders (`#3A3A3C`).
  - Crisp ClearType `Segoe UI` typography with high legibility.
  - Apple Blue (`#0A84FF`) accents, Apple Green (`#30D158`) active indicators, and Apple Orange (`#FF9F0A`) tail alerts.
  - Smooth rounded pill buttons and modern track sliders with circular white thumbs and progress fill.
- **Small Monitor Cutoff Fix**:
  - Window client height reduced to **630px** (fits comfortably on 1080p at 125%/150% scaling and 768p laptop displays).
  - Automatically queries and adapts within `SystemParametersInfo(SPI_GETWORKAREA)` to guarantee no controls, buttons, or sliders get cut off.
  - Window automatically centers on your primary work area upon launch.
- **Apple-Style Segmented Navigation**:
  - **`[ Recoil Tuning ]`**: Clean two-column card layout dividing **Sensitivity & Timing** (Master, V/H scale, RPM, Steps, Jitter) and **Stabilization & Dynamics** (V/H decay, decay start shot, kick boost & duration, 45-mag tail vertical & sideways).
  - **`[ Pattern & Vision ]`**: Anti-aliased 45-shot trajectory curve plot, live bullet firing telemetry, steady-state drift readouts, and screenshot auto-calibration.
  - **`[ Presets & Config ]`**: Weapon preset profile library with inline renaming, toggle hotkey picker, ADS requirement switch, and in-game Gunsmith build code import/export.
- **Header Quick-Bar**:
  - Cycle presets with `[◄]` and `[►]` buttons directly from any tab.
  - Prominent master status pill (`ACTIVE` / `STANDBY`).
- **Interactive Machine Vision Review**:
  - `DFCalibWnd` cross-validation modal styled in matching macOS Dark Mode. Inspect and fine-tune mannequin grey/green detection dots in real time.

---

## Features

- **Zero-Dependency Native Binary**: Single lightweight executable (`DFRecoil.exe`, ~470 KB) with native GDI+ image processing and sub-millisecond timer resolution (`timeBeginPeriod(1)`).
- **Master Recoil Multiplier & Independent Axis Scaling**: Global scale slider plus discrete vertical and horizontal multipliers.
- **Vertical & Horizontal Spray Decay**: Counters gun stabilization during full-auto spray (+ weakens pull, - strengthens).
- **Extended Magazine Tail Compensation**: Configurable vertical (`tailV`) and sideways (`tailH`) compensation applied past pattern dots for 45-round and drum magazines.
- **Auto-Calibrate from Screenshot**: Paste (`Ctrl+V`) or drag-and-drop an in-game Gunsmith mannequin screenshot to detect base grey dots (trajectory path) and green dots (loadout spread tightness), compute compression ratios, and generate calibrated recoil curves.
- **Gunsmith Build Code Sharing**: Copy and paste weapon attachment build codes directly between the app and Delta Force.
- **Keyboard Shortcuts**:
  - `1`, `2`, `3`: Switch between Recoil Tuning, Pattern & Vision, and Presets & Config tabs.
  - `F2` / Double-click: Rename active weapon profile.
  - `Ctrl+V`: Paste screenshot from clipboard.
  - `F6` (configurable): Toggle recoil compensation on/off.

---

## Quick Start

1. Download **`DFRecoil.exe`** and **`presets.ini`** from the [Releases](https://github.com/Velgoh/DF-Recoil/releases) page.
2. Run `DFRecoil.exe`.
3. Select your weapon preset (or create a new one).
4. Paste (`Ctrl+V`) a screenshot of your Gunsmith test target to auto-calibrate.
5. In game, press **F6** to toggle assistance (requires holding **Right Mouse Button** to aim down sights by default).

---

## Building from Source

Requires Visual Studio 2022 Build Tools (or Community edition):

```cmd
build.bat
```

Compiles `src\main.cpp` using MSVC with `/O2 /EHsc /W3 /utf-8` linked against `gdiplus.lib`, `gdi32.lib`, `user32.lib`, `comdlg32.lib`, `winmm.lib`, and `shell32.lib`.

---

## Testing & Verification

Run headless screenshot verification across your test suite:

```cmd
DFRecoil.exe --test
```

Or test a specific screenshot:

```cmd
DFRecoil.exe --test "path\to\screenshot.png"
```
