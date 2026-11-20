"""Reproduce the self-authored order-entry slice using real UIA, PostgreSQL and Playwright."""

import argparse
import json
import os
import platform
import subprocess
import sys
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

from engine.desktop import window_for
from engine.generate import generate
from engine.paired_replay import run_paired
from engine.run_state import atomic_json
from engine.uas import Control, Entity, Evidence, Rule, Screen, UniversalAppSpec, Workflow
from engine.windows_actions import execute_plan
from engine.windows_explorer import explore
from engine.workflow_discovery import build_pair

LOCAL = Path(__file__).resolve().parent
TITLE = "ZZTEST App Twin Order Entry"
ALLOWED = {("fill", name) for name in ("code", "quantity", "unit_price")} | {
    ("click", name) for name in ("entry", "records", "calculate", "save", "confirm_save")
}
PROBES = [
    ("required", "", "2", "7", "Code failed required validation", None),
    ("quantity_min", "ZZTEST_PROBE", "0", "7", "Quantity failed min validation", None),
    ("price_min", "ZZTEST_PROBE", "2", "-1", "Unit price failed min validation", None),
    ("multiply_a", "ZZTEST_PROBE", "2", "7", "Calculated", "14"),
    ("multiply_b", "ZZTEST_PROBE", "3", "7", "Calculated", "21"),
    ("multiply_c", "ZZTEST_PROBE", "3", "11", "Calculated", "33"),
]
INVENTORY = [
    Workflow("calculate", "Calculate order total", weight=3, dimensions=["behavior"]),
    Workflow("required", "Reject empty order code", weight=2, dimensions=["behavior", "ui"]),
    Workflow("quantity_min", "Reject zero quantity", weight=2, dimensions=["behavior"]),
    Workflow("price_min", "Reject negative price", weight=2, dimensions=["behavior"]),
    Workflow(
        "save",
        "Confirm and persist order",
        weight=5,
        permission="fixture-write",
        dimensions=["behavior", "data"],
    ),
    Workflow("reopen", "Read latest order", weight=4, dimensions=["data", "ui"]),
    Workflow(
        "duplicate",
        "Reject duplicate code",
        weight=3,
        permission="fixture-write",
        dimensions=["behavior", "data"],
    ),
]


def wait_until(operation, child):
    deadline = monotonic() + 25
    while monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError(f"fixture/service exited with {child.returncode}; check its log")
        try:
            return operation()
        except (RuntimeError, URLError):
            sleep(0.3)
    raise RuntimeError("fixture or service did not become reachable")


@contextmanager
def process(command, out, *, cwd=None, env=None):
    with out.open("w", encoding="utf-8") as log:
        child = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            yield child
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=15)


def fixture(command, title, log):
    return process(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "RemoteSigned",
            "-STA",
            "-File",
            *command,
            "-Title",
            title,
        ],
        log,
    )


def click(target):
    return {"action": "click", "automation_id": target}


def enter(code, quantity, price):
    return [
        click("entry"),
        *[
            {"action": "fill", "automation_id": field, "value": value}
            for field, value in zip(("code", "quantity", "unit_price"), (code, quantity, price))
        ],
    ]


