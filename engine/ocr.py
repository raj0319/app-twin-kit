"""Screenshot and OCR fallback for controls with no accessible children (owner-drawn, custom-painted).

Uses the OCR engine built into Windows (engine/ocr.ps1); nothing is installed. Every result carries a
confidence and the method, and a click below the caller's threshold is refused rather than guessed.
Clicks are posted to the one control's window (WM_LBUTTONDOWN/UP in its own client coordinates): no
global mouse input is synthesised.
"""

import difflib
import json
import subprocess
import tempfile
from pathlib import Path

from .desktop import capture_window, redact

SCRIPT = Path(__file__).with_name("ocr.ps1")
UPSCALE = 2


def dpi_scale(window):
    """How many physical pixels one of the window's own pixels covers. A DPI-unaware window is drawn at
    96 DPI and stretched by Windows, so its capture is smaller than the UIA rectangle."""
    from ctypes import c_int, c_uint, c_void_p, windll

    user32 = windll.user32
    try:
        # The context is a pointer-sized handle; without these types ctypes truncates it on 64-bit Python.
        user32.GetWindowDpiAwarenessContext.restype = c_void_p
        user32.GetWindowDpiAwarenessContext.argtypes = [c_void_p]
        user32.GetAwarenessFromDpiAwarenessContext.restype = c_int
        user32.GetAwarenessFromDpiAwarenessContext.argtypes = [c_void_p]
        user32.GetDpiForWindow.restype = c_uint
        user32.GetDpiForWindow.argtypes = [c_void_p]
        context = user32.GetWindowDpiAwarenessContext(window.handle)
        aware = user32.GetAwarenessFromDpiAwarenessContext(context)
        if aware != 0:
            return 1.0
        # An unaware window reports a virtual 96 DPI; the scale Windows applies is the monitor's DPI.
        from ctypes import byref

        user32.MonitorFromWindow.restype = c_void_p
        user32.MonitorFromWindow.argtypes = [c_void_p, c_uint]
        monitor = user32.MonitorFromWindow(window.handle, 2)  # MONITOR_DEFAULTTONEAREST
        x, y = c_uint(), c_uint()
        if windll.shcore.GetDpiForMonitor(c_void_p(monitor), 0, byref(x), byref(y)):  # MDT_EFFECTIVE_DPI
            return 1.0
        dpi = x.value
    except (AttributeError, OSError):  # Windows before 10 1607
        return 1.0
    return dpi / 96 if dpi else 1.0


def capture_control(window, control, path):
    """Window-only capture cropped to one control, in the control's own client pixels, upscaled for OCR."""
    from PIL import Image

    scale = dpi_scale(window)
    with tempfile.TemporaryDirectory(prefix="twin-ocr-") as folder:
        whole = Path(folder) / "window.png"
        capture_window(window, whole)
        image = Image.open(whole)
        outer, inner = window.rectangle(), control.rectangle()
        box = [
            round((inner.left - outer.left) / scale),
            round((inner.top - outer.top) / scale),
            round((inner.right - outer.left) / scale),
            round((inner.bottom - outer.top) / scale),
        ]
        crop = image.crop(box)
        crop = crop.resize((crop.width * UPSCALE, crop.height * UPSCALE))
        crop.save(path)
    return {"scale": scale, "box": box, "size": [box[2] - box[0], box[3] - box[1]]}


def recognise(image_path, timeout=60):
    done = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-ImagePath",
            str(image_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if done.returncode:
        raise RuntimeError(
            "Windows OCR failed: " + (done.stderr.strip().splitlines() or ["no output"])[-1][:160]
        )
    result = json.loads(done.stdout)
    words = result.get("words") or []
    if isinstance(words, dict):
        words = [words]
    for word in words:  # back to the control's own pixels
        for key in ("x", "y", "w", "h"):
            word[key] = round(word[key] / UPSCALE)
    return {"engine": result.get("engine"), "language": result.get("language"), "words": words}


def locate(words, label):
    """Best box for `label`. Confidence: 0.95 for one exact (case-insensitive) word, lower for a fuzzy or
    repeated match. OCR gives no score of its own, so this measures how well the text matched."""
    target = label.strip().casefold()
    scored = []
    for word in words:
        text = word["text"].strip().casefold()
        ratio = 1.0 if text == target else difflib.SequenceMatcher(None, text, target).ratio()
        if ratio >= 0.6:
            scored.append((ratio, word))
    if not scored:
        return {"found": False, "confidence": 0.0, "matches": 0}
    scored.sort(key=lambda item: -item[0])
    ratio, best = scored[0]
    rivals = sum(1 for r, _ in scored if r >= ratio - 0.05)
    confidence = (0.95 if ratio == 1.0 else 0.8 * ratio) / rivals
    return {
        "found": True,
        "confidence": round(confidence, 3),
        "matches": rivals,
        "text": redact(best["text"]),
        "box": [best["x"], best["y"], best["w"], best["h"]],
        "center": [best["x"] + best["w"] // 2, best["y"] + best["h"] // 2],
    }


def post_click(control, x, y, scale=1.0):
    """Left click at client (x, y) of the control's own window handle, posted to that window only.
    (x, y) are in the control's own pixels. Windows converts posted mouse coordinates for DPI-unaware
    windows as if they were physical, so they are scaled up first (measured live at 125%)."""
    from ctypes import windll

    handle = getattr(control, "handle", None)
    if not handle:
        raise RuntimeError("the control has no window handle to post a click to")
    x, y = round(x * scale), round(y * scale)
    point = (y << 16) | (x & 0xFFFF)
    windll.user32.PostMessageW(handle, 0x0200, 0, point)  # WM_MOUSEMOVE
    windll.user32.PostMessageW(handle, 0x0201, 0x0001, point)  # WM_LBUTTONDOWN, MK_LBUTTON
    windll.user32.PostMessageW(handle, 0x0202, 0, point)  # WM_LBUTTONUP


def read_text(window, control, evidence_path):
    shot = capture_control(window, control, evidence_path)
    words = recognise(evidence_path)["words"]
    text = " ".join(word["text"] for word in words)
    return {
        "method": "ocr",
        "text": redact(text),
        "words": len(words),
        "image": Path(evidence_path).name,
        **shot,
    }


def click_label(window, control, label, evidence_path, min_confidence=0.8):
    shot = capture_control(window, control, evidence_path)
    found = locate(recognise(evidence_path)["words"], label)
    record = {
        "method": "ocr",
        "label": label,
        "image": Path(evidence_path).name,
        "scale": shot["scale"],
        **found,
    }
    if not found["found"] or found["confidence"] < min_confidence:
        record["needs_review"] = True
        raise LookupError(json.dumps(record))
    post_click(control, *found["center"], scale=shot["scale"])
    return record
