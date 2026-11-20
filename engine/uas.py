"""Universal Application Specification (UAS), stdlib-only and JSON serializable."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

Status = Literal["observed", "inferred", "confirmed", "unknown", "contradicted"]
VERSION = "0.2.0"


@dataclass
class Evidence:
    id: str
    kind: str
    artifact: str
    observed_at: str
    confidence: float = 1.0

    def __post_init__(self):
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass
class Control:
    id: str
    role: str
    name: str
    bounds: tuple[int, int, int, int] | None = None
    evidence_ids: list[str] = field(default_factory=list)
    automation_id: str | None = None


@dataclass
class Screen:
    id: str
    title: str
    controls: list[Control] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class Workflow:
    id: str
    name: str
    steps: list[dict] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    status: Status = "unknown"
    weight: int = 1
    permission: Literal["read", "fixture-write"] = "read"
    dimensions: list[str] = field(default_factory=lambda: ["behavior"])


@dataclass
class Entity:
    id: str
    title: str
    fields: dict[str, str]
    evidence_ids: list[str] = field(default_factory=list)
    unique: list[str] = field(default_factory=list)
    relations: dict[str, str] = field(default_factory=dict)
    # Observed role permissions, e.g. {"read": ["clerk", "manager"], "create": ["manager"]}.
    # Empty means the shared API token guards the entity, as before.
    permissions: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Rule:
    id: str
    entity: str
    field: str
    operator: str
    status: Status = "unknown"
    evidence_ids: list[str] = field(default_factory=list)
    value: str | int | list[str] | None = None
    confidence: float = 0.0


@dataclass
class UniversalAppSpec:
    app_name: str
    source_platform: str = "windows"
    target_platform: str = "web"
    schema_version: str = VERSION
    screens: list[Screen] = field(default_factory=list)
    workflows: list[Workflow] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)

    def validate(self):
        import re

        if self.schema_version != VERSION:
            raise ValueError("unsupported UAS schema version")
        if not self.app_name.strip():
            raise ValueError("app_name is required")
        if self.target_platform != "web":
            raise ValueError("this pipeline targets web applications")
        ids = [e.id for e in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate evidence IDs")
        available = set(ids)
        screens = [s.id for s in self.screens]
        if len(screens) != len(set(screens)):
            raise ValueError("duplicate screen IDs")
        for screen in self.screens:
            controls = [c.id for c in screen.controls]
            if len(controls) != len(set(controls)):
                raise ValueError(f"duplicate control IDs in {screen.id}")
            for obj in [screen, *screen.controls]:
                if not set(obj.evidence_ids) <= available:
                    raise ValueError(f"missing evidence reference on {obj.id}")
        statuses = {"observed", "inferred", "confirmed", "unknown", "contradicted"}
        for collection in (self.workflows, self.entities, self.rules):
            if len({item.id for item in collection}) != len(collection):
                raise ValueError("duplicate workflow, entity or rule ID")
            for item in collection:
                if not item.id or not set(item.evidence_ids) <= available:
                    raise ValueError(f"invalid ID or evidence on {item.id}")
                if getattr(item, "status", "unknown") not in statuses:
                    raise ValueError(f"invalid status on {item.id}")
                if getattr(item, "status", None) == "confirmed" and not item.evidence_ids:
                    raise ValueError(f"confirmed item lacks evidence: {item.id}")
        for entity in self.entities:
            for operation, roles in entity.permissions.items():
                if (
                    operation not in {"read", "create"}
                    or not roles
                    or any(not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", role) for role in roles)
                ):
                    raise ValueError(f"invalid permissions on entity {entity.id}")
        for workflow in self.workflows:
            if (
                type(workflow.weight) is not int
                or workflow.weight < 1
                or workflow.permission not in {"read", "fixture-write"}
                or not workflow.dimensions
                or not set(workflow.dimensions) <= {"behavior", "data", "ui"}
            ):
                raise ValueError(f"invalid inventory entry: {workflow.id}")
        entities = {entity.id: entity for entity in self.entities}
        for entity in self.entities:
            if not all(re.fullmatch(r"[a-z][a-z0-9_]{0,39}", key) for key in [entity.id, *entity.fields]):
                raise ValueError("invalid entity or field identifier")
            if (
                "id" in entity.fields
                or not entity.fields
                or not set(entity.fields.values()) <= {"text", "integer", "boolean"}
                or not set(entity.unique) <= entity.fields.keys()
            ):
                raise ValueError(f"invalid fields on {entity.id}")
            for field_name, target in entity.relations.items():
                if entity.fields.get(field_name) != "integer" or target not in entities:
                    raise ValueError(f"invalid relation on {entity.id}.{field_name}")
        for rule in self.rules:
            if rule.entity not in entities or rule.field not in entities[rule.entity].fields:
                raise ValueError(f"invalid rule target: {rule.id}")
            if not 0 <= rule.confidence <= 1:
                raise ValueError(f"invalid rule confidence: {rule.id}")

    def save(self, path):
        self.validate()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version", "0.1.0") == "0.1.0":
            data["schema_version"] = VERSION
        data["evidence"] = [Evidence(**x) for x in data.get("evidence", [])]
        data["screens"] = [
            Screen(**{**s, "controls": [Control(**c) for c in s.get("controls", [])]})
            for s in data.get("screens", [])
        ]
        data["workflows"] = [Workflow(**w) for w in data.get("workflows", [])]
        data["entities"] = [Entity(**e) for e in data.get("entities", [])]
        data["rules"] = [Rule(**r) for r in data.get("rules", [])]
        spec = cls(**data)
        spec.validate()
        return spec


def timestamp():
    return datetime.now(timezone.utc).isoformat()
