"""Generate a distinct web UI and PostgreSQL API from the supported UAS conventions."""

import json
from dataclasses import asdict
from pathlib import Path

from .rule_engine import validate_rules
from .uas import UniversalAppSpec


def generate(spec_path, destination, *, evolve=False):
    """Write the app. With evolve=True an app generated earlier is updated in place: its migrations stay,
    and one new Alembic revision adds the new entities, fields, unique constraints and relations. Removing
    an entity or field, or changing a type, is refused for review rather than generated."""
    spec = UniversalAppSpec.load(spec_path)
    destination = Path(destination)
    template = Path(__file__).with_name("templates")
    if not spec.entities:
        raise ValueError("generation requires an evidenced domain entity and fields")
    if any(not entity.evidence_ids for entity in spec.entities):
        raise ValueError("each generated entity requires provenance")
    confirmed = [asdict(rule) for rule in spec.rules if rule.status == "confirmed"]
    validate_rules(
        confirmed,
        [{"name": entity.id, "fields": entity.fields} for entity in spec.entities],
        {item.id for item in spec.evidence},
    )
    outputs = {
        file.relative_to(template): file.read_text(encoding="utf-8")
        for file in template.rglob("*")
        if file.is_file() and not {"__pycache__", "node_modules", "dist"} & set(file.parts)
    }
    domain = {
        "title": spec.app_name,
        "entities": [asdict(entity) for entity in spec.entities],
        "rules": confirmed,
        "unknowns": spec.unknowns,
    }
    outputs[Path("backend/domain.json")] = json.dumps(domain, sort_keys=True, indent=2)
    outputs[Path("frontend/src/domain.json")] = json.dumps(domain, sort_keys=True, indent=2)
    outputs[Path("backend/rules.py")] = Path(__file__).with_name("rule_engine.py").read_text(encoding="utf-8")
    versions = destination / "backend/migrations/versions"
    previous = destination / "backend/domain.json"
    replaceable = set()
    evolution = None
    if evolve and previous.is_file():
        old = json.loads(previous.read_text(encoding="utf-8"))["entities"]
        evolution = changes(old, [asdict(entity) for entity in spec.entities])
        existing = sorted(versions.glob("[0-9][0-9][0-9][0-9]_*.py"))
        for file in existing:
            outputs[file.relative_to(destination)] = file.read_text(encoding="utf-8")
        if evolution["steps"]:
            number = len(existing) + 1
            name = Path(f"backend/migrations/versions/{number:04}_evolve.py")
            outputs[name] = evolve_migration(evolution, f"{number:04}", f"{number - 1:04}")
        replaceable = {Path("backend/domain.json"), Path("frontend/src/domain.json")}
    else:
        outputs[Path("backend/migrations/versions/0001_initial.py")] = migration(spec.entities)
    for name, content in outputs.items():
        existing = destination / name
        if existing.exists() and name not in replaceable and existing.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"generated path already contains different content: {existing}")
    for name, content in outputs.items():
        existing = destination / name
        if not existing.exists() or name in replaceable:
            existing.parent.mkdir(parents=True, exist_ok=True)
            with existing.open("w" if name in replaceable else "x", encoding="utf-8", newline="\n") as output:
                output.write(content)
    return {
        **({"evolution": evolution} if evolution is not None else {}),
        "entities": len(spec.entities),
        "confirmed_rules": len(confirmed),
        "unsupported_rules": len(spec.rules) - len(confirmed),
        "output": str(destination),
    }


def migration(entities):
    types = {"text": "sa.String(200)", "integer": "sa.Integer()", "boolean": "sa.Boolean()"}
    lines = [
        '"""Initial generated domain schema."""',
        "from alembic import op",
        "import sqlalchemy as sa",
        "",
        'revision = "0001"',
        "down_revision = None",
        "",
        "",
        "def upgrade():",
    ]
    for entity in entities:
        lines.extend(
            [
                f"    op.create_table({entity.id!r},",
                '        sa.Column("id", sa.Integer(), primary_key=True),',
            ]
        )
        for field, kind in sorted(entity.fields.items()):
            lines.append(f"        sa.Column({field!r}, {types[kind]}, nullable=False),")
        for field in sorted(entity.unique):
            lines.append(f'        sa.UniqueConstraint({field!r}, name="uq_{entity.id}_{field}"),')
        lines.append("    )")
    for entity in entities:
        for field, target in sorted(entity.relations.items()):
            lines.append(
                f'    op.create_foreign_key("fk_{entity.id}_{field}", {entity.id!r}, {target!r}, [{field!r}], ["id"])'
            )
    lines.extend(["", "", "def downgrade():"])
    for entity in entities:
        for field in sorted(entity.relations):
            lines.append(
                f'    op.drop_constraint("fk_{entity.id}_{field}", {entity.id!r}, type_="foreignkey")'
            )
    lines.extend(f"    op.drop_table({entity.id!r})" for entity in reversed(entities))
    return "\n".join(lines) + "\n"


