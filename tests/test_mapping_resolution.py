import pytest

from engine.uas import Control, Entity, Screen, UniversalAppSpec, Workflow
from engine.workflow_discovery import browser_targets, build_pair, resolve, snake, unprefixed


def spec_with(*controls, fields=None):
    fields = fields or {"code": "text", "unit_price": "integer", "sale_price": "integer", "total": "integer"}
    return UniversalAppSpec(
        "Fixture",
        screens=[Screen("entry", "Entry", list(controls), ["e"])],
        entities=[Entity("order_entry", "Orders", fields, ["e"])],
    )


def control(aid, role="Edit", name=""):
    return Control(aid or name, role, name, None, ["e"], aid)


def test_naming_styles():
    assert snake("UnitPrice") == "unit_price"
    assert snake("&Save:") == "save"
    assert unprefixed("txtUnitPrice") == "unit_price"
    assert unprefixed("btn_save") == "save"
    assert unprefixed("txtunitprice") == "txtunitprice"


@pytest.mark.parametrize(
    "source, expected",
    [
        (control("code"), ("code", "exact_id")),
        (control("UnitPrice"), ("unit_price", "normalized_id")),
        (control("txtUnitPrice"), ("unit_price", "unprefixed_id")),
        (control("btnSave", "Button"), ("save", "unprefixed_id")),
        (control("1001", "Edit", "Code:"), ("code", "unique_label")),
        (control("cmdOK", "Button", "&Calculate"), ("calculate", "unique_label")),
    ],
)
def test_predictable_mappings_resolve(source, expected):
    assert resolve(source, browser_targets(spec_with(source))) == expected


def test_ambiguous_and_unmatched_are_surfaced():
    targets = browser_targets(spec_with())
    with pytest.raises(ValueError, match=r"ambiguous.*sale_price.*unit_price"):
        resolve(control("Edit7", "Edit", "Price"), targets)
    with pytest.raises(ValueError, match="no predictable match"):
        resolve(control("Edit9", "Edit", "Discount"), targets)


def test_role_guard_blocks_input_to_button_and_outputs_for_actions():
    targets = browser_targets(spec_with())
    with pytest.raises(ValueError):
        resolve(control("save", "Edit"), targets)
    with pytest.raises(ValueError):
        resolve(control("code", "Button"), targets)
    assert resolve(control("lblStatus", "Text", "Status"), targets, observed=True) == (
        "status",
        "unprefixed_id",
    )
    with pytest.raises(ValueError):
        resolve(control("lblStatus", "Text", "Status"), targets)


def test_pair_uses_resolved_browser_ids_and_reports_review():
    price = control("txtUnitPrice")
    save = control("btnSave", "Button", "Save")
    total = control("lblTotal", "Text", "Total")
    spec = spec_with(price, save, total)
    steps = [
        {"action": "fill", "automation_id": "txtUnitPrice", "value": "7"},
        {"action": "click", "automation_id": "btnSave"},
    ]
    pair = build_pair(spec, Workflow("w", "W"), steps, {"lblTotal": "number"})
    assert [step["selector"] for step in pair["browser"]["steps"]] == ["#unit_price", "#save"]
    assert pair["observations"]["lblTotal"]["browser_selector"] == "#total"
    assert pair["resolution"]["btnSave"] == {"browser_id": "save", "method": "unprefixed_id"}
    assert pair["windows"] == steps
    vague = control("Edit7", "Edit", "Price")
    with pytest.raises(ValueError, match="ambiguous"):
        build_pair(
            spec_with(vague, total),
            Workflow("w", "W"),
            [{"action": "fill", "automation_id": "Edit7", "value": "1"}],
            {"lblTotal": "number"},
        )
