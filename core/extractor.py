import os
import cv2
import numpy as np
import re
from PIL import Image
from typing import List, Tuple, Dict, Any, Union, Optional


def load_image_to_bgr(image_input: Union[str, os.PathLike, Image.Image, np.ndarray]) -> np.ndarray:
    """
    Loads any image format (file path, PIL Image, or numpy array) into a BGR numpy array.
    """
    if isinstance(image_input, (str, os.PathLike)):
        path_str = str(image_input)
        if not os.path.exists(path_str):
            raise FileNotFoundError(f"Image file does not exist: {path_str}")
        img = cv2.imread(path_str)
        if img is None:
            raise ValueError(f"Failed to decode image from path: {path_str}")
        return img
    elif isinstance(image_input, Image.Image):
        rgb_arr = np.array(image_input.convert("RGB"))
        return cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)
    elif isinstance(image_input, np.ndarray):
        if image_input.ndim == 3 and image_input.shape[2] == 4:
            return cv2.cvtColor(image_input, cv2.COLOR_BGRA2BGR)
        elif image_input.ndim == 3 and image_input.shape[2] == 3:
            return image_input.copy()
        elif image_input.ndim == 2:
            return cv2.cvtColor(image_input, cv2.COLOR_GRAY2BGR)
        else:
            raise ValueError(f"Unsupported numpy image shape: {image_input.shape}")
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")


def calculate_fire_delay(rpm: Union[int, float]) -> int:
    """
    Calculates the millisecond delay between bullet shots based on gun RPM.
    60,000 ms / RPM, clamped to [20, 1000].
    """
    try:
        val = float(rpm)
        if val <= 0:
            return 88
        delay = round(60000.0 / val)
        return max(20, min(1000, int(delay)))
    except Exception:
        return 88


