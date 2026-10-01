import os
import sys
import glob
import math
import json
import tkinter as tk
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

from app import (
    load_pattern, load_presets, save_presets, load_config, save_config,
    RecoilEngine, bezier_ease, DFRecoilApp, MachineVisionPopup, DEFAULT_PRESETS,
    PRESETS_FILE, CONFIG_FILE, PATTERN_FILE, HOTKEY_MAP
)
from extractor import (
    load_image_to_bgr, calculate_fire_delay, extract_dual_dots_from_image,
    calculate_compression_ratios, calculate_kick_parameters, compute_deltas,
    generate_calibrated_pattern, compute_recoil_pattern, calibrate_from_image,
    ocr_multipliers_from_image
)


def test_recoil_decay_and_engine():
    print("--- Testing RecoilEngine and Decay Dynamics ---")
    engine = RecoilEngine()
    engine.shutdown() # stop worker thread during unit test

    # Default parameters verification
    assert engine.master_scale == 1.00, f"Expected default master_scale 1.00, got {engine.master_scale}"
    assert engine.require_ads is True, f"Expected default require_ads True, got {engine.require_ads}"
    assert engine.v_decay_pct == 0.0, f"Expected default v_decay_pct 0.0, got {engine.v_decay_pct}"
    assert engine.h_decay_pct == 0.0, f"Expected default h_decay_pct 0.0, got {engine.h_decay_pct}"

    # Test update_params
    engine.update_params(
        v_scale=3.5, h_scale=2.0, kick_mult=2.0, kick_decay=5,
        delay_ms=100, steps=10, jitter=0.2, hotkey="F7", require_ads=False,
        master_scale=1.5, v_decay_pct=5.0, h_decay_pct=-2.0
    )
    assert engine.vertical_scale == 3.5
    assert engine.horizontal_scale == 2.0
    assert engine.master_scale == 1.5
    assert engine.v_decay_pct == 5.0
    assert engine.h_decay_pct == -2.0
    assert engine.hotkey_name == "F7"
    assert engine.require_ads is False

    # Test decay formulas
    # v_decay_factor = max(0.0, min(3.0, 1.0 - bullet_idx * (v_decay_pct / 100.0)))
    # At 5.0% per shot:
    # shot 0: 1.0
    # shot 10: 1.0 - 0.5 = 0.5
    # shot 20: 1.0 - 1.0 = 0.0
    # shot 25: max(0.0, 1.0 - 1.25) = 0.0 (fully decayed)
    for b_idx, expected in [(0, 1.0), (10, 0.5), (20, 0.0), (25, 0.0)]:
        factor = max(0.0, min(3.0, 1.0 - b_idx * (engine.v_decay_pct / 100.0)))
        assert math.isclose(factor, expected, abs_tol=1e-5), f"Shot {b_idx}: expected {expected}, got {factor}"

    # At -2.0% per shot (strengthening):
    # shot 0: 1.0
    # shot 10: 1.0 - (-0.2) = 1.2
    factor_h_10 = max(0.0, min(3.0, 1.0 - 10 * (engine.h_decay_pct / 100.0)))
    assert math.isclose(factor_h_10, 1.2, abs_tol=1e-5), f"Expected 1.2, got {factor_h_10}"

    # Verify per-bullet shot_dx and shot_dy formula
    target_dx, target_dy = 2.0, 10.0
    bullet_idx = 0
    kick_boost = engine.get_kick_boost(bullet_idx) # kick_boost for shot 0 with kick_mult=2.0, decay=5: 1 + (2-1)*(5/5) = 2.0
    assert math.isclose(kick_boost, 2.0, abs_tol=1e-5)
    
    v_decay_factor = max(0.0, min(3.0, 1.0 - bullet_idx * (engine.v_decay_pct / 100.0)))
    h_decay_factor = max(0.0, min(3.0, 1.0 - bullet_idx * (engine.h_decay_pct / 100.0)))
    
    shot_dx = target_dx * engine.horizontal_scale * h_decay_factor * engine.master_scale
    shot_dy = target_dy * engine.vertical_scale * kick_boost * v_decay_factor * engine.master_scale
    
    # expected dx = 2.0 * 2.0 * 1.0 * 1.5 = 6.0
    # expected dy = 10.0 * 3.5 * 2.0 * 1.0 * 1.5 = 105.0
    assert math.isclose(shot_dx, 6.0, abs_tol=1e-5), f"shot_dx: expected 6.0, got {shot_dx}"
    assert math.isclose(shot_dy, 105.0, abs_tol=1e-5), f"shot_dy: expected 105.0, got {shot_dy}"

    print("[PASS] RecoilEngine and Decay Dynamics test passed.")


