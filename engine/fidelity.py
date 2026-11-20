"""Score only predeclared workflow weight backed by executed matching evidence."""


def score(inventory, results, *, unknowns=(), required=1.0):
    if not 0 < required <= 1:
        raise ValueError("threshold must be in (0, 1]")
    records = {result["id"]: result for result in results}
    workflow_ids = {item.id for item in inventory}
    if len(records) != len(results) or len(workflow_ids) != len(inventory) or records.keys() - workflow_ids:
        raise ValueError("result IDs must be unique and belong to the predeclared inventory")
    rows = [
        {
            "id": item.id,
            "weight": item.weight,
            "dimensions": item.dimensions,
            "status": records.get(item.id, {}).get("status", "missing"),
            "differences": records.get(item.id, {}).get("differences", {}),
        }
        for item in inventory
    ]

    def metrics(items):
        total = sum(item["weight"] for item in items)
        executed = sum(item["weight"] for item in items if item["status"] in {"pass", "fail"})
        matching = sum(item["weight"] for item in items if item["status"] == "pass")
        return {
            "weight": total,
            "executed_weight": executed,
            "matching_weight": matching,
            "coverage": executed / total if total else 0,
            "fidelity": matching / total if total else None,
        }

    summary = metrics(rows)
    return {
        **summary,
        "dimensions": {
            kind: metrics([row for row in rows if kind in row["dimensions"]])
            for kind in ("behavior", "data", "ui")
        },
        "results": rows,
        "unknowns": list(unknowns),
        "threshold": required,
        "gate_passed": bool(
            summary["weight"] and summary["coverage"] == 1 and summary["fidelity"] >= required
        ),
    }
