import os
import sys
import time
import math
import json
import random
import ctypes
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import List, Tuple, Dict, Any, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

user32 = ctypes.windll.user32
winmm = ctypes.windll.winmm

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

MOUSEEVENTF_MOVE = 0x0001
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02

HOTKEY_MAP = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "CapsLock": 0x14,
    "Insert": 0x2D, "Delete": 0x2E, "Home": 0x24, "End": 0x23,
    "PageUp": 0x21, "PageDown": 0x22,
    "NumLock": 0x90, "ScrollLock": 0x91,
    "Mouse4 (XButton1)": 0x05, "Mouse5 (XButton2)": 0x06
}

DEFAULT_PATTERN = [
    (-0.59, 7.52), (-1.63, 7.41), (-1.68, 7.37), (-1.01, 7.51),
    (-0.95, 7.49), (-0.87, 7.53), (0.05, 7.58), (-0.17, 7.58),
    (-0.06, 7.59), (0.42, 7.56), (0.17, 7.58), (0.75, 7.54),
    (1.37, 7.45), (0.91, 7.53), (1.62, 7.40), (1.72, 7.39),
    (1.74, 7.36), (2.13, 7.25), (1.75, 7.38), (2.46, 7.15),
    (2.25, 7.22), (2.67, 7.04), (2.74, 6.99), (2.39, 7.19),
    (3.23, 6.80), (2.47, 7.17), (2.85, 6.96), (2.63, 7.09),
    (2.73, 7.04), (2.61, 7.09), (1.88, 7.35), (2.22, 7.22),
    (1.58, 7.42), (3.31, 6.81), (0.44, 7.57), (0.42, 7.58),
    (0.42, 7.58), (1.94, 7.20), (1.99, 7.27), (0.24, 7.58),
    (0.65, 7.52), (1.53, 7.41), (0.96, 7.52), (0.36, 7.56),
    (0.36, 7.56), (0.55, 7.55), (0.82, 7.53), (1.24, 7.47),
    (1.48, 7.42), (1.15, 7.49), (0.72, 7.54), (0.38, 7.57),
    (0.25, 7.58), (0.48, 7.56), (0.95, 7.51), (1.36, 7.44),
    (1.52, 7.41), (1.18, 7.48), (0.68, 7.55), (0.35, 7.57)
]

PRESETS_FILE = os.path.join(SCRIPT_DIR, "presets.json")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
PATTERN_FILE = os.path.join(SCRIPT_DIR, "pattern.json")

DEFAULT_PRESETS: Dict[str, Dict[str, Any]] = {
    "AUG": {
        "build_code": "AUG Assault Rifle-Warfare-6LFHGS4073PHD3H80H3R3",
        "rpm": 679,
        "master_scale": 1.20,
        "vertical_scale": 2.70,
        "horizontal_scale": 2.92,
        "v_decay_pct": 1.0,
        "h_decay_pct": -1.0,
        "initial_kick_mult": 1.00,
        "kick_decay_shots": 2,
        "bullet_delay_ms": 88,
        "micro_steps": 10,
        "jitter": 0.35,
        "hotkey": "F6",
        "require_ads": True
    },
    "aks74": {
        "build_code": "AUG Assault Rifle-Warfare-6LFHGS4073PHD3H80H3R3",
        "rpm": 533,
        "master_scale": 0.41,
        "vertical_scale": 3.77,
        "horizontal_scale": 1.79,
        "v_decay_pct": 0.7,
        "h_decay_pct": 10.0,
        "initial_kick_mult": 1.20,
        "kick_decay_shots": 3,
        "bullet_delay_ms": 113,
        "micro_steps": 10,
        "jitter": 0.35,
        "hotkey": "F6",
        "require_ads": True
    }
}


def load_pattern() -> List[Tuple[float, float]]:
    if os.path.exists(PATTERN_FILE):
        try:
            with open(PATTERN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                shots = data.get("shots", [])
                if shots:
                    return [(float(s["dx"]), float(s["dy"])) for s in shots]
        except Exception:
            pass
    return DEFAULT_PATTERN.copy()


def load_presets() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    for name, p in data.items():
                        p.setdefault("master_scale", 1.00)
                        p.setdefault("v_decay_pct", 0.0)
                        p.setdefault("h_decay_pct", 0.0)
                        p.setdefault("require_ads", True)
                        if "rpm" not in p and "bullet_delay_ms" in p:
                            p["rpm"] = round(60000.0 / p["bullet_delay_ms"]) if p["bullet_delay_ms"] > 0 else 679
                    return data
        except Exception:
            try:
                bak_path = PRESETS_FILE + ".bak"
                os.replace(PRESETS_FILE, bak_path)
            except Exception:
                pass
    presets = json.loads(json.dumps(DEFAULT_PRESETS))
    save_presets(presets)
    return presets


def save_presets(presets: Dict[str, Dict[str, Any]]) -> bool:
    try:
        tmp_file = PRESETS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2)
        os.replace(tmp_file, PRESETS_FILE)
        return True
    except Exception:
        return False


def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active_preset": "AUG"}


def save_config(cfg: Dict[str, Any]) -> bool:
    try:
        tmp_file = CONFIG_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp_file, CONFIG_FILE)
        return True
    except Exception:
        return False


def precise_sleep_until(target_perf_time: float, should_run=None) -> None:
    while True:
        if should_run and not should_run():
            break
        remaining = target_perf_time - time.perf_counter()
        if remaining <= 0:
            break
        if remaining > 0.002:
            time.sleep(0.001)


def bezier_ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    p1 = 0.35
    p2 = 0.75
    return 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * (t ** 2) * p2 + (t ** 3)


