"""Import existing scripts/ui_tree.py Markdown captures into UAS without changing the source."""

import argparse
import hashlib
import re
from pathlib import Path

from .uas import Control, Evidence, Screen, UniversalAppSpec, timestamp

BOUNDS = re.compile(r"^(-?\d+),(-?\d+)\s+(\d+)x(\d+)$")


def import_capture(path: Path, root: Path) -> tuple[Screen, Evidence]:
    raw = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    evidence_id = f"capture-{digest[:16]}"
    title_match = re.search(r"^Window:\s*(.+?)\s*$", raw, re.M)
    title = title_match.group(1).strip() if title_match else path.stem
    controls = []
    for line in raw.splitlines():
        if not line.startswith("|"):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) != 5 or not parts[0].isdigit():
            continue
        _, role, name, automation_id, position = parts
        bounds_match = BOUNDS.match(position)
        bounds = tuple(map(int, bounds_match.groups())) if bounds_match else None
        control_id = automation_id or f"control-{len(controls):04d}"
        controls.append(Control(control_id, role, name, bounds, [evidence_id]))
    relative = path.relative_to(root).as_posix()
    return (
        Screen(path.stem, title, controls, [evidence_id]),
        Evidence(evidence_id, "windows-uia-markdown", relative, timestamp()),
    )


def build_spec(app_name: str, capture_dir: Path, root: Path) -> UniversalAppSpec:
    spec = UniversalAppSpec(app_name)
    for path in sorted(capture_dir.glob("*.md")):
        if path.name.endswith((".live.md", ".watcher.md")):
            continue
        screen, evidence = import_capture(path, root)
        spec.screens.append(screen)
        spec.evidence.append(evidence)
    spec.validate()
    return spec


def main():
    parser = argparse.ArgumentParser(description="Convert existing Windows UI captures to UAS")
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--captures", default="docs/raw/screens")
    parser.add_argument("--out", default="docs/spec/uas.json")
    args = parser.parse_args()
    root = Path.cwd()
    spec = build_spec(args.app_name, (root / args.captures).resolve(), root)
    spec.save(args.out)
    print(f"Wrote {len(spec.screens)} screens and {len(spec.evidence)} evidence records to {args.out}")


if __name__ == "__main__":
    main()