def prepare(output):
    if platform.system() != "Windows":
        raise RuntimeError("prepare requires a Windows desktop")
    output.mkdir(parents=True, exist_ok=False)
    work = output / "source"
    work.mkdir()
    atomic_json(output / "inventory.json", [vars(item) for item in INVENTORY])
    with fixture(
        [str(LOCAL / "order-entry.ps1"), "-FixtureDirectory", str(work)], TITLE, output / "wpf.log"
    ) as app:
        wait_until(lambda: window_for(TITLE, app.pid), app)
        snapshot = explore(TITLE, output / "wpf.json", pid=app.pid)
        run = partial(
            execute_plan,
            TITLE,
            pid=app.pid,
            allow_mutation=True,
            sandbox_confirmed=True,
            allowed_targets=ALLOWED,
            screenshots=True,
        )
        probe_evidence = {}
        for name, code, count, price, status, total in PROBES:
            file = output / f"probe-{name}.json"
            observations = {"status": "status", **({"total": "total"} if total is not None else {})}
            result = run(
                enter(code, count, price) + [click("calculate")], out_path=file, observations=observations
            )
            expected = {"status": status, **({"total": total} if total is not None else {})}
            if result["values"] != expected:
                raise AssertionError((name, expected, result["values"]))
            probe_evidence[name] = Evidence(
                name, "controlled-uia-probe", file.name, result["observations"][-1]["at"]
            )
        run([click("records")], out_path=output / "navigate.json")
        history = explore(TITLE, output / "records.json", pid=app.pid)
    title = "ZZTEST App Twin WinForms Compatibility"
    with fixture([str(LOCAL / "compatibility.ps1")], title, output / "winforms.log") as app:
        wait_until(lambda: window_for(title, app.pid), app)
        compatibility = explore(title, output / "winforms.json", pid=app.pid)
        roles = {control.get("control_type") for control in compatibility["controls"]}
        if not {"Window", "Edit", "Button"} <= roles:
            raise AssertionError(f"WinForms compatibility missing expected roles: {roles}")
    screens = []
    evidence = list(probe_evidence.values())
    for key, capture, expected in (
        ("entry", snapshot, set(target for _, target in ALLOWED) | {"status", "total"}),
        ("records", history, {"entry", "records", "latest_code", "latest_total"}),
    ):
        ref = f"{key}-uia"
        artifact = "wpf.json" if key == "entry" else "records.json"
        evidence.append(Evidence(ref, "uia", artifact, capture["captured_at"]))
        controls = [
            Control(c["id"], c["control_type"], c["name"], tuple(c["bounds"]), [ref], c["automation_id"])
            for c in capture["controls"]
            if c.get("automation_id") in expected
        ]
        if set(expected) - {control.automation_id for control in controls}:
            raise AssertionError("required controls missing in UIA capture")
        screens.append(Screen(key, key.title(), controls, [ref]))
    spec = UniversalAppSpec(
        "Order Entry",
        screens=screens,
        workflows=INVENTORY,
        evidence=evidence,
        entities=[
            Entity(
                "order_entry",
                "Orders",
                {"code": "text", "quantity": "integer", "unit_price": "integer", "total": "integer"},
                ["entry-uia", "records-uia"],
                unique=["code"],
            )
        ],
        rules=[
            Rule("code", "order_entry", "code", "required", "confirmed", ["required"], confidence=1),
            Rule(
                "quantity",
                "order_entry",
                "quantity",
                "min",
                "confirmed",
                ["quantity_min", "multiply_a"],
                1,
                1,
            ),
            Rule("price", "order_entry", "unit_price", "min", "confirmed", ["price_min", "multiply_a"], 0, 1),
            Rule(
                "total",
                "order_entry",
                "total",
                "multiply",
                "confirmed",
                ["multiply_a", "multiply_b", "multiply_c"],
                ["quantity", "unit_price"],
                1,
            ),
        ],
        unknowns=[
            "Whitespace, pricing limits and behavior outside the seven declared workflows are unmeasured."
        ],
    )
    spec.save(output / "uas.json")
    generate(output / "uas.json", output / "app")


def mapping(spec, code):
    mappings = []
    cases = {
        "calculate": (enter(code, "3", "11") + [click("calculate")], {"status": "text", "total": "number"}),
        "required": (enter("", "2", "7") + [click("calculate")], {"status": "text"}),
        "quantity_min": (enter(code, "0", "7") + [click("calculate")], {"status": "text"}),
        "price_min": (enter(code, "2", "-1") + [click("calculate")], {"status": "text"}),
        "save": (
            enter(code, "3", "11") + [click("save"), click("confirm_save")],
            {"status": "text", "total": "number"},
        ),
        "reopen": ([click("records")], {"latest_code": "exact", "latest_total": "number"}),
        "duplicate": (enter(code, "3", "11") + [click("save"), click("confirm_save")], {"status": "text"}),
    }
    for item in spec.workflows:
        steps, observations = cases[item.id]
        for step in steps:
            if step["automation_id"] in {"confirm_save", "calculate"}:
                step["wait_for_status"] = True
        mappings.append(build_pair(spec, item, steps, observations, approved_fixture=True))
    return mappings


