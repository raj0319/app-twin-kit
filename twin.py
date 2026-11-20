"""Command-line entry point for Windows capture, twin generation and verification."""

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "start",
            "resume",
            "status",
            "doctor",
            "models",
            "list-windows",
            "capture",
            "record-windows",
            "trace-windows",
            "analyze-transitions",
            "import-legacy",
            "infer-rules",
            "generate",
            "propose-mappings",
            "audit-mappings",
            "approve-mappings",
            "paired-replay",
            "repair",
            "release-gate",
            "discover-tools",
            "inspect-compat",
        ],
    )
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("--agent", choices=["auto", "codex", "claude"])
    parser.add_argument("--title", help="Exact title of the source application window")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--spec", type=Path, default=Path("state/twin/uas.json"))
    parser.add_argument("--mapping", type=Path, default=Path("state/twin/mapping.json"))
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    parser.add_argument("--seconds", type=int, default=15)
    parser.add_argument("--snapshots", type=Path, nargs="+")
    parser.add_argument("--approve-ids", nargs="+")
    parser.add_argument(
        "--fixture-consent", action="store_true", help="Permit only listed actions on a disposable fixture"
    )
    parser.add_argument("--allow", action="append", default=[], metavar="ACTION=AUTOMATION_ID")
    parser.add_argument("--screenshots", action="store_true")
    parser.add_argument("--agent-timeout", type=int, default=900)
    parser.add_argument("--max-agent-calls", type=int, default=6)
    parser.add_argument("--repair-file", type=Path, help="Generated file relative to the app directory")
    parser.add_argument("--report", type=Path, help="Baseline JSON report, refreshed by verification")
    parser.add_argument(
        "--verify-command",
        nargs=argparse.REMAINDER,
        help="Executable and arguments for regression checks, placed last",
    )
    args = parser.parse_args(argv)
    try:
        result, code = dispatch(args)
    except (ValueError, RuntimeError, OSError, ImportError) as exc:
        parser.exit(1, f"twin: {exc}\n")
    print(json.dumps(result, indent=2))
    return code


def dispatch(args):
    root = args.root.resolve()
    state = root / "state" / "twin"
    command = args.command
    spec = root / args.spec
    mapping = root / args.mapping

    def output(default):
        return root / args.output if args.output else state / default

    def allowed():
        if any("=" not in item for item in args.allow):
            raise ValueError("--allow expects ACTION=AUTOMATION_ID")
        return {tuple(item.split("=", 1)) for item in args.allow}

    if command in {"start", "resume", "status"}:
        from engine.orchestrator import execute, status

        if command == "status":
            return status(root), 0
        return execute(
            root,
            title=args.title,
            pid=args.pid,
            agent=args.agent,
            resume=command == "resume",
            timeout=args.agent_timeout,
            calls=args.max_agent_calls,
        ), 0
    if command in {"doctor", "discover-tools"}:
        from engine.diagnostics import doctor, tools

        return (doctor(args.agent or "auto") if command == "doctor" else tools(root)), 0
    if command == "models":
        from engine.agents.runner import models

        provider = args.agent if args.agent not in {None, "auto"} else "codex"
        return {"provider": provider, "models": models(provider)}, 0
    if command == "list-windows":
        from engine.desktop import list_windows

        return list_windows(), 0
    if command == "capture":
        from engine.windows_explorer import explore

        return explore(args.title, output("capture.json"), pid=args.pid), 0
    if command == "record-windows":
        from engine.windows_recorder import record_window

        return record_window(args.title, output("recording.json"), pid=args.pid, seconds=args.seconds), 0
    if command == "trace-windows":
        from engine.windows_actions import execute_plan

        if not args.report:
            raise ValueError("--report supplies a JSON list of bounded source actions")
        plan = json.loads((root / args.report).read_text(encoding="utf-8"))
        return execute_plan(
            args.title,
            plan,
            pid=args.pid,
            allow_mutation=args.fixture_consent,
            sandbox_confirmed=args.fixture_consent,
            allowed_targets=allowed(),
            screenshots=args.screenshots,
            out_path=output("trace.json"),
        ), 0
    if command == "inspect-compat":
        from engine.windows_compat import inspect

        return inspect(args.title, output("compatibility-controls.json")), 0
    if command == "analyze-transitions":
        from engine.workflow_capture import analyze_files

        return analyze_files([root / item for item in args.snapshots or []], output("transitions.json")), 0
    if command == "import-legacy":
        from engine.windows_import import build_spec

        if not args.title:
            raise ValueError("--title supplies the app name")
        imported = build_spec(args.title, root / "docs/raw/screens", root)
        imported.save(output("uas.json"))
        return {"screens": len(imported.screens)}, 0
    if command == "generate":
        from engine.generate import generate

        return generate(spec, output("app")), 0
    if command == "infer-rules":
        from engine.rule_probes import save

        if not args.report:
            raise ValueError("--report supplies controlled experiment JSON")
        return save(root / args.report, output("rule-candidates.json")), 0
    if command == "propose-mappings":
        from engine.workflow_discovery import propose_pairs

        return propose_pairs(spec, output("proposals.json")), 0
    if command == "approve-mappings":
        from engine.workflow_approval import approve

        return approve(state / "proposals.json", args.approve_ids or [], mapping), 0
    if command == "audit-mappings":
        from engine.workflow_pair import load_pairs
        from engine.workflow_quality import audit

        result = audit(load_pairs(mapping, allow_proposed=True))
        return result, 0 if result["ready"] else 1
    if command == "paired-replay":
        from engine.paired_replay import run_paired

        result = run_paired(
            mapping,
            title=args.title,
            pid=args.pid,
            url=args.url,
            output_dir=output("paired"),
            allow_mutation=args.fixture_consent,
            sandbox_confirmed=args.fixture_consent,
            screenshots=args.screenshots,
            allowed_targets=allowed(),
        )
        return result, 0 if result["total"] and result["passed"] == result["total"] else 1
    if command == "repair":
        import subprocess

        from engine.repair_loop import repair_file

        if not (args.repair_file and args.report and args.verify_command):
            raise ValueError("repair requires --repair-file, --report and --verify-command")
        report_file = root / args.report

        def read():
            return json.loads(report_file.read_text(encoding="utf-8"))

        def verify(_):
            previous = report_file.stat().st_mtime_ns
            completed = subprocess.run(args.verify_command, cwd=root, timeout=args.agent_timeout, check=False)
            if completed.returncode or report_file.stat().st_mtime_ns == previous:
                raise RuntimeError("regression command failed or did not write fresh paired evidence")
            return read()

        result = repair_file(
            output("app"),
            args.repair_file,
            read(),
            verify,
            agent=args.agent or "auto",
            timeout=args.agent_timeout,
            journal=state / "repair.json",
        )
        return result, 0 if result["status"] in {"all_workflows_pass", "no_failed_workflows"} else 1
    from engine.release import gate

    result = gate(spec, output("release.json"))
    return result, 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
