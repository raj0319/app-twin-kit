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


def _label(text):
    return (text or "").replace("&", "").strip().casefold()


def invoke_async(control, wait=1.0):
    """Invoke on a worker thread. Some toolkits (WinForms through the MSAA bridge) only return from Invoke
    after a modal dialog the click opened is closed; waiting here would deadlock the replay. Returns
    "completed" or "modal_pending" (the call is still blocked, usually by a dialog)."""
    import threading

    import comtypes

    errors = []

    def call():
        comtypes.CoInitialize()
        try:
            control.invoke()
        except comtypes.COMError as exc:  # raised when the target thread stays blocked in a modal loop
            errors.append(exc)
        except Exception as exc:  # noqa: BLE001 - reported to the caller below
            errors.append(exc)
        finally:
            comtypes.CoUninitialize()

    worker = threading.Thread(target=call, daemon=True)
    worker.start()
    worker.join(wait)
    if worker.is_alive():
        return "modal_pending"
    if errors and not isinstance(errors[0], comtypes.COMError):
        raise errors[0]
    return "modal_pending" if errors else "completed"


def menu_item(window, path):
    """The menu item at `path` (e.g. ["File", "Save"]), found through UIA parent links from a top-level
    item of the window's menu bar. Each level must match exactly one item. Parents are not opened:
    opening a WinForms menu first made the following dialog close on its own in repeated live runs."""
    if not path or len(path) > 6:
        raise ValueError("menu path needs 1 to 6 items")
    level = [
        item
        for item in window.descendants(control_type="MenuItem")
        if _label(item.element_info.name) == _label(path[0])
        and item.parent().element_info.control_type == "MenuBar"
        and item.process_id() == window.process_id()
    ]
    for depth, name in enumerate(path):
        if len(level) != 1:
            raise RuntimeError(f"menu path {' > '.join(path[: depth + 1])!r} matched {len(level)} items")
        current = level[0]
        if depth + 1 < len(path):
            level = [
                item
                for item in current.children(control_type="MenuItem")
                if _label(item.element_info.name) == _label(path[depth + 1])
            ]
    return current


def dialog_for(window, title):
    """A dialog window with this exact title owned by the same process: a child window of the main window
    (WinForms MessageBox) or another top-level window of the process."""
    from pywinauto import Desktop

    pid = window.process_id()
    found = [
        c for c in window.children() if c.element_info.control_type == "Window" and c.window_text() == title
    ]
    found += [
        w
        for w in Desktop(backend="uia").windows(process=pid, visible_only=True)
        if w.window_text() == title and w.handle != window.handle
    ]
    unique = {item.element_info.runtime_id: item for item in found}
    if len(unique) != 1:
        raise RuntimeError(f"expected one dialog titled {redact(title)!r}, found {len(unique)}")
    return next(iter(unique.values()))


def dialog_text(dialog):
    return [redact(item.window_text()) for item in dialog.descendants(control_type="Text")][:10]


KEYS = re.compile(
    r"(?:[\^+]?(?:[A-Za-z0-9 .,-]|\{(?:ENTER|TAB|ESC|UP|DOWN|LEFT|RIGHT|HOME|END|DELETE|BACKSPACE|F(?:[1-9]|1[0-2]))\})){1,20}"
)


def send_keys_scoped(control, window, keys):
    """Post keystrokes to one window's thread (PostMessage plus that thread's keyboard state for Ctrl and
    Shift). No global input is synthesised. Alt (%) is not accepted, so Alt+F4 and menu accelerators
    cannot be sent."""
    from pywinauto.controls.hwndwrapper import HwndWrapper

    if not KEYS.fullmatch(keys or ""):
        raise ValueError("keys must use the safe subset: letters, digits, Ctrl (^), Shift (+), named keys")
    handle = getattr(control, "handle", None) or window.handle
    HwndWrapper(handle).send_keystrokes(keys)


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