def verify(output, port):
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from engine.fidelity import score

    database = make_url(os.environ["DATABASE_URL"])
    if (
        database.drivername != "postgresql+psycopg"
        or database.host not in {"127.0.0.1", "localhost", "::1"}
        or not (database.database or "").startswith("app_twin_fixture")
    ):
        raise ValueError("demo requires a disposable loopback PostgreSQL database named app_twin_fixture*")
    app = output / "app"
    backend = app / "backend"
    built = app / "frontend" / "dist"
    if not built.is_dir():
        raise RuntimeError("build the generated frontend before verify")
    env = {**os.environ, "TWIN_LOCAL_DEMO": "1", "TWIN_FRONTEND_DIST": str(built)}
    env.pop("TWIN_API_TOKEN", None)
    with (output / "migrations.log").open("w") as log:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend,
            env=env,
            check=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    evidence = output / ("run-" + uuid4().hex[:8])
    evidence.mkdir()
    spec = UniversalAppSpec.load(output / "uas.json")
    code = "ZZTEST_" + evidence.name[4:].upper()
    file = evidence / "mapping.json"
    atomic_json(file, mapping(spec, code))
    source_data = evidence / "source"
    source_data.mkdir()
    url = f"http://127.0.0.1:{port}"
    with (
        fixture(
            [str(LOCAL / "order-entry.ps1"), "-FixtureDirectory", str(source_data)],
            TITLE,
            evidence / "wpf.log",
        ) as source,
        process(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
            evidence / "backend.log",
            cwd=backend,
            env=env,
        ) as service,
    ):
        wait_until(lambda: window_for(TITLE, source.pid), source)

        def health():
            with urlopen(url + "/api/health", timeout=2) as response:
                return json.load(response)

        wait_until(health, service)
        report = run_paired(
            file,
            title=TITLE,
            pid=source.pid,
            url=url,
            output_dir=evidence / "paired",
            allow_mutation=True,
            sandbox_confirmed=True,
            allowed_targets=ALLOWED,
            screenshots=True,
        )
    expected = {"code": code, "quantity": 3, "unit_price": 11, "total": 33}
    persisted_source = json.loads((source_data / "orders.json").read_text(encoding="utf-8-sig"))
    with create_engine(os.environ["DATABASE_URL"]).connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        persisted_twin = [
            dict(row)
            for row in connection.execute(
                text("SELECT code, quantity, unit_price, total FROM order_entry WHERE code = :code"),
                {"code": code},
            ).mappings()
        ]
    data_match = persisted_source == persisted_twin == [expected]
    atomic_json(
        evidence / "persistence.json",
        {"migration": revision, "source": persisted_source, "twin": persisted_twin, "match": data_match},
    )
    for row in report["results"]:
        if row["id"] in {"save", "duplicate", "reopen"} and not data_match:
            row["status"] = "fail"
            row["differences"]["persistence"] = {"reason": "persisted records do not agree"}
    result = score(spec.workflows, report["results"], unknowns=spec.unknowns)
    atomic_json(evidence / "fidelity.json", result)
    return evidence, result


def seeded_repair(output, port, agent):
    from engine.repair_loop import repair_file

    app = output / "app"
    file = app / "backend/rules.py"
    original = file.read_bytes()
    computation = b"product = values[left] * values[right]"
    if original.count(computation) != 1 or computation + b" + 1" in original:
        raise ValueError("unexpected generated calculation")
    try:
        file.write_bytes(original.replace(computation, computation + b" + 1"))
        failed, baseline = verify(output, port)
        if baseline["gate_passed"]:
            raise ValueError("the paired suite failed to detect the seeded defect")

        def regression(_):
            subprocess.run([sys.executable, "-m", "compileall", "-q", "backend"], cwd=app, check=True)
            verified, report = verify(output, port)
            atomic_json(output / "repair-retest.json", {"run": verified.name, "report": report})
            return report

        result = repair_file(
            app,
            "backend/rules.py",
            baseline,
            regression,
            agent=agent,
            journal=output / "repair-journal.json",
            timeout=150,
            max_attempts=1,
        )
        atomic_json(output / "seeded-repair.json", {"seeded_run": failed.name, **result})
        return result
    finally:
        file.write_bytes(original)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "verify", "seed-repair"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--port", type=int, default=5178)
    parser.add_argument("--agent", choices=["auto", "codex", "claude"], default="auto")
    args = parser.parse_args()
    output = args.directory.resolve()
    if args.stage == "prepare":
        prepare(output)
        return 0
    if args.stage == "seed-repair":
        result = seeded_repair(output, args.port, args.agent)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "all_workflows_pass" else 1
    evidence, result = verify(output, args.port)
    print(json.dumps({"evidence": str(evidence), "report": result}, indent=2))
    return 0 if result["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
