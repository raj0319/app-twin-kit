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
    if not matches:
        matches = _native_controls(window, selector)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected a unique visible control for {redact(selector)!r}, found {len(matches)}"
        )
    return matches[0]


def _native_controls(window, selector):
    """Visible controls with this automation ID found through the window's native child windows. In
    .NET 8 WinForms the UIA search from the window root sometimes returned nothing after several screen
    changes while the app stayed responsive (measured live); each control is still its own native window,
    and UIA wraps a native handle directly."""
    import win32gui
    from pywinauto.controls.uiawrapper import UIAWrapper
    from pywinauto.uia_element_info import UIAElementInfo

    handles = []
    win32gui.EnumChildWindows(window.handle, lambda h, bucket: bucket.append(h), handles)
    found = []
    for handle in handles:
        if not win32gui.IsWindowVisible(handle):
            continue
        try:
            control = UIAWrapper(UIAElementInfo(handle))
            if control.element_info.automation_id == selector and control.process_id() == window.process_id():
                found.append(control)
        except Exception:  # noqa: BLE001 - a child window without a UIA element
            continue
    return found


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
    item of the window's menu bar. Each level must match exactly one item. A parent is expanded only when
    its toolkit hides sub-items until the menu opens; the final item is never opened, only invoked.
    Waits up to `timeout` for the menu bar, which a freshly opened window may not expose yet."""
    from time import monotonic, sleep

    if not path or len(path) > 6:
        raise ValueError("menu path needs 1 to 6 items")
    deadline = monotonic() + timeout
    while True:
        level = [
            item
            for bar in menu_bars(window)
            for item in bar.children()
            if item.element_info.control_type == "MenuItem"
            and _label(item.element_info.name) == _label(path[0])
            and item.process_id() == window.process_id()
        ]
        if level or monotonic() >= deadline:
            break
        sleep(0.1)
    for depth, name in enumerate(path):
        if len(level) != 1:
            seen = []
            if depth == 0:
                for bar in menu_bars(window):
                    seen.append([(c.element_info.control_type, c.element_info.name) for c in bar.children()])
            raise RuntimeError(
                f"menu path {' > '.join(path[: depth + 1])!r} matched {len(level)} items"
                + (f"; menu bars seen: {seen}" if depth == 0 else "")
            )
        current = level[0]
        if depth + 1 < len(path):
            level = _submenu(current, path[depth + 1])
            if not level and _can_expand(current):
                # .NET (Core) WinForms and many other toolkits expose sub-items only while the menu is open
                # (measured on the .NET 8 Mini ERP fixture). Expanding returns at once; it does not click.
                current.expand()
                deadline = monotonic() + 2.0
                while not level and monotonic() < deadline:
                    sleep(0.1)
                    level = _submenu(current, path[depth + 1])
    return current


def menu_bars(window):
    """The window's menu bars. After a .NET 8 WinForms menu had been used and the screen changed, the
    window's UIA child list no longer contained its MenuStrip (measured live), so menu bars are also found
    through the native child windows, which UIA wraps directly."""
    import win32gui
    from pywinauto.controls.uiawrapper import UIAWrapper
    from pywinauto.uia_element_info import UIAElementInfo

    bars = {}
    for child in window.children():
        if child.element_info.control_type == "MenuBar":
            bars[tuple(child.element_info.runtime_id or ())] = child
    handles = []
    win32gui.EnumChildWindows(window.handle, lambda h, bucket: bucket.append(h), handles)
    for handle in handles:
        try:
            element = UIAWrapper(UIAElementInfo(handle))
            if element.element_info.control_type == "MenuBar":
                bars.setdefault(tuple(element.element_info.runtime_id or ()), element)
        except Exception:  # noqa: BLE001 - a child window without a UIA element
            continue
    return list(bars.values())


def select_tab(window, tabs_id, name):
    """Switch to the tab page `name` of the tab control `tabs_id` with SelectionItem.Select (no mouse)."""
    control = control_for(window, tabs_id)
    pages = [
        t
        for t in control.children()
        if t.element_info.control_type == "TabItem" and _label(t.element_info.name) == _label(name)
    ]
    if len(pages) != 1:
        raise RuntimeError(f"expected one tab {redact(name)!r}, found {len(pages)}")
    pages[0].iface_selection_item.Select()


def _can_expand(item):
    try:
        return bool(item.element_info.element.GetCurrentPattern(10005))  # ExpandCollapse
    except Exception:  # noqa: BLE001 - provider without the pattern
        return False


def _submenu(parent, name):
    """Menu items named `name` directly under `parent`, walking children level by level (direct children
    in .NET Framework WinForms, one level deeper under a Menu container in .NET 8 WinForms). A UIA
    descendants search skipped whole menus after a dropdown had been used once (measured live), so the
    walk uses children only and never enters another menu item."""
    found, queue = [], [(child, 0) for child in parent.children()]
    while queue:
        node, depth = queue.pop(0)
        kind = node.element_info.control_type
        if kind == "MenuItem":
            if _label(node.element_info.name) == _label(name):
                found.append(node)
        elif depth < 2:
            queue.extend((child, depth + 1) for child in node.children())
    return found


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
print("READY", flush=True)
item.invoke()
"""


