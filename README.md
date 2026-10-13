# DF-Recoil v2.2.0

A high-performance standalone Win32/C++ recoil compensation engine and weapon profile manager for Delta Force.

Written in native C++ with zero runtime dependencies (no Python, no OpenCV). Features an overhaul with Persona 5 dark purple aesthetic, halftone backdrop, -4.5° skewed polygon cards, diamond sliders, trajectory curve plotting, and machine-vision dot calibration.

---

## How It Works

1. **Compensation Engine & Input Dispatch**:
   - The engine operates on an independent high-priority worker thread using `timeBeginPeriod(1)` to maintain sub-millisecond precision.
   - Mouse movement offsets are calculated per bullet interval (`60000 / RPM`) and subdivided into smoothing steps (`steps`), dispatching relative movement via the Windows `SendInput` API (`MOUSEEVENTF_MOVE`).
   - Accumulator sub-pixel math prevents precision drift across long sprays.
   - Optional Gaussian jitter simulates organic mouse handling.

2. **Recoil Curve & Dynamics**:
   - **Master & Axis Scaling**: Global multiplier plus independent vertical and horizontal scaling.
   - **Initial Kick**: Amplifies initial pull (`kickMult`) across the first `kickShots` bullets to overcome initial muzzle climb, decaying smoothly into steady-state compensation.
   - **Spray Stabilization Decay**: `vDecay` and `hDecay` (% per shot) reduce or increase pull starting at `decayStart` shot to match in-game weapon stabilization mechanics.
   - **Extended Magazine Tail**: Past the base pattern shots, a steady drift vector is sustained with configurable vertical (`tailV`) and horizontal (`tailH`) scale factors for 45-round magazines and drum attachments.

3. **Vision Calibration from Screenshots**:
   - Paste (`Ctrl+V`) or drag-and-drop a screenshot of the in-game Gunsmith test target into the app.
   - GDI+ color segmentation isolates the base grey dots (initial weapon trajectory) and green dots (attachment-modified trajectory).
   - Computes vertical and horizontal compression ratios (`vRatio`, `hRatio`), kick boost, and match percentage.
   - Interactive cross-validation window (`DFCalibWnd`) enables dot review and manual point adjustments before applying to the active preset.

4. **Gunsmith Build Code Integration**:
   - Directly copy and paste weapon attachment build codes between the app and Delta Force to keep profiles aligned with your in-game loadouts.

5. **Interface**:
   - Dark Purple palette: Midnight Abyss background (`#0a0714`), Obsidian Violet card containers (`#140d24`), Electric Violet borders (`#8a2be2`), Neon Magenta accents (`#e024c3`), Atlus Yellow highlights (`#ffe600`), and pure white/comic black contrast.
   - Halftone dot matrix backdrop with comic diagonal edge slashes.
   - -4.5° skewed polygon cards with 3.0px solid black ink borders and 6.0px comic drop shadows.
   - Tilted ransom-note header badges (`[DF-RECOIL]` and `[YONAH]`).
   - Slanted comic buttons, diamond sliders, and trajectory visualization.
   - Spacious 1140x700 layout with Impact and Segoe UI typography.

---

## Default Controls & Configuration

| Parameter | Default | Description |
|---|---|---|
| **Master Toggle** | `F6` | Global hotkey to engage or suspend compensation |
| **ADS Requirement** | `Enabled` | Requires holding Right Mouse Button to compensate |
| **Master Scale** | `1.00x` | Global multiplier applied to all movement offsets |
| **Vertical Scale** | `1.00x` | Multiplier for vertical downward compensation |
| **Horizontal Scale** | `1.00x` | Multiplier for horizontal lateral compensation |
| **Fire Rate (RPM)** | Weapon default | Rate of fire in rounds per minute |
| **Smoothing Steps** | `10` | Intermediate interpolation sub-steps per shot |
| **Initial Kick** | `1.00x` | Multiplier for first-shot muzzle rise |
| **Kick Duration** | `3 shots` | Number of shots over which initial kick decays |
| **Tabs** | `1`, `2`, `3` | Quick-switch between Recoil, Trajectory, and Presets |
| **Rename Preset** | `F2` / Double-click | Inline renaming of active weapon preset |
| **Paste Target** | `Ctrl+V` | Paste screenshot from clipboard for calibration |

Configuration and weapon profiles are saved automatically to `presets.ini`.

---

## Building from Source

Requires Visual Studio 2022 (Community, Professional, or Build Tools):

```cmd
build.bat
```

Compiles `src\main.cpp` using MSVC with `/O2 /std:c++17 /EHsc /W3 /utf-8` linked against `gdiplus.lib`, `gdi32.lib`, `user32.lib`, `comdlg32.lib`, `winmm.lib`, `shell32.lib`, and `dwmapi.lib`. Output executable: `DFRecoil.exe`.

---

## Running Tests

Run the headless screenshot test suite:

```cmd
DFRecoil.exe --test
```

Or test against a specific screenshot:

```cmd
DFRecoil.exe --test "path\to\target.png"
```

The test suite validates:
- Mannequin dot extraction and green/grey dot detection
- Vertical and horizontal compression ratio calculations
- Kick parameter extraction and shot decay curves
- Classic and smooth trajectory generation
- Synchronization percentage bounds

---

## Support

For issues, bug reports, or feature requests, please open an issue on GitHub.

Glory to mankind.
