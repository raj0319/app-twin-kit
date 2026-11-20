"""Select among bounded behaviour hypotheses using controlled probe results.

Each family has a fixed, small hypothesis space. A hypothesis survives only if every probe agrees with
it; a rejected one keeps the probe that contradicts it. When more than one survives, the result says so
and proposes the input that would separate them. Nothing here confirms a rule: the output is evidence
for review, and any suggested probe still needs fixture consent and an allowlisted action to run.

Probe record (one per controlled experiment):
  {"id": "p1", "evidence_id": "probe-1", "entity": "order",
   "inputs": {"quantity": 2, "unit_price": 7},        # values entered for this probe
   "accepted": true,                                   # the source accepted the input
   "message": "Calculated",                            # optional visible outcome text
   "outputs": {"total": 14},                           # optional values the source showed
   "persisted": {"orders.total": 14, ...},             # optional row the source saved (table.column)
   "role": "clerk", "action": "save"}                  # optional, for permission hypotheses
"""

from itertools import permutations

MIN_SUPPORT = 2  # distinct supporting probes before a hypothesis is called "selected"


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _empty(value):
    return value is None or value == ""


def _verdict(survivors, support, rejected, alternatives_hint=None):
    if not survivors:
        status = "none_consistent"
    elif len(survivors) > 1:
        status = "ambiguous"
    elif support < MIN_SUPPORT:
        status = "insufficient_evidence"
    else:
        status = "selected"
    result = {"status": status, "surviving": survivors, "support": support, "rejected": rejected}
    if alternatives_hint and status in {"ambiguous", "insufficient_evidence"}:
        result["next_probe"] = alternatives_hint
    return result


def required(probes, field):
    relevant = [p for p in probes if field in p.get("inputs", {})]
    empties = [p for p in relevant if _empty(p["inputs"][field])]
    filled = [p for p in relevant if not _empty(p["inputs"][field])]
    if not empties:
        return {
            "status": "insufficient_evidence",
            "surviving": ["required", "optional"],
            "support": 0,
            "rejected": [],
            "next_probe": {"inputs": {field: ""}, "why": "no probe left this field empty"},
        }
    rejected = []
    survivors = []
    if any(p["accepted"] for p in empties):
        rejected.append(
            {"hypothesis": "required", "counterexample": next(p["id"] for p in empties if p["accepted"])}
        )
    elif empties:
        survivors.append("required")
    optional_counter = next((p["id"] for p in empties if not p["accepted"]), None)
    if optional_counter:
        rejected.append({"hypothesis": "optional", "counterexample": optional_counter})
    elif empties:
        survivors.append("optional")
    support = len(empties) + sum(1 for p in filled if p["accepted"])
    return _verdict(survivors, support, rejected)


