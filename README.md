# DF-Recoil // Universal Recoil Compensator for Delta Force

DF-Recoil is a lightweight, standalone recoil compensator and weapon preset manager for Delta Force. It provides smooth, humanized curve compensation, customizable weapon profiles, and built-in weapon build code sharing.

## Features

- **Spacious Two-Column Dashboard**: Clean, modern dark-themed UI designed for clarity without compacting or cutting off controls.
- **Master Recoil Scale**: Global multiplier slider scaling overall compensation strength up or down in one place.
- **Vertical & Horizontal Recoil Decay**: Separate per-bullet strength loss sliders (+ weakens pull, - strengthens; decays down to 0% strength) to counter weapon stabilization during full-auto spray.
- **Auto-Calibrate from Screenshot**: Paste (`Ctrl+V`) or select in-game Gunsmith mannequin screenshots. The system extracts base grey dots (trajectory path) and green dots (loadout spread tightness), computes exact vertical/horizontal compression ratios, and builds a calibrated profile.
- **Machine Vision Cross-Validation**: Interactive overlay showing detected dots and trajectory curves with click-to-add/delete dot corrections.
- **Universal Presets & Build Codes**: Create, delete, switch, and save weapon profiles with built-in Gunsmith modification build codes and one-click clipboard copying.
- **Dedicated Save & Auto-Save**: Quick Save button right next to presets, plus automatic preset persistence on exit.
- **Natural Smoothing & Kick Boost**: Bézier-interpolated micro-stepping, initial kick decay curve, and humanized jitter.
- **Hotkey & ADS-By-Default**: Default requirement to aim down sights (Hold RMB) with toggle hotkey (default: F6).

## Installation & Quick Start

1. Download `DF-Recoil.zip` from the [Releases](https://github.com/Velgoh/DF-Recoil/releases) page.
2. Extract the folder anywhere on your PC.
3. Double-click **`Start DF-Recoil.bat`** (automatically checks and installs requirements if needed).
4. Select or create your weapon preset, paste a Gunsmith screenshot to auto-calibrate, and toggle with **F6** in-game!

## Project Structure

```
DF-Recoil/
├── Start DF-Recoil.bat        # Auto-launch script with dependency check
├── README.md
├── core/
│   ├── app.py                # Main application & GUI
│   ├── extractor.py          # Machine vision dot extraction & pattern matching
│   ├── presets.json          # Weapon presets and tuning parameters
│   ├── config.json           # Active preset configuration
│   ├── pattern.json          # Calibrated recoil curve profile
│   ├── requirements.txt      # Python package requirements
│   ├── test_verification.py  # Unit test suite
│   └── test_comprehensive.py # Vision & engine validation suite
```

---

*Glory to mankind.*
