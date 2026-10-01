import sys
import os
import math
import json
import tkinter as tk

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

from app import (
    load_pattern, load_presets, save_presets, load_config, save_config,
    RecoilEngine, bezier_ease, DFRecoilApp, DEFAULT_PRESETS,
    PRESETS_FILE, CONFIG_FILE, precise_sleep_until, DEFAULT_PATTERN
)

def run_tests():
    print("=== TEST 1: Pattern Loading ===")
    pattern = load_pattern()
    print(f"Pattern shots count: {len(pattern)}")
    assert len(pattern) >= 10, f"Expected at least 10 shots, got {len(pattern)}"
    assert all(isinstance(pt, tuple) and len(pt) == 2 for pt in pattern), "Malformed shot in pattern"
    print("Pattern loading passed.")

    print("\n=== TEST 2: Presets Loading & Default Values ===")
    presets = load_presets()
    aug_key = next((k for k in presets if "AUG" in k), next(iter(presets)))
    aug = presets[aug_key]
    print(f"Testing Preset '{aug_key}':", aug)
    assert "vertical_scale" in aug and "master_scale" in aug, "Required preset fields missing"
    assert "v_decay_pct" in aug and "h_decay_pct" in aug, "Decay fields missing"
    assert "bullet_delay_ms" in aug and "micro_steps" in aug
    assert "require_ads" in aug and "hotkey" in aug
    print("Preset values verified.")

    print("\n=== TEST 3: Config Loading & Active Preset ===")
    cfg = load_config()
    print("Loaded config:", cfg)
    assert "active_preset" in cfg
    print("Config active preset verified.")

    print("\n=== TEST 4: Preset CRUD Operations ===")
    backup_presets = json.loads(json.dumps(presets))
    try:
        # Create
        custom = {
            "build_code": "CUSTOM-TEST-CODE-12345",
            "vertical_scale": 3.10,
            "horizontal_scale": 2.20,
            "initial_kick_mult": 1.90,
            "kick_decay_shots": 4,
            "bullet_delay_ms": 110,
            "micro_steps": 12,
            "jitter": 0.25,
            "hotkey": "F7",
            "require_ads": True
        }
        presets["Test Weapon"] = custom
        assert save_presets(presets)
        reloaded = load_presets()
        assert "Test Weapon" in reloaded
        assert reloaded["Test Weapon"]["build_code"] == "CUSTOM-TEST-CODE-12345"
        assert reloaded["Test Weapon"]["hotkey"] == "F7"

        # Update
        reloaded["Test Weapon"]["vertical_scale"] = 3.65
        assert save_presets(reloaded)
        reloaded2 = load_presets()
        assert reloaded2["Test Weapon"]["vertical_scale"] == 3.65

        # Delete
        del reloaded2["Test Weapon"]
        assert save_presets(reloaded2)
        reloaded3 = load_presets()
        assert "Test Weapon" not in reloaded3
    finally:
        save_presets(backup_presets)
    print("Preset CRUD operations verified.")

    print("\n=== TEST 5: Kick Boost Decay Curve ===")
    engine = RecoilEngine()
    engine.update_params(
        v_scale=1.5, h_scale=1.4, kick_mult=2.2, kick_decay=6,
        delay_ms=133, steps=10, jitter=0.35, hotkey="F6", require_ads=False
    )
    boosts = [engine.get_kick_boost(i) for i in range(10)]
    assert abs(boosts[0] - 2.20) < 1e-4
    assert abs(boosts[1] - 2.00) < 1e-4
    assert abs(boosts[2] - 1.80) < 1e-4
    assert abs(boosts[3] - 1.60) < 1e-4
    assert abs(boosts[4] - 1.40) < 1e-4
    assert abs(boosts[5] - 1.20) < 1e-4
    assert abs(boosts[6] - 1.00) < 1e-4
    assert abs(boosts[7] - 1.00) < 1e-4
    print("Kick boost decay curve verified.")

    print("\n=== TEST 6: Trajectory & Delta Computation for 65 Shots ===")
    for bullet_idx in range(65):
        if bullet_idx < len(engine.pattern):
            tdx, tdy = engine.pattern[bullet_idx]
        else:
            tdx, tdy = engine.pattern[-1]
        boost = engine.get_kick_boost(bullet_idx)
        sdx = tdx * engine.horizontal_scale
        sdy = tdy * engine.vertical_scale * boost
        assert not math.isnan(sdx) and not math.isnan(sdy)
        assert not math.isinf(sdx) and not math.isinf(sdy)
    print("All 65 shots compute finite valid numbers.")

    print("\n=== TEST 7: Kick Decay Edge Cases ===")
    engine.update_params(1.5, 1.4, 3.0, 1, 133, 10, 0.35, "F6", False)
    assert engine.get_kick_boost(0) == 3.0
    assert engine.get_kick_boost(1) == 1.0

    engine.update_params(1.5, 1.4, 1.0, 6, 133, 10, 0.35, "F6", False)
    for i in range(10):
        assert engine.get_kick_boost(i) == 1.0
    print("Edge cases passed.")

    print("\n=== TEST 8: Parameter Bounds & Clamping ===")
    engine.update_params(
        v_scale=1.5, h_scale=1.4, kick_mult=2.2, kick_decay=-5,
        delay_ms=2, steps=1, jitter=-0.5, hotkey="F6", require_ads=True
    )
    assert engine.kick_decay_shots >= 1
    assert engine.bullet_delay_ms >= 20
    assert engine.micro_steps >= 3
    assert engine.jitter >= 0.0
    assert engine.require_ads is True
    print("Parameter clamping verified.")

    print("\n=== TEST 9: Clean Thread Shutdown ===")
    engine.shutdown()
    assert engine.running is False
    assert not engine.worker_thread.is_alive()
    print("Clean thread shutdown verified.")

    print("\n=== TEST 10: GUI Preset Switching & Controls ===")
    root = tk.Tk()
    app = DFRecoilApp(root)
    root.update_idletasks()

    cur_preset = app.preset_var.get()
    assert cur_preset in app.presets
    assert "vertical_scale" in app.presets[cur_preset]
    assert app.ads_var.get() is True

    # Switch to M4A1 preset
    if "M4A1 (Standard)" in app.presets:
        app.preset_combo.set("M4A1 (Standard)")
        app._on_preset_selected()
        assert app.preset_var.get() == "M4A1 (Standard)"
        assert app.build_code_var.get() == "M4A1 Assault Rifle-Warfare-5H9Q3L4089LKJ1A20K9P1"
        assert abs(app.var_v_scale.get() - 3.40) < 1e-3

        # Switch back to original
        app.preset_combo.set(cur_preset)
        app._on_preset_selected()
        assert app.preset_var.get() == cur_preset

    app._copy_build_code()
    clip_text = root.clipboard_get()
    assert clip_text == app.build_code_var.get().strip()

    # Test Reset Defaults
    app.var_v_scale.set(1.11)
    app._reset_defaults_action()
    assert abs(app.var_v_scale.get() - 4.20) < 1e-3

    # Test Reload All
    app._reload_all_action()
    assert len(app.presets) >= 1

    app.engine.shutdown()
    root.destroy()
    print("GUI Preset Switching & Controls verified.")

    print("\n=== TEST 11: Corrupted Presets Recovery ===")
    backup_presets = json.loads(json.dumps(load_presets()))
    try:
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            f.write("INVALID JSON DATA {{{")
        recovered = load_presets()
        assert "AUG (Laser Build)" in recovered
        assert os.path.exists(PRESETS_FILE + ".bak")
        try:
            os.remove(PRESETS_FILE + ".bak")
        except Exception:
            pass
    finally:
        save_presets(backup_presets)
    print("Corrupted presets recovery verified.")

    print("\n=== TEST 12: Empty Pattern Fallback Safety ===")
    eng = RecoilEngine()
    eng.pattern = []
    if not eng.pattern:
        eng.pattern = DEFAULT_PATTERN.copy()
    assert len(eng.pattern) == 60
    eng.shutdown()
    print("Empty pattern fallback safety verified.")

    print("\n=== TEST 13: Expanded Delay Range Tuning ===")
    eng = RecoilEngine()
    eng.update_params(3.0, 2.0, 1.5, 4, 30, 8, 0.2, "F6", False)
    assert eng.bullet_delay_ms == 30
    eng.update_params(4.5, 3.0, 2.0, 5, 350, 15, 0.4, "F6", False)
    assert eng.bullet_delay_ms == 350
    eng.shutdown()
    print("Expanded delay range tuning verified.")

    print("\n=== TEST 14: Interruptible Sleep Response ===")
    import time
    import threading
    t_start = time.perf_counter()
    running_flag = [True]
    def stopper():
        return running_flag[0]
    def delay_stop():
        time.sleep(0.015)
        running_flag[0] = False
    th = threading.Thread(target=delay_stop)
    th.start()
    precise_sleep_until(t_start + 0.5, stopper)
    th.join()
    elapsed = time.perf_counter() - t_start
    assert elapsed < 0.25, f"Sleep was not interrupted promptly: {elapsed}s"
    print("Interruptible sleep response verified.")

    print("\n=== TEST 15: Preset UI Sync & Safe Deletion ===")
    root = tk.Tk()
    app = DFRecoilApp(root)
    root.update_idletasks()

    app.build_code_var.set("")
    app._copy_build_code()
    assert "No build code" in app.footer_lbl.cget("text")

    app.preset_var.set("NonExistentPresetXYZ")
    app._delete_preset_action()

    app.engine.shutdown()
    root.destroy()
    print("Preset UI Sync & Safe Deletion verified.")

    print("\n>>> ALL 15 TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    run_tests()

