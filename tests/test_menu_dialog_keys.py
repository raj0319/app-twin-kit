import pytest

from engine.desktop import KEYS
from engine.windows_actions import allow_key, validate_plan

ALLOWED = {
    ("menu", "File>Save"),
    ("dialog_click", "Confirm save|Yes"),
    ("keys", "note:^k"),
    ("keys", "window:{ESC}"),
}


def ok(plan):
    return validate_plan(plan, allow_mutation=True, sandbox_confirmed=True, allowed_targets=ALLOWED)


def test_allow_keys():
    assert allow_key({"action": "menu", "path": ["File", "Save"]}) == "File>Save"
    assert (
        allow_key({"action": "dialog_click", "dialog": "Confirm save", "button": "Yes"}) == "Confirm save|Yes"
    )
    assert allow_key({"action": "keys", "automation_id": "note", "value": "^k"}) == "note:^k"
    assert allow_key({"action": "keys", "value": "{ESC}"}) == "window:{ESC}"


def test_new_actions_need_exact_allowlist_and_consent():
    assert ok([{"action": "menu", "path": ["File", "Save"]}])
    assert ok([{"action": "dialog_click", "dialog": "Confirm save", "button": "Yes"}])
    assert ok(
        [{"action": "keys", "automation_id": "note", "value": "^k"}, {"action": "keys", "value": "{ESC}"}]
    )
    for plan in (
        [{"action": "menu", "path": ["File", "Exit"]}],
        [{"action": "dialog_click", "dialog": "Confirm save", "button": "No"}],
        [{"action": "keys", "automation_id": "note", "value": "^s"}],
    ):
        with pytest.raises(PermissionError):
            ok(plan)
    with pytest.raises(PermissionError):
        validate_plan([{"action": "menu", "path": ["File", "Save"]}], allowed_targets=ALLOWED)


@pytest.mark.parametrize("keys", ["%{F4}", "%f", "{F4}{LWIN}", "^{DELETE}x" * 11, ""])
def test_unsafe_or_unbounded_keys_are_refused(keys):
    assert not KEYS.fullmatch(keys)
    with pytest.raises((ValueError, PermissionError)):
        validate_plan(
            [{"action": "keys", "value": keys}],
            allow_mutation=True,
            sandbox_confirmed=True,
            allowed_targets={("keys", f"window:{keys}")},
        )


def test_sensitive_menu_paths_are_refused():
    with pytest.raises(ValueError):
        ok([{"action": "menu", "path": ["Account", "Reset password"]}])
