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
        PENDING.append(worker)
        return "modal_pending"
    if errors and not isinstance(errors[0], comtypes.COMError):
        raise errors[0]
    return "modal_pending" if errors else "completed"


PENDING = []  # invokes still blocked inside the source's modal loop


def settle(timeout=3.0):
    """Wait for earlier blocked invokes to return (their dialog was answered and the source's handler
    finished). Returns True when nothing is pending any more."""
    from time import monotonic

    deadline = monotonic() + timeout
    for worker in list(PENDING):
        worker.join(max(0.0, deadline - monotonic()))
        if not worker.is_alive():
            PENDING.remove(worker)
    return not PENDING


def wait_closed(dialog, timeout=3.0):
    from time import monotonic, sleep

    deadline = monotonic() + timeout
    while monotonic() < deadline:
        try:
            if not dialog.is_visible():
                return True
        except Exception:  # noqa: BLE001 - the element is gone
            return True
        sleep(0.05)
    return False


def menu_item(window, path, timeout=3.0):
    """The menu item at `path` (e.g. ["File", "Save"]), found through UIA parent links from a top-level
    item of the window's menu bar. Each level must match exactly one item. Parents are not opened:
    opening a WinForms menu first made the following dialog close on its own in repeated live runs.
    Waits up to `timeout` for the menu bar, which a freshly opened window may not expose yet."""
    from time import monotonic, sleep

    if not path or len(path) > 6:
        raise ValueError("menu path needs 1 to 6 items")
    deadline = monotonic() + timeout
    while True:
        level = [
            item
            for item in window.descendants(control_type="MenuItem")
            if _label(item.element_info.name) == _label(path[0])
            and item.parent().element_info.control_type == "MenuBar"
            and item.process_id() == window.process_id()
        ]
        if level or monotonic() >= deadline:
            break
        sleep(0.1)
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


DETACHED = []  # helper processes whose menu Invoke is still blocked by a dialog the click opened

_MENU_HELPER = """
import json, sys
from pywinauto.controls.uiawrapper import UIAWrapper
from pywinauto.uia_element_info import UIAElementInfo
from engine.desktop import menu_item
handle, pid, path = int(sys.argv[1]), int(sys.argv[2]), json.loads(sys.argv[3])
window = UIAWrapper(UIAElementInfo(handle))
if window.process_id() != pid:
    sys.exit(4)
item = menu_item(window, path)
if not item.is_enabled():
    sys.exit(3)
item.invoke()
"""


def invoke_menu_detached(handle, pid, path, wait=1.5):
    """Invoke a menu item from a separate helper process. A click that opens a modal dialog keeps its UIA
    Invoke call blocked for 20 s or more (measured live on WinForms); in this process that blocked later
    UIA calls and made the next menu click or dialog press fail. The helper holds the blocked call instead,
    and is ended once the dialog is answered or the plan finishes. The app receives exactly one click."""
    import json
    import subprocess
    import sys

    helper = subprocess.Popen(
        [sys.executable, "-c", _MENU_HELPER, str(handle), str(pid), json.dumps(list(path))],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        code = helper.wait(wait)
    except subprocess.TimeoutExpired:
        DETACHED.append(helper)
        return "modal_pending"
    if code == 4:
        raise RuntimeError("the window handle no longer belongs to the source process")
    if code == 3:
        raise PermissionError("disabled source menu item")
    if code:
        raise RuntimeError(
            "menu invoke failed: " + (helper.stderr.read().strip().splitlines() or ["?"])[-1][:160]
        )
    return "completed"


def end_detached(timeout=2.0):
    """Let helpers whose dialog was answered finish, then end the rest. Returns how many were ended."""
    import subprocess

    ended = 0
    for helper in list(DETACHED):
        try:
            helper.wait(timeout)
        except subprocess.TimeoutExpired:
            helper.kill()
            helper.wait(5)
            ended += 1
        DETACHED.remove(helper)
    return ended


def dialog_for(window, title, timeout=3.0):
    """A dialog window with this exact title owned by the same process: a child window of the main window
    (WinForms MessageBox) or another top-level window of the process. Waits up to `timeout` seconds for it
    to appear, since the click that opens it returns before the dialog is shown."""
    from time import monotonic, sleep

    from pywinauto import Desktop

    pid = window.process_id()
    deadline = monotonic() + timeout
    while True:
        found = [
            c
            for c in window.children()
            if c.element_info.control_type == "Window" and c.window_text() == title
        ]
        found += [
            w
            for w in Desktop(backend="uia").windows(process=pid, visible_only=True)
            if w.window_text() == title and w.handle != window.handle
        ]
        unique = {item.element_info.runtime_id: item for item in found}
        if len(unique) == 1 or monotonic() >= deadline:
            break
        sleep(0.1)
    if len(unique) != 1:
        raise RuntimeError(f"expected one dialog titled {redact(title)!r}, found {len(unique)}")
    return next(iter(unique.values()))


def native_dialog(pid, title, timeout=3.0):
    """The visible top-level window of `pid` with this exact title, found with plain Win32 calls. UIA
    reads of a dialog opened by a still-blocked UIA Invoke made the dialog ignore its buttons in about
    half of the live runs; these calls do not touch the dialog's UI Automation provider."""
    from time import monotonic, sleep

    import win32gui
    import win32process

    deadline = monotonic() + timeout
    while True:
        found = []

        def collect(handle, bucket):
            if (
                win32gui.IsWindowVisible(handle)
                and win32process.GetWindowThreadProcessId(handle)[1] == pid
                and win32gui.GetWindowText(handle) == title
            ):
                bucket.append(handle)

        win32gui.EnumWindows(collect, found)
        if len(found) == 1 or monotonic() >= deadline:
            break
        sleep(0.1)
    if len(found) != 1:
        raise RuntimeError(f"expected one dialog titled {redact(title)!r}, found {len(found)}")
    return found[0]


def native_dialog_click(pid, title, button):
    """Press `button` in the dialog by posting the WM_COMMAND/BN_CLICKED its button would send. This
    does not depend on the dialog being the active window, unlike BM_CLICK or UIA Invoke. Returns the
    dialog's text (redacted) and whether it closed."""
    from ctypes import windll
    from time import monotonic, sleep

    import win32gui

    dialog = native_dialog(pid, title)
    children = []
    win32gui.EnumChildWindows(dialog, lambda handle, _: children.append(handle), None)
    texts = [redact(win32gui.GetWindowText(h)) for h in children if win32gui.GetClassName(h) == "Static"]
    matches = [
        h
        for h in children
        if win32gui.GetClassName(h) == "Button" and _label(win32gui.GetWindowText(h)) == _label(button)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {button!r} button in the dialog, found {len(matches)}")
    control_id = windll.user32.GetDlgCtrlID(matches[0])
    windll.user32.PostMessageW(dialog, 0x0111, control_id & 0xFFFF, matches[0])  # WM_COMMAND, BN_CLICKED
    deadline = monotonic() + 3.0
    while monotonic() < deadline and win32gui.IsWindow(dialog) and win32gui.IsWindowVisible(dialog):
        sleep(0.05)
    closed = not (win32gui.IsWindow(dialog) and win32gui.IsWindowVisible(dialog))
    if not closed:
        raise RuntimeError("the dialog stayed open after its button command; nothing more was sent")
    return {
        "dialog_text": [t for t in texts if t][:10],
        "press": "wm_command",
        "closed": True,
        "settled": settle(),
    }


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