def bounds(probes, field):
    """Narrow min and max to intervals. A probe only counts for a field when the probe changed nothing
    else that could explain a rejection (all other fields accepted elsewhere), so cross-field effects are
    not mistaken for a bound."""
    numeric = [p for p in probes if _number(p.get("inputs", {}).get(field))]
    accepted = sorted(p["inputs"][field] for p in numeric if p["accepted"])
    isolated = [p for p in numeric if not p["accepted"] and p.get("rejected_field", field) == field]
    if not accepted:
        return {"status": "insufficient_evidence", "reason": "no accepted numeric value", "support": 0}
    low, high = accepted[0], accepted[-1]
    below = [p["inputs"][field] for p in isolated if p["inputs"][field] < low]
    above = [p["inputs"][field] for p in isolated if p["inputs"][field] > high]
    inside = [p for p in isolated if low <= p["inputs"][field] <= high]
    result = {"field": field, "accepted_range": [low, high], "support": len(numeric)}
    if inside:
        result.update(
            status="none_consistent",
            reason="a value inside the accepted range was rejected; not a simple bound",
            counterexample=inside[0]["id"],
        )
        return result
    hypotheses = {}
    if below:
        edge = max(below)
        hypotheses["min"] = {"between": [edge, low], "exact": low if low - edge <= 1 else None}
    if above:
        edge = min(above)
        hypotheses["max"] = {"between": [high, edge], "exact": high if edge - high <= 1 else None}
    result["hypotheses"] = hypotheses
    open_edges = [name for name, h in hypotheses.items() if h["exact"] is None]
    if not hypotheses:
        result["status"] = "insufficient_evidence"
        result["next_probe"] = {
            "inputs": {field: low - 1},
            "why": "no rejected value outside the accepted range",
        }
    elif open_edges:
        name = open_edges[0]
        a, b = hypotheses[name]["between"]
        result["status"] = "ambiguous"
        result["next_probe"] = {"inputs": {field: (a + b) // 2 if a + 1 < b else b}, "why": f"narrow {name}"}
    else:
        result["status"] = "selected" if len(numeric) >= MIN_SUPPORT else "insufficient_evidence"
    return result


def allowed_values(probes, field, limit=12):
    values = [p for p in probes if field in p.get("inputs", {}) and not _empty(p["inputs"][field])]
    if values and all(_number(p["inputs"][field]) for p in values):
        return {"status": "not_applicable", "reason": "numeric field; see bounds", "support": len(values)}
    accepted = sorted({str(p["inputs"][field]) for p in values if p["accepted"]})
    refused = sorted(
        {
            str(p["inputs"][field])
            for p in values
            if not p["accepted"] and p.get("rejected_field", field) == field
        }
    )
    if not refused or len(accepted) > limit:
        return {"status": "insufficient_evidence", "accepted": accepted[:limit], "support": len(values)}
    overlap = set(accepted) & set(refused)
    if overlap:
        return {
            "status": "none_consistent",
            "reason": "same value accepted and refused",
            "values": sorted(overlap),
        }
    status = "selected" if len(values) >= MIN_SUPPORT + 1 else "insufficient_evidence"
    return {"status": status, "one_of": accepted, "refused": refused, "support": len(values)}


CALCULATIONS = {
    "product": lambda a, b: a * b,
    "sum": lambda a, b: a + b,
    "difference": lambda a, b: a - b,
}


def calculation(probes, output, candidates):
    """Which formula over two numeric inputs (or a copy of one) produces `output`."""
    rows = [
        p
        for p in probes
        if p["accepted"]
        and _number(p.get("outputs", {}).get(output))
        and all(_number(p.get("inputs", {}).get(name)) for name in candidates)
    ]
    hypotheses = {}
    for left, right in permutations(candidates, 2):
        for name, function in CALCULATIONS.items():
            if name != "difference" and left > right:
                continue  # product and sum are symmetric
            hypotheses[f"{name}({left},{right})"] = (function, (left, right))
    for name in candidates:
        hypotheses[f"copy({name})"] = (lambda a, _b: a, (name, name))
    survivors, rejected = [], []
    for label, (function, (left, right)) in hypotheses.items():
        counter = next(
            (
                p["id"]
                for p in rows
                if function(p["inputs"][left], p["inputs"][right]) != p["outputs"][output]
            ),
            None,
        )
        if counter:
            rejected.append({"hypothesis": label, "counterexample": counter})
        else:
            survivors.append(label)
    distinct = {tuple(p["inputs"][n] for n in candidates) for p in rows}
    hint = None
    if len(survivors) > 1 and len(candidates) >= 2:
        hint = {
            "inputs": dict(zip(candidates, (3, 11))),
            "why": "values that give different results per formula",
        }
    elif not rows:
        hint = {"inputs": dict(zip(candidates, (3, 11))), "why": "no accepted probe showed the output"}
    result = _verdict(survivors, len(distinct), rejected, hint)
    result["output"] = output
    return result


def branches(probes):
    """Distinct visible outcomes and which field change explains each; the order validation runs in is
    read from probes where several fields were invalid at once."""
    outcomes = {}
    for p in probes:
        key = p.get("message") or ("accepted" if p["accepted"] else "rejected")
        entry = outcomes.setdefault(key, {"accepted": p["accepted"], "probes": [], "fields": set()})
        entry["probes"].append(p["id"])
        if p.get("rejected_field"):
            entry["fields"].add(p["rejected_field"])
    order = []
    for p in probes:
        if len(p.get("invalid_fields", [])) > 1 and p.get("rejected_field"):
            order.append(
                {"invalid": p["invalid_fields"], "reported_first": p["rejected_field"], "probe": p["id"]}
            )
    return {
        "outcomes": {k: {**v, "fields": sorted(v["fields"])} for k, v in sorted(outcomes.items())},
        "validation_order": order,
        "status": "selected" if outcomes else "insufficient_evidence",
    }


def persistence(probes):
    """Which input or output value lands in which saved column. A mapping survives only when the values
    agree in every saving probe and differ between at least two probes (so a constant cannot pass)."""
    saving = [p for p in probes if p["accepted"] and p.get("persisted")]
    if not saving:
        return {"status": "insufficient_evidence", "mappings": {}, "support": 0}
    sources = sorted(
        {f"inputs.{k}" for p in saving for k in p.get("inputs", {})}
        | {f"outputs.{k}" for p in saving for k in p.get("outputs", {})}
    )
    columns = sorted({c for p in saving for c in p["persisted"]})

    def value(p, source):
        kind, name = source.split(".", 1)
        return p.get(kind, {}).get(name)

    mappings, ambiguous = {}, {}
    for column in columns:
        fits = []
        for source in sources:
            pairs = [
                (value(p, source), p["persisted"].get(column)) for p in saving if column in p["persisted"]
            ]
            if pairs and all(str(a) == str(b) for a, b in pairs) and len({str(a) for a, _ in pairs}) > 1:
                fits.append(source)
        if len(fits) == 1:
            mappings[column] = fits[0]
        elif fits:
            ambiguous[column] = fits
    status = (
        "selected" if mappings and not ambiguous else "ambiguous" if ambiguous else "insufficient_evidence"
    )
    return {"status": status, "mappings": mappings, "ambiguous": ambiguous, "support": len(saving)}


def roles(probes):
    """Permission matrix from probes that name a role and an action. Contradictions are reported."""
    matrix, conflicts = {}, []
    for p in probes:
        if not (p.get("role") and p.get("action")):
            continue
        key = (p["role"], p["action"])
        allowed = bool(p.get("permitted", p["accepted"]))
        if key in matrix and matrix[key]["allowed"] != allowed:
            conflicts.append({"role": key[0], "action": key[1], "probes": [*matrix[key]["probes"], p["id"]]})
        entry = matrix.setdefault(key, {"allowed": allowed, "probes": []})
        entry["probes"].append(p["id"])
    rows = [{"role": r, "action": a, **v} for (r, a), v in sorted(matrix.items())]
    status = "none_consistent" if conflicts else "selected" if rows else "insufficient_evidence"
    return {"status": status, "permissions": rows, "conflicts": conflicts}


def _typed(value):
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
    return value


def from_trace(probe_id, plan, trace, *, evidence_id, accepted_messages, message_field="status"):
    """One probe record from an executed source plan (`windows_actions.execute_plan`): the typed inputs
    come from the plan's fill steps, the outcome from the values read after it. The rejected field is
    named only when exactly one input's name appears in the message."""
    inputs = {
        step["automation_id"]: _typed(step.get("value", ""))
        for step in plan
        if step.get("action") == "fill" and step.get("automation_id")
    }
    values = dict(trace.get("values", {}))
    message = values.pop(message_field, None)
    accepted = message in set(accepted_messages)
    probe = {
        "id": probe_id,
        "evidence_id": evidence_id,
        "inputs": inputs,
        "accepted": accepted,
        "message": message,
        "outputs": {k: _typed(v) for k, v in values.items() if _number(_typed(v))},
    }
    if not accepted and message:
        text = message.lower()
        named = [name for name in inputs if name.replace("_", " ") in text]
        if len(named) == 1:
            probe["rejected_field"] = named[0]
    return probe


def narrow_bounds(field, probes, run_probe, *, baseline, max_probes=6):
    """Run the suggested probe for `field` until its bound is exact or the probe budget is spent.
    `run_probe(inputs)` executes one approved probe (fixture consent and allowlist are the caller's) and
    returns a probe record; `baseline` holds accepted values for the other fields."""
    probes = list(probes)
    for _ in range(max_probes):
        result = bounds(probes, field)
        hint = result.get("next_probe")
        if result["status"] != "ambiguous" or not hint:
            return {"result": result, "probes": probes}
        probes.append(run_probe({**baseline, **hint["inputs"]}))
    return {"result": bounds(probes, field), "probes": probes, "budget_exhausted": True}


def analyse(probes, *, calculated=None):
    """Run every family. `calculated` maps an output name to the input names it may depend on."""
    for p in probes:
        if not isinstance(p, dict) or not {"id", "evidence_id", "accepted"} <= p.keys():
            raise ValueError("each probe needs id, evidence_id and accepted")
    fields = sorted({name for p in probes for name in p.get("inputs", {})})
    report = {
        "probes": len(probes),
        "fields": {
            name: {
                "required": required(probes, name),
                "bounds": bounds(probes, name),
                "allowed_values": allowed_values(probes, name),
            }
            for name in fields
        },
        "calculations": {
            output: calculation(probes, output, inputs) for output, inputs in (calculated or {}).items()
        },
        "branches": branches(probes),
        "persistence": persistence(probes),
        "roles": roles(probes),
        "confirmed": 0,
        "note": "Hypotheses are evidence for review; none is promoted to a confirmed rule here.",
    }
    return report
