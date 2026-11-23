"""Source-side check of the Mini ERP fixture against EXPECTED.md (worked example), through allowlisted UIA.

python -m fixtures.windows.mini_erp_demo state/mini-erp-run
Builds the fixture if needed, runs it in a new disposable data folder, and compares what the screens show
with the expected numbers.
"""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from engine.desktop import window_for
from engine.run_state import atomic_json
from engine.windows_actions import allow_key, execute_plan

from .demo import wait_until

ROOT = Path(__file__).resolve().parent / "mini-erp"
EXE = ROOT / "bin" / "out" / "MiniErp.exe"
TITLE = "ZZTEST Mini ERP - Main - admin"
DOTNET = Path.home() / ".dotnet" / "dotnet.exe"


def fill(target, value):
    return {"action": "fill", "automation_id": target, "value": value}


def click(target):
    return {"action": "click", "automation_id": target}


def pick(target, value):
    return {"action": "select", "automation_id": target, "value": value}


def menu(*path):
    return {"action": "menu", "path": list(path)}


def tab(name):
    return {"action": "tab", "automation_id": "tabs", "value": name}


def observe(target):
    return {"action": "observe", "automation_id": target}


WORKED_EXAMPLE = [
    tab("Items"),
    click("itemNew"),
    fill("itemCode", "A"),
    fill("itemName", "Item A"),
    fill("itemPrice", "100"),
    pick("itemTax", "18"),
    fill("itemStock", "10"),
    click("itemSave"),
    click("itemNew"),
    fill("itemCode", "B"),
    fill("itemName", "Item B"),
    fill("itemPrice", "45.50"),
    pick("itemTax", "5"),
    fill("itemStock", "5"),
    click("itemSave"),
    tab("Customers"),
    click("custNew"),
    fill("custCode", "C1"),
    fill("custName", "Customer One"),
    click("custSave"),
    tab("Invoice"),
    click("invNew"),
    fill("invDate", "2026-11-20"),
    pick("invCustomer", "C1"),
    fill("invDocDiscount", "5"),
    pick("lineItem", "A"),
    fill("lineQty", "3"),
    fill("lineDiscount", "10"),
    click("addLine"),
    pick("lineItem", "B"),
    fill("lineQty", "2"),
    fill("lineDiscount", "0"),
    click("addLine"),
    click("invSave"),
    observe("invNumber"),
    observe("invSubtotal"),
    observe("invDiscount"),
    observe("invTax"),
    observe("invTotal"),
    click("invConfirm"),
    click("invPost"),
    observe("invStatus"),
    tab("Ledger"),
    click("refreshLedger"),
    observe("ledgerCheck"),
    observe("status"),
]
EXPECTED = {
    "invNumber": "INV-2026-0001",
    "invSubtotal": "361.00",
    "invDiscount": "18.05",
    "invTax": "50.49",
    "invTotal": "393.44",
    "invStatus": "Posted",
    "ledgerCheck": "Balanced",
}


def build():
    if EXE.is_file():
        return
    subprocess.run(
        [str(DOTNET), "build", "-c", "Release", "-o", str(EXE.parent)],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )


def run_once(output):
    data = Path(tempfile.mkdtemp(prefix="data-", dir=output))
    allowed = {(step["action"], allow_key(step)) for step in WORKED_EXAMPLE if step["action"] != "observe"}
    # The .NET runtime may live only in the user profile; point the app at it instead of installing anything.
    env = {**os.environ, "DOTNET_ROOT": os.environ.get("DOTNET_ROOT", str(DOTNET.parent))}
    process = subprocess.Popen(
        [str(EXE), "--data", str(data), "--user", "admin", "--company", "Main"], env=env
    )
    try:
        wait_until(lambda: window_for(TITLE, process.pid), process)
        trace = execute_plan(
            TITLE,
            WORKED_EXAMPLE,
            pid=process.pid,
            allow_mutation=True,
            sandbox_confirmed=True,
            allowed_targets=allowed,
            out_path=data / "trace.json",
        )
    finally:
        process.terminate()
        process.wait(15)
    seen = {e["automation_id"]: e.get("value") for e in trace["observations"] if e["action"] == "observe"}
    stored = json.loads((data / "erp.json").read_text(encoding="utf-8"))["Companies"]["Main"]
    stock = {i["Code"]: i["Stock"] for i in stored["Items"]}
    ledger = {e["Account"]: (e["Debit"], e["Credit"]) for e in stored["Ledger"]}
    mismatches = {k: (v, seen.get(k)) for k, v in EXPECTED.items() if seen.get(k) != v}
    data_ok = stock == {"A": 7, "B": 3} and ledger == {
        "Receivable": (393.44, 0),
        "Sales": (0, 342.95),
        "Tax": (0, 50.49),
    }
    return {
        "evidence": str(data),
        "seen": seen,
        "mismatches": mismatches,
        "stock": stock,
        "ledger": ledger,
        "passed": not mismatches and data_ok,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    output = args.directory.resolve()
    output.mkdir(parents=True, exist_ok=False)
    build()
    runs = [run_once(output) for _ in range(max(1, min(args.repeat, 10)))]
    report = {"runs": runs, "passed": sum(r["passed"] for r in runs), "total": len(runs)}
    atomic_json(output / "report.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
