---
name: snapshot-diff
description: How to snapshot the original app's data (database tables, data files) before and after an action and show exactly what changed. Use whenever you record a task or verify one.
---

# Before/after data snapshot

The point: a screen shows you what the user sees. The snapshot shows you what the
app really did. Both go into every task record.

## 1. Know the data paths
They are listed in docs/raw/data-model.md under "Snapshot paths". If that file does
not exist yet, run the data-sleuth agent first.

## 2. Snapshot before
```bash
python scripts/snapshot_diff.py snapshot before-<task> --paths "<path1>" "<path2>"
```
Paths may be SQLite/DB files, folders, or single files. SQLite files are read with
`mode=ro` and every table is dumped. Other files are hashed and sized.

## 3. Do the action, then snapshot after
```bash
python scripts/snapshot_diff.py snapshot after-<task> --paths "<path1>" "<path2>"
```

## 4. Diff
```bash
python scripts/snapshot_diff.py diff before-<task> after-<task>
```
Prints added, removed and changed rows per table, and changed files. Paste the
summary into the task record under "Data changes". Snapshots live in
`state/snapshots/` and are not committed.

## 5. Other engines
- Access (.mdb/.accdb): copy the file first, then pass the copy. Needs `pyodbc`
  and the Access driver; if not available, export tables to CSV from the app.
- SQL Server Express: use `sqlcmd` or `pyodbc` to dump the tables you care about
  to CSV, then snapshot the CSV folder.
- Firebird/other: export to CSV via the app or a client tool, then snapshot.

## Never
Write to the original app's database. Snapshots are read only.