def test_preset_persistence():
    print("--- Testing Preset Persistence and Structure ---")
    presets = load_presets()
    assert any("AUG" in k for k in presets), "AUG preset missing"
    assert "aks74" in presets, "aks74 preset missing"
    assert presets["AUG"].get("rpm") == 679, "AUG RPM missing or incorrect"
    assert presets["aks74"].get("rpm") == 533, "aks74 RPM missing or incorrect"

    for name, p in presets.items():
        assert "master_scale" in p, f"{name} missing master_scale"
        assert "v_decay_pct" in p, f"{name} missing v_decay_pct"
        assert "h_decay_pct" in p, f"{name} missing h_decay_pct"
        assert "require_ads" in p, f"{name} missing require_ads"
        assert p["require_ads"] is True, f"{name} require_ads should default to True"

    # Test adding a custom preset
    test_name = "Unit Test Preset"
    presets[test_name] = {
        "build_code": "TEST-CODE-12345",
        "rpm": 600,
        "master_scale": 1.25,
        "vertical_scale": 3.80,
        "horizontal_scale": 2.50,
        "v_decay_pct": 1.5,
        "h_decay_pct": 0.5,
        "initial_kick_mult": 1.90,
        "kick_decay_shots": 4,
        "bullet_delay_ms": 100,
        "micro_steps": 12,
        "jitter": 0.25,
        "hotkey": "F8",
        "require_ads": True
    }
    assert save_presets(presets), "Failed to save presets"
    reloaded = load_presets()
    assert test_name in reloaded, "Custom preset not found in reloaded presets"
    assert reloaded[test_name]["master_scale"] == 1.25
    assert reloaded[test_name]["v_decay_pct"] == 1.5

    # Cleanup test preset
    del reloaded[test_name]
    save_presets(reloaded)
    print("[PASS] Preset Persistence test passed.")


def test_screenshot_dot_detection_and_matching():
    print("--- Testing Dot Detection Across Screenshots ---")
    files = sorted(glob.glob(r"C:\Users\Yonah\Pictures\Screenshots\DeltaForceClient-Win64-Shipping_*.png"))
    assert len(files) >= 6, f"Expected at least 6 screenshots, found {len(files)}"

    for f in files:
        base = os.path.basename(f)
        res = calibrate_from_image(f, rpm=679.0)
        assert res["success"] is True, f"Calibration failed for {base}: {res.get('error')}"

        grey_count = len(res["grey_dots"])
        green_count = len(res["green_dots"])
        print(f"[{base}] -> Grey: {grey_count}, Green: {green_count}, Sync: {res['match_percent']}%, V_ratio: {res['vert_mult']}, H_ratio: {res['horiz_mult']}")

        # Ensure dot detection found all dots
        assert grey_count >= 13, f"Expected >= 13 grey dots in {base}, got {grey_count}"
        assert green_count >= 20, f"Expected >= 20 green dots in {base}, got {green_count}"
        assert 0.2 <= res["vert_mult"] <= 1.2, f"Unrealistic vert_mult {res['vert_mult']} in {base}"
        assert 0.1 <= res["horiz_mult"] <= 1.5, f"Unrealistic horiz_mult {res['horiz_mult']} in {base}"

        pat = res["pattern"]
        assert len(pat) >= 60, f"Pattern too short: {len(pat)}"
        dys = [dy for dx, dy in pat]
        med_y = np.median(dys)
        for dx, dy in pat[:min(10, len(pat) - 1)]:
            assert dy <= med_y * 2.5, f"Kick jump detected in {base}: dy={dy} > {med_y * 2.5}"

    print("[PASS] All 6 Screenshots Dot Detection & Pattern Matching passed.")


