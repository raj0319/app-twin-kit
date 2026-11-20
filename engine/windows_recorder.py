"""Bounded process-scoped observation of UIA focus and state transitions."""

from time import monotonic, sleep

from .desktop import identity, redact, tree, utc, window_for
from .run_state import atomic_json


def record_window(title, out_path, *, pid=None, seconds=15, interval=0.5):
    if not 1 <= seconds <= 300 or not 0.1 <= interval <= 5:
        raise ValueError("invalid recording configuration")
    from pywinauto.uia_defines import IUIA
    from pywinauto.uia_element_info import UIAElementInfo

    window = window_for(title, pid)
    events = []
    previous = None
    deadline = monotonic() + seconds
    while monotonic() < deadline:
        focus = UIAElementInfo(IUIA().iuia.GetFocusedElement())
        if focus.process_id == window.process_id():
            snapshot = tree(window)
            selector = redact(focus.automation_id)
            signature = (snapshot["state_id"], selector)
            if signature != previous:
                events.append(
                    {
                        "id": identity(len(events), *signature),
                        "at": utc(),
                        "focused_control": selector,
                        "state": snapshot,
                    }
                )
            previous = signature
        else:
            previous = None
        sleep(interval)
    result = {"pid": window.process_id(), "kind": "passive_state_samples", "events": events}
    atomic_json(out_path, result)
    return result
