"""Confirm (or reject) the spec's calculated-column and numbering rules against real data (improvement #7).

App Watcher watches for days; its snapshots/before.json (or a folder of CSV exports, or an ODBC/drop-folder
dump) holds many rows. This runs the same simple checks the watcher's learner does, over all of that data, so
a rule the spec marks UNCONFIRMED can be confirmed or rejected before a user ever tests the twin.

  python scripts/confirm_rules.py <snapshot.json | folder-of-csv> [--rules docs/rules.md] [--out docs/verify/rules-confirmed.md] [--tol 0.005]

Checks per numeric column C of each table: copy of another column; product A*B; percentage A*p (p from the
common tax/discount rates and any rate that fits); and per column, a dense +1 numbering sequence. Sum-of-children
and status flows need table relations and are left to VERIFY mode. Confirmed = holds for >=95% of the rows.
"""
import argparse
import csv
import glob
import json
import os
import re
import sys

COMMON_RATES = [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.075, 0.0825]


def num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if s and s[0] in "$€£":
        s = s[1:]
    try:
        return float(s)
    except ValueError:
        return None


def load_tables(path):
    """Returns {table: {"columns":[...], "rows":[{col:val}]}} from App Watcher before.json or a CSV folder."""
    tables = {}
    if os.path.isdir(path):
        for f in sorted(glob.glob(os.path.join(path, "*.csv")) + glob.glob(os.path.join(path, "*.tsv"))):
            name = os.path.splitext(os.path.basename(f))[0]
            with open(f, encoding="utf-8-sig", newline="") as fh:
                sample = fh.read(4096)
                fh.seek(0)
                delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter if sample.strip() else ","
                r = list(csv.reader(fh, delimiter=delim))
            if not r:
                continue
            cols = [c.strip() or f"col{i+1}" for i, c in enumerate(r[0])]
            rows = [{cols[i]: (row[i] if i < len(row) else "") for i in range(len(cols))} for row in r[1:]]
            tables[name] = {"columns": cols, "rows": rows}
        return tables
    data = json.load(open(path, encoding="utf-8"))
    dbs = data.get("Databases") or data.get("databases") or {}
    for db, ts in dbs.items():
        dbshort = os.path.basename(str(db).replace("sqlserver:", ""))
        for tname, t in ts.items():
            cols = t.get("Columns") or t.get("columns") or []
            rowmap = t.get("Rows") or t.get("rows") or {}
            rows = list(rowmap.values()) if isinstance(rowmap, dict) else rowmap
            tables[f"{dbshort} / {tname}"] = {"columns": cols, "rows": rows}
    return tables


def numeric_columns(t):
    cols = {}
    for c in t["columns"]:
        vals = [num(r.get(c)) for r in t["rows"]]
        got = [v for v in vals if v is not None]
        if len(got) >= 5 and len(got) >= 0.6 * len(t["rows"]):
            cols[c] = vals
    return cols


def close(a, b, tol):
    if a is None or b is None:
        return False
    if abs(a - b) <= 0.01:
        return True
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom <= tol


def pct(hits, total):
    return 0 if total == 0 else round(100.0 * hits / total)