def extract_dual_dots_from_image(
    image_input: Union[str, os.PathLike, Image.Image, np.ndarray]
) -> Dict[str, Any]:
    """
    Crops the mannequin recoil display and detects:
    1. Base Control trajectory dots (grey dots on the left silhouette)
    2. Modified Loadout trajectory dots (green dots on the right silhouette)
    Uses multi-scale morphological top-hat, adaptive contrast/thresholding,
    and background isolation to reliably detect faint and close dots.
    """
    img = load_image_to_bgr(image_input)
    h, w = img.shape[:2]
    if h < 60 or w < 60:
        return {
            "success": False,
            "error": "Image resolution is too small.",
            "grey_dots": [],
            "green_dots": [],
            "crop_bgr": None,
            "crop_offset": (0, 0),
            "match_percent": 0
        }

    # Focus on the mannequin panel region
    roi_top = int(h * 0.15)
    roi_bottom = int(h * 0.86)
    roi_left = int(w * 0.56)
    roi_right = int(w * 0.94)

    crop_both = img[roi_top:roi_bottom, roi_left:roi_right].copy()
    ch, cw = crop_both.shape[:2]

    split_x = int(cw * 0.48)
    crop_l = crop_both[:, :split_x]
    crop_r = crop_both[:, split_x:]

    # Morphological kernels for multi-scale dot detection
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    k11 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))

    # --- LEFT HALF: GREY BASE DOTS ---
    gray_l = cv2.cvtColor(crop_l, cv2.COLOR_BGR2GRAY)
    hsv_l = cv2.cvtColor(crop_l, cv2.COLOR_BGR2HSV)

    # Multi-scale top-hat captures both small sharp dots and wider/faint dots
    th5 = cv2.morphologyEx(gray_l, cv2.MORPH_TOPHAT, k5)
    th7 = cv2.morphologyEx(gray_l, cv2.MORPH_TOPHAT, k7)
    th11 = cv2.morphologyEx(gray_l, cv2.MORPH_TOPHAT, k11)
    th_l = np.maximum(np.maximum(th5, th7), th11)

    # Mask out green UI elements or high-saturation colors on left
    green_mask_l = (hsv_l[:, :, 0] >= 35) & (hsv_l[:, :, 0] <= 95) & (hsv_l[:, :, 1] > 50)
    th_l[green_mask_l] = 0

    blurred_l = cv2.GaussianBlur(th_l.astype(float), (3, 3), 0.8)
    dil_l = cv2.dilate(blurred_l, np.ones((3, 3), np.uint8))
    # Threshold at 7.0 ensures faint top and head-adjacent dots are preserved
    peaks_l = (blurred_l == dil_l) & (blurred_l >= 7.0)
    peaks_l[:3, :] = False; peaks_l[-3:, :] = False
    peaks_l[:, :3] = False; peaks_l[:, -3:] = False
    py_l, px_l = np.where(peaks_l)

    cands_l = sorted([(x, y, blurred_l[y, x]) for x, y in zip(px_l, py_l)], key=lambda c: -c[2])
    grey_crop_dots: List[Tuple[float, float]] = []
    for x, y, score in cands_l:
        if not any(np.hypot(x - cx, y - cy) < 4.8 for cx, cy in grey_crop_dots):
            grey_crop_dots.append((float(x), float(y)))

    # Sort from bottom (first shot) to top (last shot)
    grey_crop_dots.sort(key=lambda d: -d[1])
    if grey_crop_dots:
        med_x_l = float(np.median([d[0] for d in grey_crop_dots]))
        grey_crop_dots = [d for d in grey_crop_dots if abs(d[0] - med_x_l) < 60]

    # --- RIGHT HALF: GREEN LOADOUT DOTS ---
    b_r, g_r, r_r = cv2.split(crop_r)
    g_signal = np.clip(g_r.astype(int) - ((r_r.astype(int) + b_r.astype(int)) // 2), 0, 255).astype(np.uint8)
    hsv_r = cv2.cvtColor(crop_r, cv2.COLOR_BGR2HSV)
    g_mask = (
        (hsv_r[:, :, 0] >= 30) & (hsv_r[:, :, 0] <= 100) &
        (hsv_r[:, :, 1] >= 25) & (hsv_r[:, :, 2] >= 25) &
        (g_r.astype(int) > r_r.astype(int) + 8)
    )
    g_signal = np.where(g_mask, g_signal, 0)

    g_th5 = cv2.morphologyEx(g_signal, cv2.MORPH_TOPHAT, k5)
    g_th11 = cv2.morphologyEx(g_signal, cv2.MORPH_TOPHAT, k11)
    g_th = np.maximum(np.maximum(g_signal, g_th5), g_th11)

    blurred_g = cv2.GaussianBlur(g_th.astype(float), (3, 3), 0.8)
    dil_g = cv2.dilate(blurred_g, np.ones((3, 3), np.uint8))
    peaks_g = (blurred_g == dil_g) & (blurred_g >= 7.0)
    peaks_g[:3, :] = False; peaks_g[-3:, :] = False
    peaks_g[:, :3] = False; peaks_g[:, -3:] = False
    py_g, px_g = np.where(peaks_g)

    cands_g = sorted([(x, y, blurred_g[y, x]) for x, y in zip(px_g, py_g)], key=lambda c: -c[2])
    green_crop_dots: List[Tuple[float, float]] = []
    for x, y, score in cands_g:
        cx = float(x + split_x)
        cy = float(y)
        if not any(np.hypot(cx - gx, cy - gy) < 4.8 for gx, gy in green_crop_dots):
            green_crop_dots.append((cx, cy))

    green_crop_dots.sort(key=lambda d: -d[1])
    if green_crop_dots:
        med_x_r = float(np.median([d[0] for d in green_crop_dots]))
        green_crop_dots = [d for d in green_crop_dots if abs(d[0] - med_x_r) < 60]

    n_grey = len(grey_crop_dots)
    n_green = len(green_crop_dots)
    if n_grey == 0 and n_green == 0:
        match_pct = 0
    elif max(n_grey, n_green) > 0:
        match_pct = round(100.0 * min(n_grey, n_green) / max(n_grey, n_green))
    else:
        match_pct = 100

    return {
        "success": n_green >= 2 or n_grey >= 2,
        "error": None if (n_green >= 2 or n_grey >= 2) else "No recoil dots detected.",
        "grey_dots": grey_crop_dots,
        "green_dots": green_crop_dots,
        "grey_count": n_grey,
        "green_count": n_green,
        "match_percent": match_pct,
        "crop_bgr": crop_both,
        "crop_offset": (roi_left, roi_top)
    }


def ocr_multipliers_from_image(image_bgr: np.ndarray) -> Tuple[float, float]:
    """
    Fallback OCR extractor for multiplier text if present on screen.
    Maintained for backwards compatibility.
    """
    try:
        import pytesseract
        h, w = image_bgr.shape[:2]
        crop = image_bgr[int(h * 0.1):int(h * 0.6), 0:int(w * 0.55)]
        text = pytesseract.image_to_string(crop)
        vert_mult, horiz_mult = 1.0, 1.0
        for line in text.split('\n'):
            line = line.strip()
            if 'Full-Auto Vertical Recoil Multiplier' in line or 'Vertical Recoil Multiplier' in line:
                matches = re.findall(r'(\d+\.\d+)x', line)
                if len(matches) >= 2:
                    vert_mult = float(matches[1])
                elif len(matches) == 1:
                    vert_mult = float(matches[0])
            if 'Full-Auto Horizontal Recoil Multiplier' in line or 'Horizontal Recoil Multiplier' in line:
                matches = re.findall(r'(\d+\.\d+)x', line)
                if len(matches) >= 2:
                    horiz_mult = float(matches[1])
                elif len(matches) == 1:
                    horiz_mult = float(matches[0])
        return float(vert_mult), float(horiz_mult)
    except Exception:
        return 1.0, 1.0


def calculate_compression_ratios(
    grey_dots: List[Tuple[float, float]],
    green_dots: List[Tuple[float, float]]
) -> Tuple[float, float]:
    """
    Matches the grey dots pattern (base trajectory) to the green dots (loadout trajectory)
    as a whole to calculate:
      - Vertical compression ratio: green_height / grey_height
      - Horizontal compression ratio: green_width / grey_width
    Evaluates over common corresponding shots to accurately capture tightness.
    """
    if len(grey_dots) < 2 or len(green_dots) < 2:
        return 1.0, 1.0

    sorted_grey = sorted(grey_dots, key=lambda d: -d[1])
    sorted_green = sorted(green_dots, key=lambda d: -d[1])

    K = min(len(sorted_grey), len(sorted_green))
    sub_grey = sorted_grey[:K]
    sub_green = sorted_green[:K]

    grey_h = max(d[1] for d in sub_grey) - min(d[1] for d in sub_grey)
    green_h = max(d[1] for d in sub_green) - min(d[1] for d in sub_green)
    v_ratio = (green_h / grey_h) if grey_h > 5.0 else 1.0

    grey_w = max(d[0] for d in sub_grey) - min(d[0] for d in sub_grey)
    green_w = max(d[0] for d in sub_green) - min(d[0] for d in sub_green)

    if grey_w > 5.0:
        h_ratio = green_w / grey_w
    elif green_w > 5.0:
        h_ratio = green_w / 20.0
    else:
        h_ratio = 1.0

    v_ratio = round(max(0.10, min(2.50, float(v_ratio))), 2)
    h_ratio = round(max(0.10, min(2.50, float(h_ratio))), 2)

    return v_ratio, h_ratio


def compute_deltas(dots: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if len(dots) < 2:
        return []
    sorted_dots = sorted(dots, key=lambda d: -d[1])
    return [
        (sorted_dots[i][0] - sorted_dots[i + 1][0], sorted_dots[i][1] - sorted_dots[i + 1][1])
        for i in range(len(sorted_dots) - 1)
    ]


def calculate_kick_parameters(dots: List[Tuple[float, float]]) -> Dict[str, Any]:
    """
    Analyzes trajectory dots to compute initial kick multiplier,
    kick decay shots, and base vertical/horizontal scale factors.
    """
    if len(dots) < 2:
        return {
            "initial_kick_mult": 2.20,
            "kick_decay_shots": 6,
            "vertical_scale": 2.70,
            "horizontal_scale": 2.99
        }

    sorted_dots = sorted(dots, key=lambda d: -d[1])
    deltas = []
    for i in range(len(sorted_dots) - 1):
        dx = sorted_dots[i][0] - sorted_dots[i + 1][0]
        dy = sorted_dots[i][1] - sorted_dots[i + 1][1]
        deltas.append((dx, dy))

    tail_sample = deltas[min(4, len(deltas) - 1):]
    steady_dy = float(np.median([d[1] for d in tail_sample])) if tail_sample else 7.5
    if steady_dy <= 0:
        steady_dy = 7.5

    first_dy = float(deltas[0][1]) if deltas else steady_dy
    max_initial_dy = max(first_dy, float(deltas[1][1])) if len(deltas) > 1 else first_dy
    kick_ratio = max_initial_dy / steady_dy
    kick_mult = round(max(1.00, min(4.00, kick_ratio)), 2)

    decay_shots = 6
    for idx, d in enumerate(deltas):
        if idx >= 1 and d[1] <= 1.15 * steady_dy:
            decay_shots = idx + 1
            break
    decay_shots = max(1, min(15, decay_shots))

    all_y = [d[1] for d in sorted_dots]
    all_x = [d[0] for d in sorted_dots]
    spread_h = max(all_y) - min(all_y)
    spread_w = max(all_x) - min(all_x)

    ref_h = 222.0
    ref_w = 40.0
    v_scale = round(max(0.50, min(6.00, 2.70 * (spread_h / ref_h))), 2) if spread_h > 10 else 2.70
    h_scale = round(max(0.50, min(6.00, 2.99 * (spread_w / ref_w))), 2) if spread_w > 5 else 2.99

    return {
        "initial_kick_mult": kick_mult,
        "kick_decay_shots": decay_shots,
        "vertical_scale": v_scale,
        "horizontal_scale": h_scale
    }


def generate_calibrated_pattern(
    grey_dots: List[Tuple[float, float]],
    green_dots: List[Tuple[float, float]],
    v_ratio: float = 1.0,
    h_ratio: float = 1.0,
    max_shots: int = 65,
    initial_kick_mult: float = 1.0,
    kick_decay_shots: int = 1
) -> Tuple[List[Tuple[float, float]], Tuple[float, float]]:
    """
    Generates a full 60-65 shot recoil compensation pattern by:
    1. Scaling the base trajectory shape (grey dots) by the measured compression ratios (v_ratio, h_ratio)
    2. Incorporating green dot extensions if the loadout provided additional data points
    3. Normalizing initial kick to avoid double-amplification with runtime kick_boost
    4. Extrapolating the steady-state tail to cover full magazine size
    """
    sorted_grey = sorted(grey_dots, key=lambda d: -d[1]) if grey_dots else []
    sorted_green = sorted(green_dots, key=lambda d: -d[1]) if green_dots else []

    deltas: List[Tuple[float, float]] = []

    if len(sorted_grey) >= 2:
        for i in range(len(sorted_grey) - 1):
            dx = (sorted_grey[i][0] - sorted_grey[i + 1][0]) * h_ratio
            dy = (sorted_grey[i][1] - sorted_grey[i + 1][1]) * v_ratio
            if initial_kick_mult > 1.0 and kick_decay_shots > 0 and i < kick_decay_shots:
                factor = 1.0 + (initial_kick_mult - 1.0) * ((kick_decay_shots - i) / float(kick_decay_shots))
                dy = dy / factor
            deltas.append((round(float(dx), 2), round(float(dy), 2)))

        if len(sorted_green) > len(sorted_grey):
            for i in range(len(sorted_grey) - 1, len(sorted_green) - 1):
                dx = sorted_green[i][0] - sorted_green[i + 1][0]
                dy = sorted_green[i][1] - sorted_green[i + 1][1]
                deltas.append((round(float(dx), 2), round(float(dy), 2)))

    elif len(sorted_green) >= 2:
        for i in range(len(sorted_green) - 1):
            dx = sorted_green[i][0] - sorted_green[i + 1][0]
            dy = sorted_green[i][1] - sorted_green[i + 1][1]
            if initial_kick_mult > 1.0 and kick_decay_shots > 0 and i < kick_decay_shots:
                factor = 1.0 + (initial_kick_mult - 1.0) * ((kick_decay_shots - i) / float(kick_decay_shots))
                dy = dy / factor
            deltas.append((round(float(dx), 2), round(float(dy), 2)))

    if not deltas:
        return [], (0.0, 0.0)

    tail_count = min(5, max(3, len(deltas)))
    tail_sample = deltas[-tail_count:]
    tail_dx = round(float(sum(d[0] for d in tail_sample) / len(tail_sample)), 2)
    tail_dy = round(float(sum(d[1] for d in tail_sample) / len(tail_sample)), 2)

    full_pattern = list(deltas)
    while len(full_pattern) < max_shots:
        full_pattern.append((tail_dx, tail_dy))

    return full_pattern, (tail_dx, tail_dy)


def compute_recoil_pattern(
    dots: List[Tuple[float, float]],
    max_shots: int = 65,
    initial_kick_mult: float = 1.0,
    kick_decay_shots: int = 1
) -> Tuple[List[Tuple[float, float]], Tuple[float, float]]:
    """
    Computes a recoil pattern from a single set of dots (backwards compatible).
    """
    if len(dots) < 2:
        return [], (0.0, 0.0)
    return generate_calibrated_pattern(
        grey_dots=[],
        green_dots=dots,
        v_ratio=1.0,
        h_ratio=1.0,
        max_shots=max_shots,
        initial_kick_mult=initial_kick_mult,
        kick_decay_shots=kick_decay_shots
    )


def calibrate_from_image(
    image_input: Union[str, os.PathLike, Image.Image, np.ndarray],
    rpm: Union[int, float] = 679.0,
    max_shots: int = 65,
    manual_vert_mult: Optional[float] = None,
    manual_horiz_mult: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Performs full automated calibration from a weapon recoil screenshot:
    1. Detects base (grey) and loadout (green) dots on the mannequin
    2. Calculates vertical and horizontal compression ratios (tightness)
    3. Synthesizes calibrated recoil pattern and weapon kick parameters
    """
    try:
        res = extract_dual_dots_from_image(image_input)
    except Exception as e:
        return {
            "success": False,
            "error": f"Image processing error: {str(e)}",
            "grey_dots": [],
            "green_dots": [],
            "grey_count": 0,
            "green_count": 0,
            "match_percent": 0,
            "rpm": rpm,
            "delay_ms": calculate_fire_delay(rpm),
            "initial_kick_mult": 2.20,
            "kick_decay_shots": 6,
            "vertical_scale": 2.70,
            "horizontal_scale": 2.99,
            "pattern": [],
            "steady_state": (0.0, 0.0),
            "badge_text": "",
            "crop_bgr": None,
            "crop_offset": (0, 0),
            "vert_mult": 1.0,
            "horiz_mult": 1.0,
            "pattern_type": "None"
        }

    if not res["success"]:
        return {
            "success": False,
            "error": res.get("error", "No dots detected on mannequin."),
            "grey_dots": [],
            "green_dots": [],
            "grey_count": 0,
            "green_count": 0,
            "match_percent": 0,
            "rpm": rpm,
            "delay_ms": calculate_fire_delay(rpm),
            "initial_kick_mult": 2.20,
            "kick_decay_shots": 6,
            "vertical_scale": 2.70,
            "horizontal_scale": 2.99,
            "pattern": [],
            "steady_state": (0.0, 0.0),
            "badge_text": "",
            "crop_bgr": None,
            "crop_offset": (0, 0),
            "vert_mult": 1.0,
            "horiz_mult": 1.0,
            "pattern_type": "None"
        }

    grey_dots = res["grey_dots"]
    green_dots = res["green_dots"]

    # Calculate compression ratios
    v_ratio, h_ratio = calculate_compression_ratios(grey_dots, green_dots)

    if manual_vert_mult is not None:
        v_ratio = float(manual_vert_mult)
    if manual_horiz_mult is not None:
        h_ratio = float(manual_horiz_mult)

    # Determine reference dots for kick parameters
    ref_dots = green_dots if len(green_dots) >= 2 else grey_dots
    kick_params = calculate_kick_parameters(ref_dots)

    # Generate pattern scaled by compression ratios
    final_pattern, steady_state = generate_calibrated_pattern(
        grey_dots=grey_dots,
        green_dots=green_dots,
        v_ratio=v_ratio,
        h_ratio=h_ratio,
        max_shots=max_shots,
        initial_kick_mult=kick_params["initial_kick_mult"],
        kick_decay_shots=kick_params["kick_decay_shots"]
    )

    if len(grey_dots) >= 2 and len(green_dots) >= 2:
        pattern_type = "Pattern Matched"
    elif len(green_dots) >= 2:
        pattern_type = "Green Direct"
    elif len(grey_dots) >= 2:
        pattern_type = "Grey Base"
    else:
        pattern_type = "Fallback"

    delay_ms = calculate_fire_delay(rpm)
    pct = res["match_percent"]
    shot_count = max(len(green_dots), len(grey_dots))
    badge = f"Calibrated {shot_count} shots @ {int(rpm)} RPM ({delay_ms}ms) | Ratio: V×{v_ratio:.2f} H×{h_ratio:.2f} ({pct}% Sync)"

    return {
        "success": True,
        "error": None,
        "grey_dots": grey_dots,
        "green_dots": green_dots,
        "grey_count": res["grey_count"],
        "green_count": res["green_count"],
        "match_percent": pct,
        "rpm": rpm,
        "delay_ms": delay_ms,
        "initial_kick_mult": kick_params["initial_kick_mult"],
        "kick_decay_shots": kick_params["kick_decay_shots"],
        "vertical_scale": kick_params["vertical_scale"],
        "horizontal_scale": kick_params["horizontal_scale"],
        "pattern": final_pattern,
        "steady_state": steady_state,
        "badge_text": badge,
        "crop_bgr": res["crop_bgr"],
        "crop_offset": res["crop_offset"],
        "vert_mult": v_ratio,
        "horiz_mult": h_ratio,
        "pattern_type": pattern_type
    }
