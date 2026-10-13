# DF-Recoil v2.1.0 (Atlus UI Overhaul)

A high-performance standalone Win32/C++ recoil compensator and weapon profile manager for **Delta Force**.

Re-engineered as a native C++ executable with zero runtime dependencies (no Python, no OpenCV). Featuring an **Atlus (Persona / Metaphor) Dark Purple aesthetic** with razor-sharp angular chamfers, diamond sliders, responsive monitor adaptation, Bézier-interpolated mouse movement, and machine vision dot calibration.

---

## What's New in v2.1.0 (Atlus Metaphor UI Overhaul)

- **Atlus Dark Purple Palette**:
  - Midnight Abyss background (`#0C0916`), obsidian-violet card surfaces (`#19112E`), and inset telemetry wells (`#0F0A1C`).
  - Electric Violet borders (`#3E2664`) with high-voltage highlights (`#6B3DB0`).
  - Atlus Signature Neon Magenta (`#E52DF0`) for active tabs, slider progress, and critical action buttons.
  - Pale Lilac (`#D4C3F8`) and stark pure white (`#FFFFFF`) typography for maximum readability.
- **Razor-Sharp Angular Chamfers & Slanted Geometry**:
  - Replaced rounded pill buttons with 45° chamfered polygons and slanted ribbons.
  - Custom Atlus diamond logo and angled switches.
  - Diamond slider thumbs with neon magenta borders and active track progress fills.
  - DWM immersive dark mode title bar integration (`DF-RECOIL // METAPHOR`).
- **Streamlined Three-Tab Architecture**:
  - **`[ RECOIL ]`**: Dual-column layout dividing **Sensitivity** (Master, V/H scale, RPM, Steps, Jitter) and **Stabilization** (V/H decay, decay start shot, kick boost & duration, 45-mag tail vertical & sideways).
  - **`[ TRAJECTORY ]`**: Anti-aliased 45-shot trajectory curve plot, live bullet telemetry, steady drift vectors, and screenshot auto-calibration.
  - **`[ PRESETS ]`**: Weapon preset profile library with inline renaming, toggle hotkey picker, ADS requirement switch, and in-game Gunsmith build code import/export.
- **Interactive Vision Review**:
  - `DFCalibWnd` cross-validation modal with live mannequin grey/green detection dot review in matching Atlus styling.

---

## Features

- **Zero-Dependency Native Binary**: Single lightweight executable (`DFRecoil.exe`, ~470 KB) with native GDI+ image processing and sub-millisecond timer resolution (`timeBeginPeriod(1)`).
- **Master Multiplier & Independent Axis Scaling**: Global scale slider plus discrete vertical and horizontal multipliers.
- **Vertical & Horizontal Spray Decay**: Counters gun stabilization during full-auto spray (+ weakens pull, - strengthens).
- **Extended Magazine Tail Compensation**: Configurable vertical (`tailV`) and sideways (`tailH`) compensation applied past pattern dots for 45-round and drum magazines.
- **Auto-Calibrate from Screenshot**: Paste (`Ctrl+V`) or drag-and-drop an in-game Gunsmith mannequin screenshot to detect base grey dots (trajectory path) and green dots (loadout spread tightness), compute compression ratios, and generate calibrated recoil curves.
- **Gunsmith Build Code Sharing**: Copy and paste weapon attachment build codes directly between the app and Delta Force.
- **Keyboard Shortcuts**:
  - `1`, `2`, `3`: Switch between Recoil, Trajectory, and Presets tabs.
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

Compiles `src\main.cpp` using MSVC with `/O2 /EHsc /W3 /utf-8` linked against `gdiplus.lib`, `gdi32.lib`, `user32.lib`, `comdlg32.lib`, `winmm.lib`, `shell32.lib`, and `dwmapi.lib`.

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

---

*Glory to mankind.*