def check_table(name, t, tol):
    findings = []
    nums = numeric_columns(t)
    n = len(t["rows"])
    names = list(nums)
    for c in names:
        cv = nums[c]
        rows_with_c = [i for i in range(n) if cv[i] is not None]
        if len(rows_with_c) < 5:
            continue
        # copy of another column
        for a in names:
            if a == c:
                continue
            av = nums[a]
            hits = sum(1 for i in rows_with_c if close(cv[i], av[i], tol))
            if pct(hits, len(rows_with_c)) >= 95:
                findings.append((f"{name}.{c}", f"copy of {a}", hits, len(rows_with_c)))
                break
        # product A*B
        done = False
        for i_a in range(len(names)):
            for i_b in range(i_a, len(names)):
                a, b = names[i_a], names[i_b]
                if c in (a, b):
                    continue
                av, bv = nums[a], nums[b]
                hits = sum(1 for i in rows_with_c if av[i] is not None and bv[i] is not None and close(cv[i], av[i] * bv[i], tol))
                if pct(hits, len(rows_with_c)) >= 95:
                    findings.append((f"{name}.{c}", f"{a} * {b}", hits, len(rows_with_c)))
                    done = True
                    break
            if done:
                break
        # percentage A*p
        if not done:
            for a in names:
                if a == c:
                    continue
                av = nums[a]
                pairs = [(cv[i], av[i]) for i in rows_with_c if av[i] not in (None, 0)]
                if len(pairs) < 5:
                    continue
                seen_rate = round(sum(x / y for x, y in pairs) / len(pairs), 4)
                for p in {seen_rate, *COMMON_RATES}:
                    if p <= 0:
                        continue
                    hits = sum(1 for x, y in pairs if close(x, y * p, tol))
                    if pct(hits, len(pairs)) >= 95:
                        findings.append((f"{name}.{c}", f"{a} * {p:g} ({p*100:g}%)", hits, len(pairs)))
                        done = True
                        break
                if done:
                    break
        # dense +1 numbering sequence
        ints = sorted({int(v) for v in cv if v is not None and float(v).is_integer()})
        if len(ints) >= 5 and (ints[-1] - ints[0] + 1) and len(ints) / (ints[-1] - ints[0] + 1) >= 0.9:
            findings.append((f"{name}.{c}", "numbering sequence (dense, +1 per row)", len(ints), len(ints)))
    return findings


def spec_rules(rules_path):
    """Pulls the calculated-column and sequence lines out of docs/rules.md (or memory/rules.md)."""
    rules = []
    if not rules_path or not os.path.exists(rules_path):
        return rules
    for line in open(rules_path, encoding="utf-8"):
        t = line.strip()
        m = re.match(r"- `([^`]+)`\.(\S+):", t)
        if m and ("explains" in t or "increases by one" in t or "UNCONFIRMED" in t.upper() or "calcul" in t.lower()):
            rules.append({"table": m.group(1), "column": m.group(2).strip("`"), "text": t})
    return rules


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--rules")
    ap.add_argument("--out")
    ap.add_argument("--tol", type=float, default=0.005)
    a = ap.parse_args()
    tables = load_tables(a.data)
    if not tables:
        print("No tables found in " + a.data)
        return 1
    all_found = []
    for name, t in tables.items():
        all_found += check_table(name, t, a.tol)

    out = ["# Rules confirmed from data", "",
           f"Checked {len(tables)} tables from `{a.data}`. A rule is confirmed when it holds for 95% or more of the rows.",
           "Sum-of-children and status flows need table relations and are checked in VERIFY mode, not here.", "",
           "## Found in the data", ""]
    if all_found:
        out.append("| Column | Rule | Holds for |")
        out.append("|---|---|---|")
        for col, rule, hits, tot in all_found:
            out.append(f"| `{col}` | {rule} | {hits} of {tot} rows |")
    else:
        out.append("_No copy, product, percentage or sequence rule held for 95% of the rows._")

    rules = spec_rules(a.rules)
    if rules:
        out += ["", "## The spec's rules, against this data", ""]
        found_cols = {c.lower(): r for c, r, _, _ in all_found}
        for r in rules:
            key = f"{r['table']}.{r['column']}".lower()
            hit = next((v for k, v in found_cols.items() if k.endswith(r['column'].lower()) and r['table'].split('/')[-1].strip().lower() in k), None)
            status = f"CONFIRMED ({hit})" if hit else "NOT FOUND in this data (keep UNCONFIRMED; test in a flow run)"
            out.append(f"- `{r['table']}`.{r['column']}: {status}")

    text = "\n".join(out) + "\n"
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        open(a.out, "w", encoding="utf-8").write(text)
        print(f"Wrote {a.out}: {len(all_found)} rules confirmed from {len(tables)} tables.")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