class RecoilEngine:
    def __init__(self):
        self.enabled = False
        self.running = True
        self.master_scale = 1.00
        self.vertical_scale = 4.20
        self.horizontal_scale = 3.85
        self.v_decay_pct = 0.0
        self.h_decay_pct = 0.0
        self.initial_kick_mult = 2.20
        self.kick_decay_shots = 6
        self.bullet_delay_ms = 133
        self.micro_steps = 10
        self.jitter = 0.35
        self.hotkey_name = "F6"
        self.require_ads = True

        self.pattern = load_pattern()
        self.gui_hwnd = None
        self.on_state_change = None

        winmm.timeBeginPeriod(1)
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def set_gui_hwnd(self, hwnd):
        self.gui_hwnd = hwnd

    def toggle(self):
        self.enabled = not self.enabled
        if self.on_state_change:
            self.on_state_change(self.enabled)

    def set_enabled(self, state: bool):
        self.enabled = state
        if self.on_state_change:
            self.on_state_change(self.enabled)

    def update_params(
        self,
        v_scale,
        h_scale,
        kick_mult,
        kick_decay,
        delay_ms,
        steps,
        jitter,
        hotkey,
        require_ads,
        master_scale=1.00,
        v_decay_pct=0.0,
        h_decay_pct=0.0
    ):
        self.master_scale = max(0.10, min(5.00, float(master_scale)))
        self.vertical_scale = float(v_scale)
        self.horizontal_scale = float(h_scale)
        self.v_decay_pct = float(v_decay_pct)
        self.h_decay_pct = float(h_decay_pct)
        self.initial_kick_mult = float(kick_mult)
        self.kick_decay_shots = max(1, min(30, int(kick_decay)))
        self.bullet_delay_ms = max(20, min(1000, int(delay_ms)))
        self.micro_steps = max(3, min(50, int(steps)))
        self.jitter = max(0.0, float(jitter))
        self.hotkey_name = hotkey
        self.require_ads = bool(require_ads)

    def get_kick_boost(self, bullet_idx: int) -> float:
        if bullet_idx < self.kick_decay_shots and self.kick_decay_shots > 0:
            factor = (self.kick_decay_shots - bullet_idx) / float(self.kick_decay_shots)
            return 1.0 + (self.initial_kick_mult - 1.0) * factor
        return 1.0

    def _is_lmb_down(self) -> bool:
        return (user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000) != 0

    def _is_rmb_down(self) -> bool:
        return (user32.GetAsyncKeyState(VK_RBUTTON) & 0x8000) != 0

    def _is_hotkey_pressed(self) -> bool:
        vk = HOTKEY_MAP.get(self.hotkey_name, 0x75)
        return (user32.GetAsyncKeyState(vk) & 0x8000) != 0

    def _is_gui_focused(self) -> bool:
        if not self.gui_hwnd:
            return False
        try:
            fg = user32.GetForegroundWindow()
            if not fg:
                return False
            if fg == self.gui_hwnd:
                return True
            if user32.GetAncestor(fg, 2) == self.gui_hwnd or user32.GetAncestor(fg, 3) == self.gui_hwnd:
                return True
        except Exception:
            pass
        return False

    def _worker_loop(self):
        hotkey_prev = False
        accum_x = 0.0
        accum_y = 0.0

        while self.running:
            hotkey_now = self._is_hotkey_pressed()
            if hotkey_now and not hotkey_prev:
                self.toggle()
            hotkey_prev = hotkey_now

            if not self.enabled:
                time.sleep(0.01)
                continue

            if self._is_gui_focused():
                time.sleep(0.01)
                continue

            if not self._is_lmb_down():
                time.sleep(0.002)
                continue

            if self.require_ads and not self._is_rmb_down():
                time.sleep(0.002)
                continue

            bullet_idx = 0
            accum_x = 0.0
            accum_y = 0.0

            while self.running and self.enabled and self._is_lmb_down():
                if self.require_ads and not self._is_rmb_down():
                    break
                if self._is_gui_focused():
                    break

                if not self.pattern:
                    self.pattern = DEFAULT_PATTERN.copy()

                if bullet_idx < len(self.pattern):
                    target_dx, target_dy = self.pattern[bullet_idx]
                else:
                    target_dx, target_dy = self.pattern[-1]

                kick_boost = self.get_kick_boost(bullet_idx)

                v_decay_factor = max(0.0, min(3.0, 1.0 - bullet_idx * (self.v_decay_pct / 100.0)))
                h_decay_factor = max(0.0, min(3.0, 1.0 - bullet_idx * (self.h_decay_pct / 100.0)))

                shot_dx = target_dx * self.horizontal_scale * h_decay_factor * self.master_scale
                shot_dy = target_dy * self.vertical_scale * kick_boost * v_decay_factor * self.master_scale

                steps = self.micro_steps
                step_duration = (self.bullet_delay_ms / 1000.0) / steps
                shot_start_time = time.perf_counter()

                prev_ease = 0.0
                stopped_early = False
                for s in range(1, steps + 1):
                    hk_mid = self._is_hotkey_pressed()
                    if hk_mid and not hotkey_prev:
                        self.toggle()
                        hotkey_prev = hk_mid
                        stopped_early = True
                        break
                    hotkey_prev = hk_mid

                    if not (self.running and self.enabled and self._is_lmb_down()):
                        stopped_early = True
                        break

                    if self.require_ads and not self._is_rmb_down():
                        stopped_early = True
                        break

                    if self._is_gui_focused():
                        stopped_early = True
                        break

                    t = s / steps
                    curr_ease = bezier_ease(t)
                    delta_progress = curr_ease - prev_ease
                    prev_ease = curr_ease

                    step_x = shot_dx * delta_progress
                    step_y = shot_dy * delta_progress

                    if self.jitter > 0:
                        jx = random.gauss(0, self.jitter * 0.12)
                        jy = random.gauss(0, self.jitter * 0.12)
                        step_x += jx
                        step_y += jy

                    accum_x += step_x
                    accum_y += step_y

                    move_x = int(accum_x)
                    move_y = int(accum_y)
                    accum_x -= move_x
                    accum_y -= move_y

                    if move_x != 0 or move_y != 0:
                        user32.mouse_event(MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)

                    step_deadline = shot_start_time + s * step_duration
                    precise_sleep_until(step_deadline, lambda: self.running and self.enabled and self._is_lmb_down())

                if stopped_early:
                    break

                bullet_idx += 1

            accum_x = 0.0
            accum_y = 0.0

    def shutdown(self):
        self.running = False
        winmm.timeEndPeriod(1)
        if hasattr(self, "worker_thread") and self.worker_thread.is_alive():
            try:
                self.worker_thread.join(timeout=0.2)
            except Exception:
                pass


