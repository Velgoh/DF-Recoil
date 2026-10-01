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
from typing import List, Tuple, Dict, Any

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
    "AUG (Laser Build)": {
        "build_code": "AUG Assault Rifle-Warfare-6LFHGS4073PHD3H80H3R3",
        "vertical_scale": 4.20,
        "horizontal_scale": 3.85,
        "initial_kick_mult": 2.20,
        "kick_decay_shots": 6,
        "bullet_delay_ms": 133,
        "micro_steps": 10,
        "jitter": 0.35,
        "hotkey": "F6",
        "require_ads": False
    },
    "M4A1 (Standard)": {
        "build_code": "M4A1 Assault Rifle-Warfare-5H9Q3L4089LKJ1A20K9P1",
        "vertical_scale": 3.40,
        "horizontal_scale": 1.80,
        "initial_kick_mult": 1.75,
        "kick_decay_shots": 5,
        "bullet_delay_ms": 75,
        "micro_steps": 10,
        "jitter": 0.30,
        "hotkey": "F6",
        "require_ads": False
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
                    return data
        except Exception:
            pass
    presets = json.loads(json.dumps(DEFAULT_PRESETS))
    save_presets(presets)
    return presets


def save_presets(presets: Dict[str, Dict[str, Any]]) -> bool:
    try:
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2)
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
    return {"active_preset": "AUG (Laser Build)"}


def save_config(cfg: Dict[str, Any]) -> bool:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception:
        return False


def precise_sleep_until(target_perf_time: float) -> None:
    while True:
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
        self.vertical_scale = 4.20
        self.horizontal_scale = 3.85
        self.initial_kick_mult = 2.20
        self.kick_decay_shots = 6
        self.bullet_delay_ms = 133
        self.micro_steps = 10
        self.jitter = 0.35
        self.hotkey_name = "F6"
        self.require_ads = False

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

    def update_params(self, v_scale, h_scale, kick_mult, kick_decay, delay_ms, steps, jitter, hotkey, require_ads):
        self.vertical_scale = float(v_scale)
        self.horizontal_scale = float(h_scale)
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

                if bullet_idx < len(self.pattern):
                    target_dx, target_dy = self.pattern[bullet_idx]
                else:
                    target_dx, target_dy = self.pattern[-1]

                kick_boost = self.get_kick_boost(bullet_idx)
                shot_dx = target_dx * self.horizontal_scale
                shot_dy = target_dy * self.vertical_scale * kick_boost

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
                    precise_sleep_until(step_deadline)

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


class DFRecoilApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Delta Force // Recoil Compensator")
        self.root.geometry("540x890")
        self.root.minsize(490, 780)
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

        self.root.update_idletasks()
        try:
            self.hwnd = user32.GetAncestor(self.root.winfo_id(), 2)
            self.engine.set_gui_hwnd(self.hwnd)
        except Exception:
            self.hwnd = None

        self._build_ui()

        active_preset = self.config.get("active_preset", "AUG (Laser Build)")
        if active_preset not in self.presets:
            active_preset = next(iter(self.presets)) if self.presets else "AUG (Laser Build)"
        self._refresh_preset_list(select_name=active_preset)
        self._load_preset_to_ui(active_preset)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=self.BG_COLOR)
        header.pack(fill="x", padx=24, pady=(14, 6))

        title_lbl = tk.Label(
            header,
            text="DELTA FORCE // RECOIL",
            font=("Segoe UI", 16, "bold"),
            fg=self.ACCENT_CYAN,
            bg=self.BG_COLOR
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            header,
            text="Universal Recoil Profile & Pattern Manager",
            font=("Segoe UI", 9),
            fg=self.TEXT_MUTED,
            bg=self.BG_COLOR
        )
        sub_lbl.pack(anchor="w", pady=(1, 0))

        # Status Banner
        self.toggle_frame = tk.Frame(
            self.root,
            bg=self.INACTIVE_BG,
            highlightbackground=self.INACTIVE_RED,
            highlightthickness=2,
            cursor="hand2"
        )
        self.toggle_frame.pack(fill="x", padx=24, pady=6)
        self.toggle_frame.bind("<Button-1>", lambda e: self.engine.toggle())

        self.status_title = tk.Label(
            self.toggle_frame,
            text="● STANDBY // DISABLED",
            font=("Segoe UI", 14, "bold"),
            fg="#FFFFFF",
            bg=self.INACTIVE_BG,
            cursor="hand2"
        )
        self.status_title.pack(pady=(8, 2))
        self.status_title.bind("<Button-1>", lambda e: self.engine.toggle())

        self.status_sub = tk.Label(
            self.toggle_frame,
            text="Press [F6] or click to ENABLE",
            font=("Segoe UI", 9, "bold"),
            fg="#FECACA",
            bg=self.INACTIVE_BG,
            cursor="hand2"
        )
        self.status_sub.pack(pady=(0, 8))
        self.status_sub.bind("<Button-1>", lambda e: self.engine.toggle())

        # Presets & Build Code Card
        preset_card = tk.Frame(
            self.root,
            bg=self.CARD_BG,
            highlightbackground=self.CARD_BORDER,
            highlightthickness=1
        )
        preset_card.pack(fill="x", padx=24, pady=4)

        # Row 1: Preset selector, New, Delete
        p_row1 = tk.Frame(preset_card, bg=self.CARD_BG)
        p_row1.pack(fill="x", padx=12, pady=(8, 4))

        tk.Label(
            p_row1,
            text="Preset:",
            font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_MAIN,
            bg=self.CARD_BG
        ).pack(side="left")

        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(
            p_row1,
            textvariable=self.preset_var,
            state="readonly",
            width=22
        )
        self.preset_combo.pack(side="left", padx=(8, 10))
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)

        btn_new = tk.Button(
            p_row1,
            text="+ New",
            font=("Segoe UI", 8, "bold"),
            fg=self.ACTIVE_GREEN,
            bg=self.BTN_NORMAL,
            activebackground=self.BTN_HOVER,
            activeforeground=self.ACTIVE_GREEN,
            relief="flat",
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._new_preset_action
        )
        btn_new.pack(side="left", padx=2)

        btn_del = tk.Button(
            p_row1,
            text="Delete",
            font=("Segoe UI", 8, "bold"),
            fg=self.INACTIVE_RED,
            bg=self.BTN_NORMAL,
            activebackground=self.BTN_HOVER,
            activeforeground=self.INACTIVE_RED,
            relief="flat",
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._delete_preset_action
        )
        btn_del.pack(side="left", padx=2)

        # Row 2: Build Code entry & Copy button
        p_row2 = tk.Frame(preset_card, bg=self.CARD_BG)
        p_row2.pack(fill="x", padx=12, pady=(4, 8))

        tk.Label(
            p_row2,
            text="Build Code:",
            font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_MAIN,
            bg=self.CARD_BG
        ).pack(side="left")

        self.build_code_var = tk.StringVar()
        self.build_code_entry = tk.Entry(
            p_row2,
            textvariable=self.build_code_var,
            font=("Consolas", 8),
            bg="#0D1117",
            fg=self.ACCENT_CYAN,
            insertbackground="#FFFFFF",
            relief="flat",
            highlightbackground=self.CARD_BORDER,
            highlightcolor=self.ACCENT_CYAN,
            highlightthickness=1
        )
        self.build_code_entry.pack(side="left", fill="x", expand=True, padx=(8, 6))

        self.btn_copy_code = tk.Button(
            p_row2,
            text="Copy",
            font=("Segoe UI", 8, "bold"),
            fg=self.TEXT_MAIN,
            bg=self.BTN_NORMAL,
            activebackground=self.BTN_HOVER,
            activeforeground=self.ACCENT_CYAN,
            relief="flat",
            bd=0,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._copy_build_code
        )
        self.btn_copy_code.pack(side="right")

        # Sliders Section Card
        sliders_card = tk.Frame(
            self.root,
            bg=self.CARD_BG,
            highlightbackground=self.CARD_BORDER,
            highlightthickness=1
        )
        sliders_card.pack(fill="x", padx=24, pady=4)

        self.var_v_scale = tk.DoubleVar(value=4.20)
        self.lbl_v_val = self._create_slider_row(
            sliders_card, "Vertical Recoil Scale", "Pull-down compensation multiplier",
            self.var_v_scale, 0.1, 6.0, 0.01, "{:.2f}x"
        )

        self.var_h_scale = tk.DoubleVar(value=3.85)
        self.lbl_h_val = self._create_slider_row(
            sliders_card, "Horizontal Recoil Scale", "Horizontal drift compensation multiplier",
            self.var_h_scale, 0.1, 6.0, 0.01, "{:.2f}x"
        )

        self.var_kick_mult = tk.DoubleVar(value=2.20)
        self.lbl_kick_mult_val = self._create_slider_row(
            sliders_card, "Initial Kick Multiplier", "First-shot kick multiplier",
            self.var_kick_mult, 1.0, 4.0, 0.05, "{:.2f}x"
        )

        self.var_kick_decay = tk.IntVar(value=6)
        self.lbl_kick_decay_val = self._create_slider_row(
            sliders_card, "Kick Decay (Shots)", "Initial shot decay window",
            self.var_kick_decay, 1, 15, 1, "{} shots"
        )

        self.var_delay = tk.IntVar(value=133)
        self.lbl_delay_val = self._create_slider_row(
            sliders_card, "Bullet Fire Delay (ms)", "Timing interval between shots",
            self.var_delay, 40, 200, 1, "{} ms"
        )

        self.var_steps = tk.IntVar(value=10)
        self.lbl_steps_val = self._create_slider_row(
            sliders_card, "Smoothing Micro-Steps", "Subdivision steps per bullet interval",
            self.var_steps, 4, 25, 1, "{} steps"
        )

        self.var_jitter = tk.DoubleVar(value=0.35)
        self.lbl_jitter_val = self._create_slider_row(
            sliders_card, "Randomness / Jitter", "Micro-variance to humanize input",
            self.var_jitter, 0.0, 1.5, 0.01, "±{:.2f} px"
        )

        # Options Card
        opts_card = tk.Frame(
            self.root,
            bg=self.CARD_BG,
            highlightbackground=self.CARD_BORDER,
            highlightthickness=1
        )
        opts_card.pack(fill="x", padx=24, pady=4)

        opts_inner = tk.Frame(opts_card, bg=self.CARD_BG)
        opts_inner.pack(fill="x", padx=12, pady=6)

        tk.Label(
            opts_inner,
            text="Toggle Hotkey:",
            font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_MAIN,
            bg=self.CARD_BG
        ).pack(side="left")

        self.hotkey_var = tk.StringVar(value="F6")
        self.hk_combo = ttk.Combobox(
            opts_inner,
            textvariable=self.hotkey_var,
            values=list(HOTKEY_MAP.keys()),
            state="readonly",
            width=12
        )
        self.hk_combo.pack(side="left", padx=(8, 20))
        self.hk_combo.bind("<<ComboboxSelected>>", self._on_hotkey_changed)

        self.ads_var = tk.BooleanVar(value=False)
        self.ads_chk = tk.Checkbutton(
            opts_inner,
            text="Require ADS (Hold RMB)",
            variable=self.ads_var,
            font=("Segoe UI", 9),
            fg=self.TEXT_MAIN,
            bg=self.CARD_BG,
            activebackground=self.CARD_BG,
            activeforeground=self.ACCENT_CYAN,
            selectcolor=self.BG_COLOR,
            command=self._sync_engine_from_ui
        )
        self.ads_chk.pack(side="right")

        # Action Buttons
        btn_frame = tk.Frame(self.root, bg=self.BG_COLOR)
        btn_frame.pack(fill="x", padx=24, pady=8)

        def make_action_btn(parent, text, cmd, fg_color):
            btn = tk.Button(
                parent,
                text=text,
                font=("Segoe UI", 9, "bold"),
                fg=fg_color,
                bg=self.BTN_NORMAL,
                activebackground=self.BTN_HOVER,
                activeforeground=fg_color,
                relief="flat",
                bd=0,
                padx=12,
                pady=6,
                cursor="hand2",
                command=cmd
            )
            btn.pack(side="left", expand=True, fill="x", padx=4)
            return btn

        make_action_btn(btn_frame, "Save Preset", self._save_preset_action, self.ACTIVE_GREEN)
        make_action_btn(btn_frame, "Reset Defaults", self._reset_defaults_action, self.ACCENT_GOLD)
        make_action_btn(btn_frame, "Reload All", self._reload_all_action, self.ACCENT_CYAN)

        # Status Footer
        self.footer_lbl = tk.Label(
            self.root,
            text="Ready",
            font=("Segoe UI", 8),
            fg=self.TEXT_MUTED,
            bg=self.BG_COLOR
        )
        self.footer_lbl.pack(side="bottom", pady=(0, 6))

    def _create_slider_row(self, parent, title, subtext, variable, from_, to, resolution, val_format):
        container = tk.Frame(parent, bg=self.CARD_BG)
        container.pack(fill="x", padx=12, pady=2)

        hdr = tk.Frame(container, bg=self.CARD_BG)
        hdr.pack(fill="x")

        tk.Label(
            hdr,
            text=title,
            font=("Segoe UI", 9, "bold"),
            fg=self.TEXT_MAIN,
            bg=self.CARD_BG
        ).pack(side="left")

        val_lbl = tk.Label(
            hdr,
            text=val_format.format(variable.get()),
            font=("Segoe UI", 9, "bold"),
            fg=self.ACCENT_CYAN,
            bg=self.CARD_BG
        )
        val_lbl.pack(side="right")

        tk.Label(
            container,
            text=subtext,
            font=("Segoe UI", 8),
            fg=self.TEXT_MUTED,
            bg=self.CARD_BG
        ).pack(anchor="w")

        def on_slider_move(val):
            try:
                raw_val = float(val)
                if resolution >= 1.0:
                    snapped = round(raw_val / resolution) * resolution
                    variable.set(int(snapped))
                else:
                    decimals = max(0, -int(math.floor(math.log10(resolution))))
                    snapped = round(raw_val, decimals)
                    variable.set(snapped)
            except Exception:
                pass
            val_lbl.config(text=val_format.format(variable.get()))
            self._sync_engine_from_ui()

        scale = ttk.Scale(
            container,
            from_=from_,
            to=to,
            variable=variable,
            command=on_slider_move
        )
        scale.pack(fill="x", pady=(1, 2))
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

        self.var_v_scale.set(float(preset.get("vertical_scale", 4.20)))
        self.var_h_scale.set(float(preset.get("horizontal_scale", 3.85)))
        self.var_kick_mult.set(float(preset.get("initial_kick_mult", 2.20)))
        self.var_kick_decay.set(int(preset.get("kick_decay_shots", 6)))
        self.var_delay.set(int(preset.get("bullet_delay_ms", 133)))
        self.var_steps.set(int(preset.get("micro_steps", 10)))
        self.var_jitter.set(float(preset.get("jitter", 0.35)))
        self.hotkey_var.set(str(preset.get("hotkey", "F6")))
        self.ads_var.set(bool(preset.get("require_ads", False)))

        self.lbl_v_val.config(text=f"{self.var_v_scale.get():.2f}x")
        self.lbl_h_val.config(text=f"{self.var_h_scale.get():.2f}x")
        self.lbl_kick_mult_val.config(text=f"{self.var_kick_mult.get():.2f}x")
        self.lbl_kick_decay_val.config(text=f"{self.var_kick_decay.get()} shots")
        self.lbl_delay_val.config(text=f"{self.var_delay.get()} ms")
        self.lbl_steps_val.config(text=f"{self.var_steps.get()} steps")
        self.lbl_jitter_val.config(text=f"±{self.var_jitter.get():.2f} px")

        self._sync_engine_from_ui()
        self._update_hotkey_display()

    def _get_ui_preset_data(self) -> Dict[str, Any]:
        return {
            "build_code": self.build_code_var.get().strip(),
            "vertical_scale": round(self.var_v_scale.get(), 2),
            "horizontal_scale": round(self.var_h_scale.get(), 2),
            "initial_kick_mult": round(self.var_kick_mult.get(), 2),
            "kick_decay_shots": int(self.var_kick_decay.get()),
            "bullet_delay_ms": int(self.var_delay.get()),
            "micro_steps": int(self.var_steps.get()),
            "jitter": round(self.var_jitter.get(), 2),
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
            require_ads=self.ads_var.get()
        )

    def _update_hotkey_display(self):
        hk = self.hotkey_var.get()
        if not self.engine.enabled:
            self.status_sub.config(text=f"Press [{hk}] or click to ENABLE")
        else:
            self.status_sub.config(text=f"Press [{hk}] to DISABLE | Hold LMB to Fire")

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
            self.btn_copy_code.config(text="Copied!")
            self.root.after(1200, lambda: self.btn_copy_code.config(text="Copy"))
            self.footer_lbl.config(text="Build code copied to clipboard")

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
        save_config({"active_preset": name})
        self.footer_lbl.config(text=f"Created preset '{name}'")

    def _delete_preset_action(self):
        name = self.preset_var.get()
        if len(self.presets) <= 1:
            messagebox.showwarning("Warning", "Cannot delete the only remaining preset.", parent=self.root)
            return
        if messagebox.askyesno("Delete Preset", f"Delete preset '{name}'?", parent=self.root):
            del self.presets[name]
            save_presets(self.presets)
            next_name = next(iter(self.presets))
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
            self.presets[name] = json.loads(json.dumps(DEFAULT_PRESETS["AUG (Laser Build)"]))
        self._load_preset_to_ui(name)
        save_presets(self.presets)
        self.footer_lbl.config(text=f"Reset '{name}' to defaults.")

    def _reload_all_action(self):
        self.presets = load_presets()
        self.config = load_config()
        self.engine.pattern = load_pattern()
        name = self.config.get("active_preset", "AUG (Laser Build)")
        if name not in self.presets:
            name = next(iter(self.presets)) if self.presets else "AUG (Laser Build)"
        self._refresh_preset_list(select_name=name)
        self._load_preset_to_ui(name)
        self.footer_lbl.config(text="Reloaded presets and pattern from disk.")

    def _on_engine_state_change(self, is_enabled: bool):
        self.root.after(0, self._update_ui_state, is_enabled)

    def _update_ui_state(self, is_enabled: bool):
        try:
            hk = self.hotkey_var.get()
            if is_enabled:
                self.toggle_frame.config(bg=self.ACTIVE_BG, highlightbackground=self.ACTIVE_GREEN)
                self.status_title.config(text="● ACTIVE // RUNNING", bg=self.ACTIVE_BG, fg="#FFFFFF")
                self.status_sub.config(text=f"Press [{hk}] to DISABLE | Hold LMB to Fire", bg=self.ACTIVE_BG, fg="#A7F3D0")
                self.footer_lbl.config(text="Recoil Compensation ACTIVE")
            else:
                self.toggle_frame.config(bg=self.INACTIVE_BG, highlightbackground=self.INACTIVE_RED)
                self.status_title.config(text="● STANDBY // DISABLED", bg=self.INACTIVE_BG, fg="#FFFFFF")
                self.status_sub.config(text=f"Press [{hk}] or click to ENABLE", bg=self.INACTIVE_BG, fg="#FECACA")
                self.footer_lbl.config(text="Recoil Compensation STANDBY")
        except Exception:
            pass

    def _on_close(self):
        self.engine.shutdown()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = DFRecoilApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
