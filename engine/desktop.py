"""Process-pinned UI Automation and privacy-aware snapshots."""

import hashlib
import re
from collections import deque
from datetime import datetime, timezone

SECRET = re.compile(r"password|secret|token|api[ _-]?key|ssn|credit[ _-]?card", re.I)
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")


def redact(value):
    text = str(value or "")
    return "[redacted]" if SECRET.search(text) else EMAIL.sub("[redacted]", text)[:300]


def utc():
    return datetime.now(timezone.utc).isoformat()


def identity(*parts):
    return hashlib.sha256(repr(parts).encode()).hexdigest()[:20]


def window_for(title, pid=None):
    from pywinauto import Desktop

    if not title or len(title) > 200:
        raise ValueError("an exact window title is required")
    windows = (
        Desktop(backend="uia").windows(title=title, process=pid, visible_only=True)
        if pid
        else (Desktop(backend="uia").windows(title=title, visible_only=True))
    )
    if len(windows) != 1:
        raise RuntimeError(f"expected exactly one matching visible window, found {len(windows)}")
    return windows[0]


def list_windows():
    from pywinauto import Desktop

    result = []
    for window in Desktop(backend="uia").windows(visible_only=True):
        try:
            if title := window.window_text():
                result.append(
                    {
                        "title": redact(title),
                        "pid": window.process_id(),
                        "framework": window.element_info.framework_id,
                    }
                )
        except (RuntimeError, OSError):
            continue
    return result


def tree(window, limit=500, depth_limit=8):
    queue = deque([(window, 0, "root", 0)])
    controls = []
    while queue and len(controls) < limit:
        control, depth, parent, ordinal = queue.popleft()
        try:
            info = control.element_info
            if info.process_id != window.process_id():
                continue
            raw_id = info.automation_id or ""
            role = info.control_type or ""
            key = identity(parent, raw_id, role, ordinal if not raw_id else "")
            rect = info.rectangle
            item = {
                "id": key,
                "parent": parent,
                "automation_id": redact(raw_id),
                "name": "[redacted]" if role in {"Edit", "Document"} else redact(info.name),
                "control_type": role,
                "framework": info.framework_id,
                "bounds": [rect.left, rect.top, rect.width(), rect.height()],
                "visible": bool(control.is_visible()),
                "enabled": bool(control.is_enabled()),
                "depth": depth,
            }
            controls.append(item)
            if depth < depth_limit:
                queue.extend((child, depth + 1, key, index) for index, child in enumerate(control.children()))
        except Exception as exc:
            controls.append({"depth": depth, "error": type(exc).__name__})
    stable = [(item.get("id"), item.get("visible"), item.get("enabled")) for item in controls]
    return {
        "state_id": identity(stable),
        "captured_at": utc(),
        "pid": window.process_id(),
        "controls": controls,
        "truncated": bool(queue) or any(c["depth"] == depth_limit for c in controls),
    }


def control_for(window, selector):
    if not selector:
        return window
    matches = [
        control
        for control in window.descendants()
        if control.element_info.automation_id == selector
        and control.process_id() == window.process_id()
        and control.is_visible()
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected a unique visible control for {redact(selector)!r}, found {len(matches)}"
        )
    return matches[0]


def read_control(control):
    info = control.element_info
    if SECRET.search((info.name or "") + " " + (info.automation_id or "")):
        return "[redacted]"
    # Avoid recording arbitrary text entered into source fields.
    if info.control_type in {"Edit", "Document"}:
        return "[redacted]"
    return redact(control.window_text())


def capture_window(window, path):
    """Capture the selected HWND only, including when other windows overlap it."""
    from ctypes import windll

    import win32gui
    import win32ui
    from PIL import Image

    handle = window.handle
    rect = window.rectangle()
    width, height = rect.width(), rect.height()
    if not 0 < width * height <= 24_000_000:
        raise OSError("unsupported capture dimensions")
    dc_handle = win32gui.GetWindowDC(handle)
    source = win32ui.CreateDCFromHandle(dc_handle)
    memory = source.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(source, width, height)
    previous = memory.SelectObject(bitmap)
    try:
        if not windll.user32.PrintWindow(handle, memory.GetSafeHdc(), 2):
            raise OSError("PrintWindow unavailable")
        image = Image.frombytes("RGB", (width, height), bitmap.GetBitmapBits(True), "raw", "BGRX")
        if image.getbbox() is None:
            raise OSError("PrintWindow returned a blank image")
        image.save(path)
    finally:
        memory.SelectObject(previous)
        win32gui.DeleteObject(bitmap.GetHandle())
        memory.DeleteDC()
        win32gui.ReleaseDC(handle, dc_handle)