BACKFILL = {"text": "''", "integer": "0", "boolean": "false"}


def changes(old_entities, new_entities):
    """Additive schema changes between two domain models; anything destructive raises for review."""
    old = {entity["id"]: entity for entity in old_entities}
    new = {entity["id"]: entity for entity in new_entities}
    if removed := sorted(old.keys() - new.keys()):
        raise ValueError(f"evolution would drop entities {removed}; review and migrate by hand")
    steps = []
    for key, entity in new.items():
        if key not in old:
            steps.append({"op": "create_table", "entity": entity})
            continue
        before = old[key]
        dropped = sorted(before["fields"].keys() - entity["fields"].keys())
        retyped = sorted(
            f
            for f in before["fields"]
            if f in entity["fields"] and before["fields"][f] != entity["fields"][f]
        )
        if dropped or retyped:
            raise ValueError(f"evolution of {key} would drop {dropped} or retype {retyped}; review by hand")
        for field, kind in sorted(entity["fields"].items()):
            if field not in before["fields"]:
                steps.append(
                    {
                        "op": "add_column",
                        "table": key,
                        "field": field,
                        "kind": kind,
                        "backfill": BACKFILL[kind],
                    }
                )
        for field in sorted(set(entity.get("unique", [])) - set(before.get("unique", []))):
            steps.append({"op": "add_unique", "table": key, "field": field})
        for field, target in sorted(entity.get("relations", {}).items()):
            if field not in before.get("relations", {}):
                steps.append({"op": "add_relation", "table": key, "field": field, "target": target})
    return {"steps": steps, "backfilled": [step for step in steps if step["op"] == "add_column"]}


class _Entity:
    """Attribute view of an entity dict, for migration()."""

    def __init__(self, data):
        self.id = data["id"]
        self.fields = data["fields"]
        self.unique = data.get("unique", [])
        self.relations = data.get("relations", {})


def evolve_migration(evolution, revision, down_revision):
    types = {"text": "sa.String(200)", "integer": "sa.Integer()", "boolean": "sa.Boolean()"}
    up, down = [], []
    for step in evolution["steps"]:
        if step["op"] == "create_table":
            entity = step["entity"]
            body = (
                migration([_Entity(entity)])
                .split("def upgrade():\n", 1)[1]
                .split("\n\n\ndef downgrade", 1)[0]
            )
            up.append(body.rstrip())
            down.insert(0, f"    op.drop_table({entity['id']!r})")
        elif step["op"] == "add_column":
            table, field, kind = step["table"], step["field"], step["kind"]
            up.append(
                f"    op.add_column({table!r}, sa.Column({field!r}, {types[kind]}, nullable=False, "
                f"server_default=sa.text({step['backfill']!r})))"
            )
            down.insert(0, f"    op.drop_column({table!r}, {field!r})")
        elif step["op"] == "add_unique":
            name = f"uq_{step['table']}_{step['field']}"
            up.append(f"    op.create_unique_constraint({name!r}, {step['table']!r}, [{step['field']!r}])")
            down.insert(0, f"    op.drop_constraint({name!r}, {step['table']!r}, type_='unique')")
        elif step["op"] == "add_relation":
            name = f"fk_{step['table']}_{step['field']}"
            up.append(
                f"    op.create_foreign_key({name!r}, {step['table']!r}, {step['target']!r}, "
                f"[{step['field']!r}], ['id'])"
            )
            down.insert(0, f"    op.drop_constraint({name!r}, {step['table']!r}, type_='foreignkey')")
    lines = [
        '"""Generated additive schema evolution; new columns are backfilled with the listed defaults."""',
        "from alembic import op",
        "import sqlalchemy as sa",
        "",
        f"revision = {revision!r}",
        f"down_revision = {down_revision!r}",
        "",
        "",
        "def upgrade():",
        *up,
        "",
        "",
        "def downgrade():",
        *down,
    ]
    return "\n".join(lines) + "\n"
