"""Generate explicitly evidenced, deterministic field rules without executing arbitrary code."""

import json
import operator
from pathlib import Path

OPERATORS = {"required", "min", "max", "equals", "one_of", "multiply"}
INVALID = {
    "required": lambda value, bound: value is None or value == "",
    "min": lambda value, bound: value is not None and value < bound,
    "max": lambda value, bound: value is not None and value > bound,
    "equals": operator.ne,
    "one_of": lambda value, bound: value not in bound,
}


def validate_rules(rules, entities, evidence_ids):
    known = {e["name"]: e["fields"] for e in entities}
    derived = {
        (rule.get("entity"), rule.get("field")) for rule in rules if rule.get("operator") == "multiply"
    }
    if len(derived) != sum(rule.get("operator") == "multiply" for rule in rules):
        raise ValueError("duplicate calculated field")
    for rule in rules:
        if rule.get("entity") not in known or rule.get("field") not in known[rule["entity"]]:
            raise ValueError("rule references unknown entity or field")
        if rule.get("operator") not in OPERATORS:
            raise ValueError("unsupported rule operator")
        if not rule.get("evidence_ids") or not set(rule["evidence_ids"]) <= set(evidence_ids):
            raise ValueError("rule requires valid supporting evidence")
        if rule.get("status") != "confirmed":
            raise ValueError("only confirmed rules can be enforced")
        if rule["operator"] in ("min", "max") and (
            isinstance(rule.get("value"), bool) or not isinstance(rule.get("value"), (int, float))
        ):
            raise ValueError("numeric threshold required")
        if rule["operator"] == "one_of" and (not isinstance(rule.get("value"), list) or not rule["value"]):
            raise ValueError("one_of requires nonempty list")
        if rule["operator"] == "multiply":
            inputs = rule.get("value")
            fields = known[rule["entity"]]
            if (
                not isinstance(inputs, list)
                or len(inputs) != 2
                or any(
                    not isinstance(key, str)
                    or fields.get(key) != "integer"
                    or (rule["entity"], key) in derived
                    for key in inputs
                )
                or fields[rule["field"]] != "integer"
            ):
                raise ValueError("multiply requires two non-derived integer fields and an integer output")
    return True


def apply_rules(entity, payload, rules):
    errors = []
    for rule in rules:
        if rule["entity"] != entity or rule["operator"] == "multiply":
            continue
        field, op, bound = rule["field"], rule["operator"], rule.get("value")
        value = payload.get(field)
        try:
            invalid = INVALID[op](value, bound)
        except (TypeError, ValueError):
            invalid = True
        if invalid:
            errors.append({"field": field, "rule": op})
    return errors


def calculate(entity, values, rules):
    result = dict(values)
    for rule in rules:
        if rule["entity"] == entity and rule["operator"] == "multiply":
            left, right = rule["value"]
            product = values[left] * values[right]
            if not -2147483648 <= product <= 2147483647:
                raise ValueError("Calculated value exceeds the supported integer range")
            result[rule["field"]] = product
    return result


def export_rules(rule_path, entity_path, evidence_ids, output):
    rules = json.loads(Path(rule_path).read_text(encoding="utf-8"))
    entities = json.loads(Path(entity_path).read_text(encoding="utf-8"))
    validate_rules(rules, entities, evidence_ids)
    p = Path(output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rules, indent=2), encoding="utf-8")
    return {"rules": len(rules), "path": str(p)}
