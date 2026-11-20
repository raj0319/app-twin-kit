"""Generate a distinct web UI and PostgreSQL API from the supported UAS conventions."""

import json
from dataclasses import asdict
from pathlib import Path

from .rule_engine import validate_rules
from .uas import UniversalAppSpec


def generate(spec_path, destination):
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
    outputs[Path("backend/migrations/versions/0001_initial.py")] = migration(spec.entities)
    for name, content in outputs.items():
        existing = destination / name
        if existing.exists() and existing.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"generated path already contains different content: {existing}")
    for name, content in outputs.items():
        existing = destination / name
        if not existing.exists():
            existing.parent.mkdir(parents=True, exist_ok=True)
            with existing.open("x", encoding="utf-8", newline="\n") as output:
                output.write(content)
    return {
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