def invoke_menu_detached(handle, pid, path, wait=1.5, startup=20.0):
    """Invoke a menu item from a separate helper process. A click that opens a modal dialog keeps its UIA
    Invoke call blocked for 20 s or more (measured live on WinForms); in this process that blocked later
    UIA calls and made the next menu click or dialog press fail. The helper holds the blocked call instead,
    and is ended once the dialog is answered or the plan finishes. The app receives exactly one click.

    The helper prints READY just before it clicks. Only then does the `wait` for a modal start, so the
    helper's own start-up time (1-2 s) can never let the click land after later steps have begun."""
    import json
    import subprocess
    import sys
    import threading

    helper = subprocess.Popen(
        [sys.executable, "-c", _MENU_HELPER, str(handle), str(pid), json.dumps(list(path))],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ready = threading.Event()

    def watch():
        for line in helper.stdout:
            if line.strip() == "READY":
                ready.set()
                return

    threading.Thread(target=watch, daemon=True).start()
    if not ready.wait(startup) and helper.poll() is None:
        helper.kill()
        helper.wait(5)
        raise RuntimeError("the menu helper did not reach the menu item in time; nothing was clicked")
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


def open_dialogs(pid, main_handle):
    """Visible standard dialog windows (#32770, e.g. message boxes) of the process other than the main
    window, with their title and static text (redacted). Plain Win32 calls only."""
    import win32gui
    import win32process

    found = []

    def collect(handle, bucket):
        # Any other visible top-level window of the process: standard dialogs (#32770) and the app's own
        # dialog forms (e.g. WinForms error windows), which real apps use as often as message boxes.
        if (
            handle != main_handle
            and win32gui.IsWindowVisible(handle)
            and win32process.GetWindowThreadProcessId(handle)[1] == pid
            and win32gui.GetWindowText(handle)
            and not win32gui.GetClassName(handle).startswith(("tooltips", "IME", "MSCTFIME"))
        ):
            bucket.append(handle)

    win32gui.EnumWindows(collect, found)
    result = []
    for handle in found:
        children = []
        win32gui.EnumChildWindows(handle, lambda h, bucket: bucket.append(h), children)
        text = [redact(win32gui.GetWindowText(h)) for h in children if win32gui.GetClassName(h) == "Static"]
        if not text:  # an app's own dialog form: take the visible text of its child controls
            text = [redact(win32gui.GetWindowText(h)) for h in children if win32gui.IsWindowVisible(h)]
        result.append(
            {
                "title": redact(win32gui.GetWindowText(handle)),
                "class": win32gui.GetClassName(handle)[:40],
                "text": [t for t in text if t][:6],
            }
        )
    return result


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


def select_scoped(combo, value, timeout=2.0):
    """Choose `value` in a combo box through UIA patterns only: expand, SelectionItem.Select on the list
    item, collapse, then confirm the combo shows the value. pywinauto's select() can fall back to a real
    mouse click at screen coordinates; on the Mini ERP fixture that click landed on the button under the
    drop-down. If the item cannot be selected without the mouse, nothing is clicked and an error is raised."""
    from time import monotonic, sleep

    if _native_combo_select(combo, value):
        return

    def items():
        return [
            item
            for item in combo.descendants(control_type="ListItem")
            if _label(item.element_info.name) == _label(value)
        ]

    expanded = False
    found = items()
    if not found and _can_expand(combo):
        combo.expand()
        expanded = True
        deadline = monotonic() + timeout
        while not found and monotonic() < deadline:
            sleep(0.1)
            found = items()
    try:
        if len(found) != 1:
            raise RuntimeError(
                f"expected one list item {redact(value)!r} in the combo box, found {len(found)}"
            )
        found[0].iface_selection_item.Select()
    finally:
        if expanded or _is_expanded(combo):
            combo.collapse()
    sleep(0.1)
    shown = combo.window_text() or combo.element_info.name
    if _label(shown) != _label(value):
        try:
            shown = combo.iface_value.CurrentValue
        except Exception:  # noqa: BLE001 - combo without a Value pattern
            pass
    if _label(shown) != _label(value):
        raise RuntimeError(f"the combo box shows {redact(shown)!r} after selecting {redact(value)!r}")


def _native_combo_select(combo, value):
    """Select by standard combo-box messages sent to this one native control: read the items
    (CB_GETLBTEXT), set the selection (CB_SETCURSEL) and notify the owner with CBN_SELCHANGE, as a user's
    choice would. No popup and no mouse. .NET 8 WinForms drop-downs did not always expose their list items
    to UIA after expanding (measured live). Returns False when the control is not a native combo box."""
    import ctypes
    from ctypes import wintypes

    import win32gui

    handle = getattr(combo, "handle", None)
    if not handle or "COMBOBOX" not in win32gui.GetClassName(handle).upper():
        return False
    user32 = ctypes.windll.user32
    user32.SendMessageW.restype = ctypes.c_ssize_t
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    count = user32.SendMessageW(handle, 0x0146, 0, 0)  # CB_GETCOUNT
    matches = []
    for index in range(max(0, count)):
        length = user32.SendMessageW(handle, 0x0149, index, 0)  # CB_GETLBTEXTLEN
        if length < 0 or length > 500:
            continue
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.SendMessageW(handle, 0x0148, index, ctypes.cast(buffer, ctypes.c_void_p).value)  # CB_GETLBTEXT
        if _label(buffer.value) == _label(value):
            matches.append(index)
    if len(matches) != 1:
        raise RuntimeError(f"expected one item {redact(value)!r} in the combo box, found {len(matches)}")
    user32.SendMessageW(handle, 0x014E, matches[0], 0)  # CB_SETCURSEL
    control_id = user32.GetDlgCtrlID(handle)
    parent = user32.GetParent(handle)
    result = ctypes.c_size_t()
    user32.SendMessageTimeoutW(
        parent, 0x0111, ((1 << 16) | (control_id & 0xFFFF)), handle, 0x0002, 5000, ctypes.byref(result)
    )  # WM_COMMAND, CBN_SELCHANGE
    if user32.SendMessageW(handle, 0x0147, 0, 0) != matches[0]:  # CB_GETCURSEL
        raise RuntimeError(f"the combo box did not keep {redact(value)!r} selected")
    return True


def _is_expanded(control):
    try:
        return control.iface_expand_collapse.CurrentExpandCollapseState == 1
    except Exception:  # noqa: BLE001 - no ExpandCollapse pattern
        return False


def wait_idle(window, timeout_ms=3000):
    """Wait until the source's UI thread has handled what the last action queued. .NET 8 WinForms runs a
    UIA Invoke's click handler after Invoke returns; at full speed the next steps overtook it (a "New" click
    cleared fields typed after it, measured live). WaitForInputIdle returns once the thread waits for input
    with an empty queue; the WM_NULL round trip then confirms it is processing messages again."""
    import ctypes
    from ctypes import wintypes

    kernel32, user32 = ctypes.windll.kernel32, ctypes.windll.user32
    process = kernel32.OpenProcess(
        0x00100000 | 0x0400, False, window.process_id()
    )  # SYNCHRONIZE | QUERY_INFO
    try:
        if process:
            user32.WaitForInputIdle(process, timeout_ms)
    finally:
        if process:
            kernel32.CloseHandle(process)
    result = ctypes.c_size_t()
    for _ in range(2):
        user32.SendMessageTimeoutW(
            wintypes.HWND(window.handle), 0, 0, 0, 0x0002, timeout_ms, ctypes.byref(result)
        )


def native_pid(window):
    """The window's process ID from Win32, not UIA: a UIA call can block while the source sits in a modal
    loop started by an earlier UIA Invoke."""
    import win32process

    return win32process.GetWindowThreadProcessId(window.handle)[1]


def click_control(control, timeout_ms=1500):
    """Click a button. A native button gets the WM_COMMAND/BN_CLICKED it would send its parent itself, via
    SendMessageTimeout: it returns once the click handler has finished (so the next step cannot overtake
    it), or after `timeout_ms` when the handler opened a modal dialog, without blocking anything here.
    In .NET 8 WinForms a UIA Invoke runs the handler inside the UIA call; when the handler showed a
    message box every later UIA call from this process hung behind it (measured live). Controls without a
    native button handle fall back to a UIA Invoke on a worker thread."""
    import ctypes
    from ctypes import wintypes

    import win32gui

    handle = getattr(control, "handle", None)
    if handle and "BUTTON" in win32gui.GetClassName(handle).upper():
        user32 = ctypes.windll.user32
        parent = user32.GetParent(handle)
        control_id = user32.GetDlgCtrlID(handle)
        if parent and control_id:
            result = ctypes.c_size_t()
            done = user32.SendMessageTimeoutW(
                wintypes.HWND(parent),
                0x0111,
                control_id & 0xFFFF,
                handle,
                0x0002,
                timeout_ms,
                ctypes.byref(result),
            )  # WM_COMMAND, BN_CLICKED (0), SMTO_ABORTIFHUNG
            return "completed" if done else "modal_pending"
    return invoke_async(control)


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