class MachineVisionPopup(tk.Toplevel):
    def __init__(self, parent, calib_res, rpm_val, apply_cb):
        super().__init__(parent)
        self.title("Pattern Cross-Validation")
        self.geometry("620x680")
        self.minsize(580, 600)
        self.configure(bg="#0D1117")
        self.apply_cb = apply_cb
        self.calib_res = calib_res
        self.rpm_val = rpm_val
        self.green_dots = list(calib_res.get("green_dots", []))
        self.grey_dots = list(calib_res.get("grey_dots", []))
        self.crop_bgr = calib_res.get("crop_bgr")

        match_pct = calib_res.get("match_percent", 0)
        vert_mult = calib_res.get("vert_mult", 1.0)
        horiz_mult = calib_res.get("horiz_mult", 1.0)
        pattern_type = calib_res.get("pattern_type", "Calculated")

        hdr_frame = tk.Frame(self, bg="#0D1117")
        hdr_frame.pack(fill="x", padx=16, pady=(10, 4))

        self.banner = tk.Label(
            hdr_frame,
            text=f"Synchronized: {len(self.grey_dots)} Base / {len(self.green_dots)} Loadout Dots ({match_pct}% Match)",
            fg="#10B981", bg="#0D1117", font=("Segoe UI", 10, "bold")
        )
        self.banner.pack(anchor="w")

        self.ratio_status = tk.Label(
            hdr_frame,
            text=f"Compression Ratios: Vert ×{vert_mult:.2f} | Horiz ×{horiz_mult:.2f} | Mode: {pattern_type}",
            fg="#38BDF8", bg="#0D1117", font=("Segoe UI", 9)
        )
        self.ratio_status.pack(anchor="w", pady=(2, 0))

        hint_lbl = tk.Label(
            hdr_frame,
            text="Tip: Left side clicks add/remove Grey dots. Right side clicks add/remove Green dots.",
            fg="#8B949E", bg="#0D1117", font=("Segoe UI", 8)
        )
        hint_lbl.pack(anchor="w", pady=(2, 4))

        canvas_container = tk.Frame(self, bg="#161B22", highlightbackground="#30363D", highlightthickness=1)
        canvas_container.pack(fill="both", expand=True, padx=16, pady=4)

        self.canvas = tk.Canvas(canvas_container, bg="#161B22", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=2, pady=2)

        self.tk_img = None
        if self.crop_bgr is not None:
            try:
                from PIL import Image, ImageTk
                import cv2
                rgb = cv2.cvtColor(self.crop_bgr, cv2.COLOR_BGR2RGB)
                self.tk_img = ImageTk.PhotoImage(image=Image.fromarray(rgb))
                self.canvas.create_image(10, 10, anchor="nw", image=self.tk_img)
            except Exception:
                pass

        btn_frame = tk.Frame(self, bg="#0D1117")
        btn_frame.pack(fill="x", padx=16, pady=(8, 12))

        tk.Button(
            btn_frame, text="Reset to Auto-Detected", font=("Segoe UI", 9),
            bg="#21262D", fg="#F0F6FC", activebackground="#30363D", activeforeground="#F0F6FC",
            relief="flat", bd=0, padx=10, pady=5, cursor="hand2", command=self.reset
        ).pack(side="left")

        tk.Button(
            btn_frame, text="Confirm & Apply", font=("Segoe UI", 9, "bold"),
            bg="#21262D", fg="#10B981", activebackground="#30363D", activeforeground="#10B981",
            relief="flat", bd=0, padx=12, pady=5, cursor="hand2", command=self.confirm
        ).pack(side="right")

        tk.Button(
            btn_frame, text="Cancel", font=("Segoe UI", 9),
            bg="#21262D", fg="#EF4444", activebackground="#30363D", activeforeground="#EF4444",
            relief="flat", bd=0, padx=10, pady=5, cursor="hand2", command=self.destroy
        ).pack(side="right", padx=6)

        self.canvas.bind("<Button-1>", self.on_click)
        self.draw_overlays()

    def reset(self):
        self.green_dots = list(self.calib_res.get("green_dots", []))
        self.grey_dots = list(self.calib_res.get("grey_dots", []))
        self.draw_overlays()

    def on_click(self, event):
        x = event.x - 10
        y = event.y - 10
        if x < 0 or y < 0:
            return

        cw = self.crop_bgr.shape[1] if self.crop_bgr is not None else 360
        ch = self.crop_bgr.shape[0] if self.crop_bgr is not None else 400
        if x >= cw or y >= ch:
            return

        split_x = int(cw * 0.48)
        removed = False

        if x >= split_x:
            for i, (dx, dy) in enumerate(self.green_dots):
                if (dx - x) ** 2 + (dy - y) ** 2 < 64:
                    self.green_dots.pop(i)
                    removed = True
                    break
            if not removed:
                self.green_dots.append((float(x), float(y)))
        else:
            for i, (dx, dy) in enumerate(self.grey_dots):
                if (dx - x) ** 2 + (dy - y) ** 2 < 64:
                    self.grey_dots.pop(i)
                    removed = True
                    break
            if not removed:
                self.grey_dots.append((float(x), float(y)))

        self.draw_overlays()

    def draw_overlays(self):
        self.canvas.delete("overlay")

        # Offset for canvas margin
        ox, oy = 10, 10

        n_grey = len(self.grey_dots)
        n_green = len(self.green_dots)
        if n_grey == 0 and n_green == 0:
            match_pct = 0
        elif max(n_grey, n_green) > 0:
            match_pct = round(100.0 * min(n_grey, n_green) / max(n_grey, n_green))
        else:
            match_pct = 100

        self.banner.config(
            text=f"Synchronized: {n_grey} Base / {n_green} Loadout Dots ({match_pct}% Match)"
        )

        for dx, dy in self.grey_dots:
            self.canvas.create_oval(
                ox + dx - 5, oy + dy - 5, ox + dx + 5, oy + dy + 5,
                outline="#FFFFFF", dash=(2, 2), tags="overlay", width=1
            )
        for dx, dy in self.green_dots:
            self.canvas.create_oval(
                ox + dx - 4, oy + dy - 4, ox + dx + 4, oy + dy + 4,
                outline="#10B981", width=2, tags="overlay"
            )

        if len(self.grey_dots) > 1:
            sorted_grey_pts = sorted(self.grey_dots, key=lambda d: -d[1])
            pts_grey = []
            for dx, dy in sorted_grey_pts:
                pts_grey.extend([ox + dx, oy + dy])
            self.canvas.create_line(pts_grey, fill="#94A3B8", tags="overlay", width=1)

        if len(self.green_dots) > 1:
            sorted_green = sorted(self.green_dots, key=lambda d: -d[1])
            pts = []
            for dx, dy in sorted_green:
                pts.extend([ox + dx, oy + dy])
            self.canvas.create_line(pts, fill="#10B981", tags="overlay", width=2)

        if len(self.grey_dots) >= 2 and len(self.green_dots) >= 1:
            try:
                from extractor import calculate_compression_ratios
                v_mult, h_mult = calculate_compression_ratios(self.grey_dots, self.green_dots)
                sorted_grey = sorted(self.grey_dots, key=lambda d: -d[1])
                sorted_green = sorted(self.green_dots, key=lambda d: -d[1])
                base_gx, base_gy = sorted_green[0]
                base_rx, base_ry = sorted_grey[0]

                calc_pts = []
                for dx, dy in sorted_grey:
                    cx = base_gx + (dx - base_rx) * h_mult
                    cy = base_gy - (base_ry - dy) * v_mult
                    calc_pts.extend([ox + cx, oy + cy])
                if len(calc_pts) >= 4:
                    self.canvas.create_line(calc_pts, fill="#38BDF8", dash=(3, 2), tags="overlay", width=2)

                self.ratio_status.config(
                    text=f"Ratios: Vert ×{v_mult:.2f} | Horiz ×{h_mult:.2f} | Base: {n_grey}, Loadout: {n_green}"
                )
            except Exception:
                pass
        else:
            self.ratio_status.config(
                text=f"Ratios: Vert ×1.00 | Horiz ×1.00 | Base: {n_grey}, Loadout: {n_green}"
            )

    def confirm(self):
        from extractor import calculate_compression_ratios, generate_calibrated_pattern, calculate_kick_parameters, calculate_fire_delay
        v_ratio, h_ratio = calculate_compression_ratios(self.grey_dots, self.green_dots)
        ref_dots = self.green_dots if len(self.green_dots) >= 2 else self.grey_dots
        kp = calculate_kick_parameters(ref_dots)
        pat, steady = generate_calibrated_pattern(
            self.grey_dots, self.green_dots,
            v_ratio=v_ratio, h_ratio=h_ratio,
            initial_kick_mult=kp["initial_kick_mult"],
            kick_decay_shots=kp["kick_decay_shots"]
        )

        n_grey = len(self.grey_dots)
        n_green = len(self.green_dots)
        if n_grey == 0 and n_green == 0:
            match_pct = 0
        elif max(n_grey, n_green) > 0:
            match_pct = round(100.0 * min(n_grey, n_green) / max(n_grey, n_green))
        else:
            match_pct = 100

        delay_ms = calculate_fire_delay(self.rpm_val)
        shot_count = max(n_green, n_grey)
        new_badge = f"Calibrated {shot_count} shots @ {int(self.rpm_val)} RPM ({delay_ms}ms) | Ratio: V×{v_ratio:.2f} H×{h_ratio:.2f} ({match_pct}% Sync)"

        res = dict(self.calib_res)
        res["grey_dots"] = self.grey_dots
        res["green_dots"] = self.green_dots
        res["grey_count"] = n_grey
        res["green_count"] = n_green
        res["match_percent"] = match_pct
        res["badge_text"] = new_badge
        res["pattern"] = pat
        res["steady_state"] = steady
        res["vert_mult"] = v_ratio
        res["horiz_mult"] = h_ratio
        res["pattern_type"] = "Pattern Matched" if n_grey >= 2 and n_green >= 2 else "Fallback"

        self.apply_cb(self.green_dots, self.grey_dots, self.rpm_val, v_ratio, h_ratio, res)
        self.destroy()


class DFRecoilApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Delta Force Recoil Manager")
        self.root.geometry("1000x800")
        self.root.minsize(920, 720)
        self.root.resizable(True, True)

        self.BG_COLOR = "#0D1117"
        self.CARD_BG = "#161B22"
        self.CARD_BORDER = "#30363D"
        self.TEXT_MAIN = "#F0F6FC"
        self.TEXT_MUTED = "#8B949E"
        self.ACCENT_CYAN = "#38BDF8"
        self.ACCENT_GOLD = "#F59E0B"
        self.ACTIVE_GREEN = "#10B981"
        self.ACTIVE_BG = "#064E3B"
        self.INACTIVE_RED = "#EF4444"
        self.INACTIVE_BG = "#7F1D1D"
        self.BTN_NORMAL = "#21262D"
        self.BTN_HOVER = "#30363D"

        self.root.configure(bg=self.BG_COLOR)

        self.presets = load_presets()
        self.config = load_config()

        self.engine = RecoilEngine()
        self.engine.on_state_change = self._on_engine_state_change

        self._calib_img_path = None
        self._calib_img_pil = None
        self._last_calib_res = None

        self.root.update_idletasks()
        try:
            f = self.root.wm_frame()
            self.hwnd = int(f, 16) if f else user32.GetAncestor(self.root.winfo_id(), 2)
            self.engine.set_gui_hwnd(self.hwnd)
        except Exception:
            self.hwnd = None

        self._configure_styles()
        self._build_ui()

        active_preset = self.config.get("active_preset", "AUG")
        if active_preset not in self.presets:
            active_preset = next(iter(self.presets)) if self.presets else "AUG"
        self._refresh_preset_list(select_name=active_preset)
        self._load_preset_to_ui(active_preset)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_styles(self):
        try:
            style = ttk.Style()
            style.theme_use("clam")
            style.configure(
                "TCombobox",
                fieldbackground="#0D1117",
                background="#21262D",
                foreground="#F0F6FC",
                darkcolor="#30363D",
                lightcolor="#30363D",
                bordercolor="#30363D",
                arrowcolor="#38BDF8"
            )
            style.map(
                "TCombobox",
                fieldbackground=[("readonly", "#0D1117")],
                foreground=[("readonly", "#F0F6FC")]
            )
            style.configure(
                "TScale",
                background=self.CARD_BG,
                troughcolor="#0D1117",
                sliderrelief="flat"
            )
        except Exception:
            pass

    def _build_ui(self):
        header = tk.Frame(self.root, bg=self.BG_COLOR)
        header.pack(fill="x", padx=16, pady=(10, 4))
        tk.Label(
            header, text="Delta Force Recoil Manager", font=("Segoe UI", 15, "bold"),
            fg=self.ACCENT_CYAN, bg=self.BG_COLOR
        ).pack(anchor="w")

        self.toggle_frame = tk.Frame(
            self.root, bg=self.INACTIVE_BG,
            highlightbackground=self.INACTIVE_RED, highlightthickness=2, cursor="hand2"
        )
        self.toggle_frame.pack(fill="x", padx=16, pady=(4, 6))
        self.toggle_frame.bind("<Button-1>", lambda e: self.engine.toggle())

        self.status_title = tk.Label(
            self.toggle_frame, text="Standby (Disabled)",
            font=("Segoe UI", 12, "bold"), fg="#FFFFFF", bg=self.INACTIVE_BG, cursor="hand2"
        )
        self.status_title.pack(pady=(4, 1))
        self.status_title.bind("<Button-1>", lambda e: self.engine.toggle())

        self.status_sub = tk.Label(
            self.toggle_frame, text="Press [F6] or click banner to enable",
            font=("Segoe UI", 9, "bold"), fg="#FECACA", bg=self.INACTIVE_BG, cursor="hand2"
        )
        self.status_sub.pack(pady=(0, 4))
        self.status_sub.bind("<Button-1>", lambda e: self.engine.toggle())

        body = tk.Frame(self.root, bg=self.BG_COLOR)
        body.pack(fill="both", expand=True, padx=16, pady=(2, 4))

        col_left = tk.Frame(body, bg=self.BG_COLOR)
        col_left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        col_right = tk.Frame(body, bg=self.BG_COLOR)
        col_right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        # Master scale
        master_card = tk.Frame(col_left, bg=self.CARD_BG, highlightbackground=self.CARD_BORDER, highlightthickness=1)
        master_card.pack(fill="x", pady=(0, 4))
        self.var_master_scale = tk.DoubleVar(value=1.00)
        self.lbl_master_val = self._create_slider_row(
            master_card, "Master Scale",
            self.var_master_scale, 0.10, 3.00, 0.01, "{:.2f}x"
        )

        # Recoil tuning
        sliders_card = tk.Frame(col_left, bg=self.CARD_BG, highlightbackground=self.CARD_BORDER, highlightthickness=1)
        sliders_card.pack(fill="both", expand=True, pady=(0, 4))

        self.var_v_scale = tk.DoubleVar(value=2.70)
        self.lbl_v_val = self._create_slider_row(
            sliders_card, "Vertical Scale",
            self.var_v_scale, 0.10, 6.00, 0.01, "{:.2f}x"
        )

        self.var_h_scale = tk.DoubleVar(value=2.92)
        self.lbl_h_val = self._create_slider_row(
            sliders_card, "Horizontal Scale",
            self.var_h_scale, 0.10, 6.00, 0.01, "{:.2f}x"
        )

        self.var_v_decay = tk.DoubleVar(value=1.0)
        self.lbl_v_decay_val = self._create_slider_row(
            sliders_card, "Vertical Decay (%/shot)",
            self.var_v_decay, -5.0, 10.0, 0.1, "{:+.1f}%"
        )

        self.var_h_decay = tk.DoubleVar(value=-1.0)
        self.lbl_h_decay_val = self._create_slider_row(
            sliders_card, "Horizontal Decay (%/shot)",
            self.var_h_decay, -5.0, 10.0, 0.1, "{:+.1f}%"
        )

        self.var_kick_mult = tk.DoubleVar(value=1.00)
        self.lbl_kick_mult_val = self._create_slider_row(
            sliders_card, "Initial Kick",
            self.var_kick_mult, 1.00, 4.00, 0.05, "{:.2f}x"
        )

        self.var_kick_decay = tk.IntVar(value=2)
        self.lbl_kick_decay_val = self._create_slider_row(
            sliders_card, "Kick Duration",
            self.var_kick_decay, 1, 15, 1, "{} shots"
        )

        self.var_delay = tk.IntVar(value=88)
        self.lbl_delay_val = self._create_slider_row(
            sliders_card, "Fire Delay (ms)",
            self.var_delay, 20, 400, 1, "{} ms"
        )

        self.var_steps = tk.IntVar(value=10)
        self.lbl_steps_val = self._create_slider_row(
            sliders_card, "Smoothing Steps",
            self.var_steps, 3, 30, 1, "{} steps"
        )

        self.var_jitter = tk.DoubleVar(value=0.35)
        self.lbl_jitter_val = self._create_slider_row(
            sliders_card, "Jitter",
            self.var_jitter, 0.00, 1.50, 0.01, "±{:.2f} px"
        )

        # Controls & activation
        opts_card = tk.Frame(col_left, bg=self.CARD_BG, highlightbackground=self.CARD_BORDER, highlightthickness=1)
        opts_card.pack(fill="x", pady=(0, 4))
        opts_inner = tk.Frame(opts_card, bg=self.CARD_BG)
        opts_inner.pack(fill="x", padx=12, pady=6)

        tk.Label(
            opts_inner, text="Toggle Hotkey:", font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_MAIN, bg=self.CARD_BG
        ).pack(side="left")

        self.hotkey_var = tk.StringVar(value="F6")
        self.hk_combo = ttk.Combobox(
            opts_inner, textvariable=self.hotkey_var,
            values=list(HOTKEY_MAP.keys()), state="readonly", width=12
        )
        self.hk_combo.pack(side="left", padx=(6, 16))
        self.hk_combo.bind("<<ComboboxSelected>>", self._on_hotkey_changed)

        self.ads_var = tk.BooleanVar(value=True)
        self.ads_chk = tk.Checkbutton(
            opts_inner, text="Require ADS (Hold RMB)",
            variable=self.ads_var, font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_MAIN, bg=self.CARD_BG,
            activebackground=self.CARD_BG, activeforeground=self.ACCENT_CYAN,
            selectcolor=self.BG_COLOR, command=self._sync_engine_from_ui
        )
        self.ads_chk.pack(side="left")

        # Action buttons
        btn_frame = tk.Frame(col_left, bg=self.BG_COLOR)
        btn_frame.pack(fill="x", pady=(0, 4))
        for txt, cmd, fg in [
            ("Save Preset", self._save_preset_action, self.ACTIVE_GREEN),
            ("Reset Defaults", self._reset_defaults_action, self.ACCENT_GOLD),
            ("Reload All", self._reload_all_action, self.ACCENT_CYAN)
        ]:
            tk.Button(
                btn_frame, text=txt, font=("Segoe UI", 9, "bold"), fg=fg,
                bg=self.BTN_NORMAL, activebackground=self.BTN_HOVER, activeforeground=fg,
                relief="flat", bd=0, padx=8, pady=5, cursor="hand2", command=cmd
            ).pack(side="left", expand=True, fill="x", padx=2)

        # Preset manager
        preset_card = tk.Frame(col_right, bg=self.CARD_BG, highlightbackground=self.CARD_BORDER, highlightthickness=1)
        preset_card.pack(fill="x", pady=(0, 4))

        p_hdr = tk.Frame(preset_card, bg=self.CARD_BG)
        p_hdr.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(
            p_hdr, text="Weapon Preset Manager", font=("Segoe UI", 10, "bold"),
            fg=self.TEXT_MAIN, bg=self.CARD_BG
        ).pack(anchor="w")

        p_row1 = tk.Frame(preset_card, bg=self.CARD_BG)
        p_row1.pack(fill="x", padx=12, pady=4)
        tk.Label(
            p_row1, text="Preset:", font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_MAIN, bg=self.CARD_BG
        ).pack(side="left")

        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(p_row1, textvariable=self.preset_var, state="readonly", width=18)
        self.preset_combo.pack(side="left", padx=(6, 6))
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)

        tk.Button(
            p_row1, text="Save", font=("Segoe UI", 8, "bold"), fg=self.ACTIVE_GREEN,
            bg=self.BTN_NORMAL, activebackground=self.BTN_HOVER, activeforeground=self.ACTIVE_GREEN,
            relief="flat", bd=0, padx=8, pady=3, cursor="hand2", command=self._save_preset_action
        ).pack(side="left", padx=2)

        tk.Button(
            p_row1, text="+ New", font=("Segoe UI", 8, "bold"), fg=self.ACCENT_CYAN,
            bg=self.BTN_NORMAL, activebackground=self.BTN_HOVER, activeforeground=self.ACCENT_CYAN,
            relief="flat", bd=0, padx=8, pady=3, cursor="hand2", command=self._new_preset_action
        ).pack(side="left", padx=2)

        tk.Button(
            p_row1, text="Delete", font=("Segoe UI", 8, "bold"), fg=self.INACTIVE_RED,
            bg=self.BTN_NORMAL, activebackground=self.BTN_HOVER, activeforeground=self.INACTIVE_RED,
            relief="flat", bd=0, padx=8, pady=3, cursor="hand2", command=self._delete_preset_action
        ).pack(side="left", padx=2)

        p_row2 = tk.Frame(preset_card, bg=self.CARD_BG)
        p_row2.pack(fill="x", padx=12, pady=(2, 8))
        tk.Label(
            p_row2, text="Build Code:", font=("Segoe UI", 8, "bold"),
            fg=self.TEXT_MAIN, bg=self.CARD_BG
        ).pack(side="left")

        self.build_code_var = tk.StringVar()
        self.build_code_entry = tk.Entry(
            p_row2, textvariable=self.build_code_var,
            font=("Consolas", 8), bg="#0D1117", fg=self.ACCENT_CYAN,
            insertbackground="#FFFFFF", relief="flat",
            highlightbackground=self.CARD_BORDER, highlightcolor=self.ACCENT_CYAN, highlightthickness=1
        )
        self.build_code_entry.pack(side="left", fill="x", expand=True, padx=(6, 4))

        self.btn_copy_code = tk.Button(
            p_row2, text="Copy", font=("Segoe UI", 8, "bold"),
            fg=self.TEXT_MAIN, bg=self.BTN_NORMAL,
            activebackground=self.BTN_HOVER, activeforeground=self.ACCENT_CYAN,
            relief="flat", bd=0, padx=8, pady=2, cursor="hand2", command=self._copy_build_code
        )
        self.btn_copy_code.pack(side="right")

        # Auto-calibrate
        calib_card = tk.Frame(col_right, bg=self.CARD_BG, highlightbackground=self.CARD_BORDER, highlightthickness=1)
        calib_card.pack(fill="x", pady=(0, 4))

        tk.Label(
            calib_card, text="Auto-Calibrate from Screenshot", font=("Segoe UI", 10, "bold"),
            fg=self.TEXT_MAIN, bg=self.CARD_BG
        ).pack(anchor="w", padx=12, pady=(8, 2))

        tk.Label(
            calib_card,
            text="Extracts base and loadout patterns from screenshots to compute compensation ratios.",
            font=("Segoe UI", 8), fg=self.TEXT_MUTED, bg=self.CARD_BG, wraplength=440, justify="left"
        ).pack(anchor="w", padx=12, pady=(0, 4))

        c_row1 = tk.Frame(calib_card, bg=self.CARD_BG)
        c_row1.pack(fill="x", padx=12, pady=4)

        tk.Button(
            c_row1, text="Select Screenshot...", font=("Segoe UI", 8, "bold"), fg=self.TEXT_MAIN,
            bg=self.BTN_NORMAL, activebackground=self.BTN_HOVER, activeforeground=self.ACCENT_CYAN,
            relief="flat", bd=0, padx=10, pady=4, cursor="hand2", command=self._select_screenshot
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            c_row1, text="Paste Screenshot (Ctrl+V)", font=("Segoe UI", 8), fg=self.TEXT_MAIN,
            bg=self.BTN_NORMAL, activebackground=self.BTN_HOVER, activeforeground=self.ACCENT_CYAN,
            relief="flat", bd=0, padx=10, pady=4, cursor="hand2", command=self._paste_screenshot
        ).pack(side="left")

        c_row2 = tk.Frame(calib_card, bg=self.CARD_BG)
        c_row2.pack(fill="x", padx=12, pady=4)

        tk.Label(
            c_row2, text="Weapon RPM:", font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_MAIN, bg=self.CARD_BG
        ).pack(side="left")

        self.rpm_var = tk.StringVar(value="679")
        tk.Entry(
            c_row2, textvariable=self.rpm_var, font=("Consolas", 9), width=6,
            bg="#0D1117", fg=self.ACCENT_CYAN, insertbackground="#FFFFFF", relief="flat",
            highlightbackground=self.CARD_BORDER, highlightcolor=self.ACCENT_CYAN, highlightthickness=1
        ).pack(side="left", padx=(6, 12))

        tk.Button(
            c_row2, text="Calibrate & Verify...", font=("Segoe UI", 9, "bold"), fg=self.ACTIVE_GREEN,
            bg=self.BTN_NORMAL, activebackground=self.BTN_HOVER, activeforeground=self.ACTIVE_GREEN,
            relief="flat", bd=0, padx=12, pady=3, cursor="hand2", command=self._run_calibration
        ).pack(side="left")

        c_row3 = tk.Frame(calib_card, bg=self.CARD_BG)
        c_row3.pack(fill="x", padx=12, pady=(2, 8))

        self.calib_badge = tk.Label(
            c_row3, text="No screenshot analyzed yet.", font=("Segoe UI", 8),
            fg=self.TEXT_MUTED, bg=self.CARD_BG
        )
        self.calib_badge.pack(side="left")

        # Telemetry
        telemetry_card = tk.Frame(col_right, bg=self.CARD_BG, highlightbackground=self.CARD_BORDER, highlightthickness=1)
        telemetry_card.pack(fill="both", expand=True, pady=(0, 4))

        tk.Label(
            telemetry_card, text="Pattern & Telemetry", font=("Segoe UI", 10, "bold"),
            fg=self.TEXT_MAIN, bg=self.CARD_BG
        ).pack(anchor="w", padx=12, pady=(8, 4))

        self.lbl_telemetry_shots = tk.Label(
            telemetry_card, text="Loaded Pattern: 60 shots active",
            font=("Segoe UI", 9), fg=self.TEXT_MAIN, bg=self.CARD_BG
        )
        self.lbl_telemetry_shots.pack(anchor="w", padx=12, pady=1)

        self.lbl_telemetry_ratios = tk.Label(
            telemetry_card, text="Compression: Vert ×1.00 | Horiz ×1.00",
            font=("Segoe UI", 9), fg=self.ACCENT_CYAN, bg=self.CARD_BG
        )
        self.lbl_telemetry_ratios.pack(anchor="w", padx=12, pady=1)

        self.lbl_telemetry_decay = tk.Label(
            telemetry_card, text="Active Decay: V: +0.0%/shot | H: +0.0%/shot",
            font=("Segoe UI", 9), fg=self.ACCENT_GOLD, bg=self.CARD_BG
        )
        self.lbl_telemetry_decay.pack(anchor="w", padx=12, pady=1)

        self.lbl_telemetry_steady = tk.Label(
            telemetry_card, text="Steady-State Drift: dx = +0.35, dy = +7.57",
            font=("Segoe UI", 9), fg=self.TEXT_MUTED, bg=self.CARD_BG
        )
        self.lbl_telemetry_steady.pack(anchor="w", padx=12, pady=1)

        self.btn_open_vision = tk.Button(
            telemetry_card, text="Open Cross-Validation", font=("Segoe UI", 8, "bold"),
            fg=self.ACCENT_CYAN, bg=self.BTN_NORMAL, activebackground=self.BTN_HOVER, activeforeground=self.ACCENT_CYAN,
            relief="flat", bd=0, padx=10, pady=4, cursor="hand2", command=self._open_vision_popup
        )
        self.btn_open_vision.pack(anchor="w", padx=12, pady=(8, 8))

        self.footer_lbl = tk.Label(
            self.root, text="Ready",
            font=("Segoe UI", 8), fg=self.TEXT_MUTED, bg=self.BG_COLOR
        )
        self.footer_lbl.pack(side="bottom", pady=(0, 4))

        self.root.bind("<Control-v>", lambda e: self._paste_screenshot())

    def _create_slider_row(self, parent, title, variable, from_, to, resolution, val_format, subtext=""):
        container = tk.Frame(parent, bg=self.CARD_BG)
        container.pack(fill="x", padx=12, pady=3)

        hdr = tk.Frame(container, bg=self.CARD_BG)
        hdr.pack(fill="x")

        tk.Label(
            hdr, text=title, font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_MAIN, bg=self.CARD_BG
        ).pack(side="left")

        val_lbl = tk.Label(
            hdr, text=val_format.format(variable.get()), font=("Segoe UI", 9, "bold"),
            fg=self.ACCENT_CYAN, bg=self.CARD_BG
        )
        val_lbl.pack(side="right")

        if subtext:
            tk.Label(
                container, text=subtext, font=("Segoe UI", 8),
                fg=self.TEXT_MUTED, bg=self.CARD_BG
            ).pack(anchor="w")

        def on_slider_move(val):
            try:
                raw_val = float(val)
                snapped = round(raw_val / resolution) * resolution
                if resolution >= 1.0:
                    variable.set(int(snapped))
                else:
                    decimals = max(0, -int(math.floor(math.log10(resolution))))
                    variable.set(round(snapped, decimals))
            except Exception:
                pass
            val_lbl.config(text=val_format.format(variable.get()))
            self._sync_engine_from_ui()

        scale = ttk.Scale(
            container, from_=from_, to=to, variable=variable,
            command=on_slider_move
        )
        scale.pack(fill="x", pady=(2, 2))
        return val_lbl

    def _refresh_preset_list(self, select_name=None):
        names = list(self.presets.keys())
        self.preset_combo["values"] = names
        if select_name and select_name in names:
            self.preset_combo.set(select_name)
        elif names:
            self.preset_combo.set(names[0])

    def _load_preset_to_ui(self, name: str):
        preset = self.presets.get(name)
        if not preset:
            return
        self.preset_var.set(name)
        self.build_code_var.set(preset.get("build_code", ""))

        rpm_val = preset.get("rpm")
        if rpm_val is not None:
            self.rpm_var.set(str(int(rpm_val)))
        else:
            delay = preset.get("bullet_delay_ms", 88)
            calc_rpm = round(60000.0 / delay) if delay > 0 else 679
            self.rpm_var.set(str(int(calc_rpm)))

        self.var_master_scale.set(float(preset.get("master_scale", 1.00)))
        self.var_v_scale.set(float(preset.get("vertical_scale", 2.70)))
        self.var_h_scale.set(float(preset.get("horizontal_scale", 2.92)))
        self.var_v_decay.set(float(preset.get("v_decay_pct", 0.0)))
        self.var_h_decay.set(float(preset.get("h_decay_pct", 0.0)))
        self.var_kick_mult.set(float(preset.get("initial_kick_mult", 1.00)))
        self.var_kick_decay.set(int(preset.get("kick_decay_shots", 2)))
        self.var_delay.set(int(preset.get("bullet_delay_ms", 88)))
        self.var_steps.set(int(preset.get("micro_steps", 10)))
        self.var_jitter.set(float(preset.get("jitter", 0.35)))
        self.hotkey_var.set(str(preset.get("hotkey", "F6")))
        self.ads_var.set(bool(preset.get("require_ads", True)))

        self.lbl_master_val.config(text=f"{self.var_master_scale.get():.2f}x")
        self.lbl_v_val.config(text=f"{self.var_v_scale.get():.2f}x")
        self.lbl_h_val.config(text=f"{self.var_h_scale.get():.2f}x")
        self.lbl_v_decay_val.config(text=f"{self.var_v_decay.get():+.1f}%")
        self.lbl_h_decay_val.config(text=f"{self.var_h_decay.get():+.1f}%")
        self.lbl_kick_mult_val.config(text=f"{self.var_kick_mult.get():.2f}x")
        self.lbl_kick_decay_val.config(text=f"{self.var_kick_decay.get()} shots")
        self.lbl_delay_val.config(text=f"{self.var_delay.get()} ms")
        self.lbl_steps_val.config(text=f"{self.var_steps.get()} steps")
        self.lbl_jitter_val.config(text=f"±{self.var_jitter.get():.2f} px")

        self._sync_engine_from_ui()
        self._update_hotkey_display()
        self._update_telemetry_display()

    def _get_ui_preset_data(self) -> Dict[str, Any]:
        try:
            rpm_val = int(float(self.rpm_var.get()))
        except ValueError:
            delay = int(self.var_delay.get())
            rpm_val = round(60000.0 / delay) if delay > 0 else 679

        return {
            "build_code": self.build_code_var.get().strip(),
            "rpm": rpm_val,
            "master_scale": round(float(self.var_master_scale.get()), 2),
            "vertical_scale": round(float(self.var_v_scale.get()), 2),
            "horizontal_scale": round(float(self.var_h_scale.get()), 2),
            "v_decay_pct": round(float(self.var_v_decay.get()), 1),
            "h_decay_pct": round(float(self.var_h_decay.get()), 1),
            "initial_kick_mult": round(float(self.var_kick_mult.get()), 2),
            "kick_decay_shots": int(self.var_kick_decay.get()),
            "bullet_delay_ms": int(self.var_delay.get()),
            "micro_steps": int(self.var_steps.get()),
            "jitter": round(float(self.var_jitter.get()), 2),
            "hotkey": self.hotkey_var.get(),
            "require_ads": self.ads_var.get()
        }

    def _sync_engine_from_ui(self):
        self.engine.update_params(
            v_scale=self.var_v_scale.get(),
            h_scale=self.var_h_scale.get(),
            kick_mult=self.var_kick_mult.get(),
            kick_decay=self.var_kick_decay.get(),
            delay_ms=self.var_delay.get(),
            steps=self.var_steps.get(),
            jitter=self.var_jitter.get(),
            hotkey=self.hotkey_var.get(),
            require_ads=self.ads_var.get(),
            master_scale=self.var_master_scale.get(),
            v_decay_pct=self.var_v_decay.get(),
            h_decay_pct=self.var_h_decay.get()
        )
        if hasattr(self, "lbl_telemetry_decay"):
            self.lbl_telemetry_decay.config(
                text=f"Active Decay: V: {self.var_v_decay.get():+.1f}%/shot | H: {self.var_h_decay.get():+.1f}%/shot"
            )
        self._update_hotkey_display()

    def _update_hotkey_display(self):
        hk = self.hotkey_var.get()
        if not self.engine.enabled:
            self.status_sub.config(text=f"Press [{hk}] or click banner to enable")
        else:
            ads_text = "Aim (Hold RMB) + Fire (LMB)" if self.ads_var.get() else "Hold LMB to Fire"
            self.status_sub.config(text=f"Press [{hk}] to disable | {ads_text}")

    def _update_telemetry_display(self, calib_res=None):
        if calib_res:
            self._last_calib_res = calib_res
        pat = self.engine.pattern or []
        self.lbl_telemetry_shots.config(text=f"Loaded Pattern: {len(pat)} shots active")
        if self._last_calib_res:
            vm = self._last_calib_res.get("vert_mult", 1.0)
            hm = self._last_calib_res.get("horiz_mult", 1.0)
            sync = self._last_calib_res.get("match_percent", 100)
            self.lbl_telemetry_ratios.config(text=f"Compression: Vert ×{vm:.2f} | Horiz ×{hm:.2f} ({sync}% Sync)")
            steady = self._last_calib_res.get("steady_state", (0.0, 0.0))
            self.lbl_telemetry_steady.config(text=f"Steady-State Drift: dx = {steady[0]:+.2f}, dy = {steady[1]:+.2f}")
        elif pat:
            tail = pat[-min(3, len(pat)):]
            steady_dx = sum(d[0] for d in tail) / len(tail)
            steady_dy = sum(d[1] for d in tail) / len(tail)
            self.lbl_telemetry_steady.config(text=f"Steady-State Drift: dx = {steady_dx:+.2f}, dy = {steady_dy:+.2f}")

    def _on_preset_selected(self, event=None):
        name = self.preset_var.get()
        if name in self.presets:
            self._load_preset_to_ui(name)
            save_config({"active_preset": name})
            self.footer_lbl.config(text=f"Loaded preset: {name}")

    def _on_hotkey_changed(self, event=None):
        self._sync_engine_from_ui()
        self._update_hotkey_display()
        self.footer_lbl.config(text=f"Hotkey set to [{self.hotkey_var.get()}]")

    def _copy_build_code(self):
        code = self.build_code_var.get().strip()
        if code:
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.root.update()
            self.btn_copy_code.config(text="Copied!")
            self.root.after(1200, lambda: self.btn_copy_code.config(text="Copy"))
            self.footer_lbl.config(text="Build code copied to clipboard")
        else:
            self.footer_lbl.config(text="No build code to copy")

    def _new_preset_action(self):
        name = simpledialog.askstring("New Preset", "Enter preset name:", parent=self.root)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in self.presets:
            messagebox.showinfo("Preset Exists", f"Preset '{name}' already exists.", parent=self.root)
            self.preset_combo.set(name)
            self._on_preset_selected()
            return
        self.presets[name] = self._get_ui_preset_data()
        save_presets(self.presets)
        self._refresh_preset_list(select_name=name)
        self._load_preset_to_ui(name)
        save_config({"active_preset": name})
        self.footer_lbl.config(text=f"Created preset '{name}'")

    def _delete_preset_action(self):
        name = self.preset_var.get()
        if name not in self.presets:
            return
        if len(self.presets) <= 1:
            messagebox.showwarning("Warning", "Cannot delete the only remaining preset.", parent=self.root)
            return
        if messagebox.askyesno("Delete Preset", f"Delete preset '{name}'?", parent=self.root):
            self.presets.pop(name, None)
            save_presets(self.presets)
            next_name = next(iter(self.presets)) if self.presets else "AUG"
            self._refresh_preset_list(select_name=next_name)
            self._load_preset_to_ui(next_name)
            save_config({"active_preset": next_name})
            self.footer_lbl.config(text=f"Deleted preset '{name}'")

    def _save_preset_action(self):
        name = self.preset_var.get().strip()
        if not name:
            return
        self.presets[name] = self._get_ui_preset_data()
        if save_presets(self.presets):
            save_config({"active_preset": name})
            self.footer_lbl.config(text=f"Saved preset '{name}'")
        else:
            self.footer_lbl.config(text="Error saving preset.")

    def _reset_defaults_action(self):
        name = self.preset_var.get()
        if name in DEFAULT_PRESETS:
            self.presets[name] = json.loads(json.dumps(DEFAULT_PRESETS[name]))
        else:
            fallback = next(iter(DEFAULT_PRESETS))
            self.presets[name] = json.loads(json.dumps(DEFAULT_PRESETS[fallback]))
        self._load_preset_to_ui(name)
        save_presets(self.presets)
        self.footer_lbl.config(text=f"Reset '{name}' to defaults.")

    def _reload_all_action(self):
        self.presets = load_presets()
        self.config = load_config()
        self.engine.pattern = load_pattern()
        name = self.config.get("active_preset", "AUG")
        if name not in self.presets:
            name = next(iter(self.presets)) if self.presets else "AUG"
        self._refresh_preset_list(select_name=name)
        self._load_preset_to_ui(name)
        self._update_telemetry_display()
        self.footer_lbl.config(text="Reloaded presets and pattern from disk.")

    def _on_engine_state_change(self, is_enabled: bool):
        self.root.after(0, self._update_ui_state, is_enabled)

    def _update_ui_state(self, is_enabled: bool):
        try:
            hk = self.hotkey_var.get()
            if is_enabled:
                self.toggle_frame.config(bg=self.ACTIVE_BG, highlightbackground=self.ACTIVE_GREEN)
                self.status_title.config(text="Active (Enabled)", bg=self.ACTIVE_BG, fg="#FFFFFF")
                ads_text = "Aim (Hold RMB) + Fire (LMB)" if self.ads_var.get() else "Hold LMB to Fire"
                self.status_sub.config(text=f"Press [{hk}] to disable | {ads_text}", bg=self.ACTIVE_BG, fg="#A7F3D0")
                self.footer_lbl.config(text="Recoil compensation active")
            else:
                self.toggle_frame.config(bg=self.INACTIVE_BG, highlightbackground=self.INACTIVE_RED)
                self.status_title.config(text="Standby (Disabled)", bg=self.INACTIVE_BG, fg="#FFFFFF")
                self.status_sub.config(text=f"Press [{hk}] or click banner to enable", bg=self.INACTIVE_BG, fg="#FECACA")
                self.footer_lbl.config(text="Ready")
        except Exception:
            pass

    def _select_screenshot(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
        if path:
            self._calib_img_path = path
            self._calib_img_pil = None
            self.footer_lbl.config(text=f"Selected: {os.path.basename(path)}")

    def _paste_screenshot(self):
        from PIL import ImageGrab
        img = ImageGrab.grabclipboard()
        if img:
            self._calib_img_pil = img
            self._calib_img_path = None
            self.footer_lbl.config(text="Image pasted from clipboard")

    def _run_calibration(self):
        from extractor import calibrate_from_image
        try:
            rpm = float(self.rpm_var.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid RPM. Please enter a valid number (e.g. 679).", parent=self.root)
            return

        img_src = getattr(self, "_calib_img_path", None) or getattr(self, "_calib_img_pil", None)
        if not img_src:
            messagebox.showerror("Error", "No image selected. Please click 'Select Screenshot' or 'Paste Screenshot'.", parent=self.root)
            return

        try:
            res = calibrate_from_image(img_src, rpm=rpm)
            if not res.get("success", False):
                messagebox.showerror("Error", res.get("error", "Calibration failed"), parent=self.root)
                return

            self._last_calib_res = res
            MachineVisionPopup(self.root, res, rpm, self._apply_calibration)
        except Exception as e:
            messagebox.showerror("Error", f"Calibration error: {str(e)}", parent=self.root)

    def _open_vision_popup(self):
        if not self._last_calib_res:
            if getattr(self, "_calib_img_path", None) or getattr(self, "_calib_img_pil", None):
                self._run_calibration()
                return
            messagebox.showinfo("Vision Cross-Validation", "No calibration has been run yet. Please select/paste a screenshot and run calibration first.", parent=self.root)
            return
        try:
            rpm = float(self.rpm_var.get())
        except ValueError:
            rpm = 679.0
        MachineVisionPopup(self.root, self._last_calib_res, rpm, self._apply_calibration)

    def _apply_calibration(self, green_dots, grey_dots, rpm_val, vert_mult, horiz_mult, calib_res=None):
        from extractor import calculate_kick_parameters, calculate_fire_delay, generate_calibrated_pattern

        delay_ms = calculate_fire_delay(rpm_val)
        ref_dots = green_dots if len(green_dots) >= 2 else grey_dots
        kick_params = calculate_kick_parameters(ref_dots)

        self.var_delay.set(delay_ms)
        self.rpm_var.set(str(int(rpm_val)))
        self.var_v_scale.set(kick_params["vertical_scale"])
        self.var_h_scale.set(kick_params["horizontal_scale"])
        self.var_kick_mult.set(kick_params["initial_kick_mult"])
        self.var_kick_decay.set(kick_params["kick_decay_shots"])

        if calib_res and calib_res.get("pattern"):
            pat = calib_res["pattern"]
        else:
            pat, _ = generate_calibrated_pattern(
                grey_dots, green_dots,
                v_ratio=vert_mult, h_ratio=horiz_mult,
                initial_kick_mult=kick_params["initial_kick_mult"],
                kick_decay_shots=kick_params["kick_decay_shots"]
            )

        if pat:
            self.engine.pattern = pat
            try:
                pattern_data = {
                    "description": "Delta Force Recoil Profile (Calibrated)",
                    "gun": self.preset_var.get(),
                    "game": "Delta Force",
                    "magazine_size": len(pat),
                    "base_fire_delay_ms": delay_ms,
                    "shots": [{"bullet": i + 1, "dx": round(dx, 2), "dy": round(dy, 2)} for i, (dx, dy) in enumerate(pat)]
                }
                tmp_pattern = PATTERN_FILE + ".tmp"
                with open(tmp_pattern, "w", encoding="utf-8") as f:
                    json.dump(pattern_data, f, indent=2)
                os.replace(tmp_pattern, PATTERN_FILE)
            except Exception:
                pass

        self._sync_engine_from_ui()

        self.lbl_v_val.config(text=f"{self.var_v_scale.get():.2f}x")
        self.lbl_h_val.config(text=f"{self.var_h_scale.get():.2f}x")
        self.lbl_kick_mult_val.config(text=f"{self.var_kick_mult.get():.2f}x")
        self.lbl_kick_decay_val.config(text=f"{self.var_kick_decay.get()} shots")
        self.lbl_delay_val.config(text=f"{self.var_delay.get()} ms")

        badge_text = calib_res.get("badge_text", f"Calibrated @ {int(rpm_val)} RPM") if calib_res else f"Calibrated @ {int(rpm_val)} RPM"
        self.calib_badge.config(text=badge_text)
        self._update_telemetry_display(calib_res)
        self.footer_lbl.config(text="Calibration successfully applied to engine & pattern")

    def _on_close(self):
        try:
            self._save_preset_action()
        except Exception:
            pass
        self.engine.shutdown()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = DFRecoilApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
