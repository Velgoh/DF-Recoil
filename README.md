# DF-Recoil // Universal Recoil Compensator for Delta Force

DF-Recoil is a lightweight, standalone recoil compensator and weapon preset manager for Delta Force. It provides smooth, humanized curve compensation, customizable weapon profiles, and built-in weapon build code sharing.

## Features

- **Universal Presets**: Create, switch, and save distinct recoil profiles for different weapons and attachments.
- **Weapon Build Codes**: Attach in-game Gunsmith modification codes directly to presets with one-click copy to clipboard.
- **Natural Smoothing**: Bézier-interpolated micro-stepping eliminates jagged cursor motion.
- **Dynamic Kick Boost**: Smooth initial kick compensation curve decays into steady sustained fire.
- **Customizable Tuning**: Sliders for vertical/horizontal scale, initial kick multiplier, kick decay shots, fire delay, micro-steps, and jitter.
- **Hotkey & ADS Toggle**: Instant toggle via hotkey (default: F6) and optional Right Mouse Button (ADS) requirement.
- **Zero Dependencies**: Runs on standard Windows Python 3.10+ without external third-party packages.

## Bundled Preset

Pre-configured with a calibrated AUG setup:
- **Weapon**: AUG (Laser Build)
- **Build Code**: `AUG Assault Rifle-Warfare-6LFHGS4073PHD3H80H3R3`
- **Settings**: Vertical 4.20x, Horizontal 3.85x, Kick Mult 2.20x, Decay 6 shots, Delay 133ms, Steps 10, Jitter 0.35px, Hotkey F6.

## Installation

### Option 1: Release Package (Ready to Run)
1. Download `DF-Recoil.zip` from the [Releases](https://github.com/Velgoh/DF-Recoil/releases) page.
2. Extract the archive anywhere on your PC.
3. Run `Start DF-Recoil.bat`.

### Option 2: Run from Source
1. Ensure Python 3.10+ is installed on Windows.
2. Clone this repository:
   ```bash
   git clone https://github.com/Velgoh/DF-Recoil.git
   cd DF-Recoil
   ```
3. Launch via the root batch file:
   ```cmd
   Start DF-Recoil.bat
   ```
   Or run directly:
   ```bash
   python core/app.py
   ```

## Usage

1. Open `Start DF-Recoil.bat`.
2. Select your desired weapon preset from the dropdown.
3. Press your hotkey (**F6** by default) or click the status banner in the GUI to enable compensation.
4. In-game, hold Left Mouse Button (LMB) to fire.
5. If using build codes, click **Copy** next to the Build Code field and paste it directly into Delta Force's Gunsmith import screen.

## Project Structure

```
DF-Recoil/
├── Start DF-Recoil.bat      # Quick launcher
├── README.md
├── core/
│   ├── app.py              # Main application & GUI
│   ├── presets.json        # Weapon presets and build codes
│   ├── config.json         # Active preset configuration
│   ├── pattern.json        # Calibrated recoil curve profile
│   ├── requirements.txt    # Standard library notice
│   └── test_verification.py # Test suite
```

---

*Glory to mankind.*
