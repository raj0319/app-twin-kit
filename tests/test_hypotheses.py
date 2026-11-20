import json

import pytest

from engine.hypotheses import (
    allowed_values,
    analyse,
    bounds,
    calculation,
    from_trace,
    narrow_bounds,
    persistence,
    required,
    roles,
)
from engine.rule_probes import save


def probe(pid, accepted=True, rejected_field=None, **inputs):
    record = {"id": pid, "evidence_id": pid, "inputs": inputs, "accepted": accepted}
    if rejected_field:
        record["rejected_field"] = rejected_field
    return record


def test_required_selects_and_rejects():
    probes = [probe("a", False, code=""), probe("b", code="X1"), probe("c", code="X2")]
    assert required(probes, "code")["status"] == "selected"
    opposite = [probe("a", True, code=""), probe("b", code="X")]
    result = required(opposite, "code")
    assert result["surviving"] == ["optional"]
    assert {"hypothesis": "required", "counterexample": "a"} in result["rejected"]
    assert required([probe("b", code="X")], "code")["status"] == "insufficient_evidence"


def test_bounds_narrow_and_detect_non_bound():
    probes = [probe("a", qty=2), probe("b", qty=5), probe("c", False, "qty", qty=0)]
    result = bounds(probes, "qty")
    assert result["status"] == "ambiguous" and result["hypotheses"]["min"]["between"] == [0, 2]
    assert result["next_probe"]["inputs"] == {"qty": 1}
    probes.append(probe("d", qty=1))
    assert bounds(probes, "qty")["hypotheses"]["min"]["exact"] == 1
    hole = [probe("a", qty=1), probe("b", qty=9), probe("c", False, "qty", qty=4)]
    assert bounds(hole, "qty")["status"] == "none_consistent"
    other_field = [probe("a", qty=2), probe("b", qty=5), probe("c", False, "price", qty=0)]
    assert bounds(other_field, "qty")["status"] == "insufficient_evidence"


def test_allowed_values_only_for_text():
    probes = [probe("a", kind="A"), probe("b", kind="B"), probe("c", False, "kind", kind="Z")]
    assert allowed_values(probes, "kind") | {} == {
        "status": "selected",
        "one_of": ["A", "B"],
        "refused": ["Z"],
        "support": 3,
    }
    assert allowed_values([probe("a", n=1), probe("b", False, n=0)], "n")["status"] == "not_applicable"


def test_calculation_selects_single_formula_or_reports_ambiguity():
    rows = [
        {**probe("a", q=2, p=7), "outputs": {"total": 14}},
        {**probe("b", q=3, p=7), "outputs": {"total": 21}},
    ]
    result = calculation(rows, "total", ["p", "q"])
    assert result["status"] == "selected" and result["surviving"] == ["product(p,q)"]
    assert any(r["hypothesis"] == "sum(p,q)" for r in result["rejected"])
    tie = [{**probe("a", q=2, p=2), "outputs": {"total": 4}}]
    tied = calculation(tie, "total", ["p", "q"])
    assert tied["status"] == "ambiguous" and set(tied["surviving"]) >= {"product(p,q)", "sum(p,q)"}
    assert tied["next_probe"]["inputs"] == {"p": 3, "q": 11}


def test_persistence_needs_varying_values_and_reports_ambiguity():
    rows = [
        {
            **probe("a", code="A", q=2),
            "outputs": {"total": 14},
            "persisted": {"orders.code": "A", "orders.total": 14, "orders.flag": 1},
        },
        {
            **probe("b", code="B", q=3),
            "outputs": {"total": 21},
            "persisted": {"orders.code": "B", "orders.total": 21, "orders.flag": 1},
        },
    ]
    result = persistence(rows)
    assert result["mappings"] == {"orders.code": "inputs.code", "orders.total": "outputs.total"}
    copies = [
        {**probe("a", q=2), "outputs": {"total": 2}, "persisted": {"t.v": 2}},
        {**probe("b", q=3), "outputs": {"total": 3}, "persisted": {"t.v": 3}},
    ]
    assert persistence(copies)["ambiguous"] == {"t.v": ["inputs.q", "outputs.total"]}


def test_roles_matrix_and_conflicts():
    rows = [
        {**probe("a"), "role": "clerk", "action": "save"},
        {**probe("b", False), "role": "viewer", "action": "save"},
    ]
    assert roles(rows)["status"] == "selected"
    rows.append({**probe("c", False), "role": "clerk", "action": "save"})
    assert roles(rows)["conflicts"][0]["probes"] == ["a", "c"]


def test_from_trace_and_live_style_narrowing():
    plan = [
        {"action": "fill", "automation_id": "quantity", "value": "0"},
        {"action": "click", "automation_id": "calculate"},
    ]
    record = from_trace(
        "p",
        plan,
        {"values": {"status": "Quantity failed min validation", "total": ""}},
        evidence_id="e",
        accepted_messages={"Calculated"},
    )
    assert record["inputs"] == {"quantity": 0} and not record["accepted"]
    assert record["rejected_field"] == "quantity" and record["outputs"] == {}

    def run(inputs):
        return probe(
            f"run-{inputs['qty']}", inputs["qty"] >= 3, None if inputs["qty"] >= 3 else "qty", **inputs
        )

    seed = [probe("a", qty=9), probe("b", False, "qty", qty=0)]
    outcome = narrow_bounds("qty", seed, run, baseline={"code": "X"})
    assert outcome["result"]["hypotheses"]["min"]["exact"] == 3
    assert len(outcome["probes"]) - len(seed) <= 4


def test_analyse_requires_ids_and_never_confirms(tmp_path):
    with pytest.raises(ValueError):
        analyse([{"inputs": {}}])
    path = tmp_path / "probes.json"
    path.write_text(
        json.dumps({"probes": [probe("a", False, code=""), probe("b", code="X"), probe("c", code="Y")]})
    )
    summary = save(path, tmp_path / "out.json")
    assert summary["confirmed"] == 0 and summary["selected"] == 1
    assert (
        json.loads((tmp_path / "out.json").read_text())["fields"]["code"]["required"]["status"] == "selected"
    )