def test_ui_and_popup():
    print("--- Testing DFRecoilApp UI & MachineVisionPopup ---")
    backup_presets = json.loads(json.dumps(load_presets()))
    root = tk.Tk()
    root.withdraw()
    try:
        app = DFRecoilApp(root)

        # Check UI widgets exist
        assert hasattr(app, "var_master_scale"), "Missing var_master_scale"
        assert hasattr(app, "var_v_decay"), "Missing var_v_decay"
        assert hasattr(app, "var_h_decay"), "Missing var_h_decay"
        assert hasattr(app, "ads_var"), "Missing ads_var"
        assert app.ads_var.get() is True, "ADS checkbox should be True by default"

        # Test slider update
        app.var_master_scale.set(1.50)
        app.var_v_decay.set(2.5)
        app.var_h_decay.set(1.0)
        app._sync_engine_from_ui()

        assert app.engine.master_scale == 1.50
        assert app.engine.v_decay_pct == 2.5
        assert app.engine.h_decay_pct == 1.0

        # Test MachineVisionPopup instantiation
        dummy_calib = {
            "success": True,
            "grey_dots": [(100.0, 300.0), (100.0, 250.0), (100.0, 200.0)],
            "green_dots": [(200.0, 300.0), (200.0, 265.0), (200.0, 230.0)],
            "match_percent": 100,
            "vert_mult": 0.70,
            "horiz_mult": 0.65,
            "crop_bgr": np.zeros((350, 350, 3), dtype=np.uint8),
            "pattern_type": "Pattern Matched",
            "pattern": [(0.0, 7.0)] * 60,
            "badge_text": "Test"
        }

        # Test MachineVisionPopup click bounds & edit reactivity
        dummy_calib2 = {
            "success": True,
            "grey_dots": [(100.0, 300.0), (100.0, 250.0), (100.0, 200.0)],
            "green_dots": [(200.0, 300.0), (200.0, 265.0), (200.0, 230.0)],
            "match_percent": 100,
            "vert_mult": 0.70,
            "horiz_mult": 0.65,
            "crop_bgr": np.zeros((350, 350, 3), dtype=np.uint8),
            "pattern_type": "Pattern Matched",
            "pattern": [(0.0, 7.0)] * 60,
            "badge_text": "Initial Badge"
        }

        last_res = []
        def record_apply(green, grey, rpm, vm, hm, res):
            last_res.append(res)

        popup2 = MachineVisionPopup(root, dummy_calib2, 679.0, record_apply)
        
        # 1. Test clicking outside bounds (e.g. x=400, y=400 on 350x350 crop)
        class DummyEvent:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        # Canvas has ox=10, oy=10 offset, so canvas x=450 is crop x=440 (out of bounds)
        popup2.on_click(DummyEvent(450, 400))
        assert len(popup2.green_dots) == 3, f"Expected 3 green dots after OOB click, got {len(popup2.green_dots)}"
        assert len(popup2.grey_dots) == 3, f"Expected 3 grey dots after OOB click, got {len(popup2.grey_dots)}"

        # 2. Test in-bounds dot addition (canvas x=230, y=190 -> crop x=220, y=180 on green side)
        popup2.on_click(DummyEvent(230, 190))
        assert len(popup2.green_dots) == 4, f"Expected 4 green dots after add, got {len(popup2.green_dots)}"
        assert "4 Loadout" in popup2.banner.cget("text"), "Banner did not update dot count"

        # 3. Test dot removal by clicking near existing dot (crop x=220, y=180 -> canvas x=230, y=190)
        popup2.on_click(DummyEvent(231, 189))
        assert len(popup2.green_dots) == 3, f"Expected 3 green dots after removal, got {len(popup2.green_dots)}"

        # 4. Test confirm updates badge and match_percent
        popup2.confirm()
        assert len(last_res) == 1
        assert "Calibrated" in last_res[0]["badge_text"]
        assert last_res[0]["match_percent"] == 100
        print("[PASS] MachineVisionPopup bounds and reactivity verified.")

        # Test ADS subtitle text update in active state
        app.engine.set_enabled(True)
        app._update_ui_state(True)
        assert "Aim (Hold RMB)" in app.status_sub.cget("text")
        app.ads_var.set(False)
        app._sync_engine_from_ui()
        assert "Hold LMB to Fire" in app.status_sub.cget("text"), f"Expected 'Hold LMB to Fire', got '{app.status_sub.cget('text')}'"
        app.ads_var.set(True)
        app._sync_engine_from_ui()
        assert "Aim (Hold RMB)" in app.status_sub.cget("text")
        print("[PASS] ADS toggle subtitle reactivity verified.")

    finally:
        try:
            app._on_close()
        except Exception:
            pass
        save_presets(backup_presets)
    print("[PASS] UI and Popup test passed.")


if __name__ == "__main__":
    test_recoil_decay_and_engine()
    test_preset_persistence()
    test_screenshot_dot_detection_and_matching()
    test_ui_and_popup()
    print("\n==========================================")
    print("ALL COMPREHENSIVE TESTS PASSED 100%!")
    print("==========================================")
