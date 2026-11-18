---
name: observe-app
description: How to open the original desktop app, read its UI Automation control tree, take a screenshot, and log the screen in the standard format. Use whenever you need to look at a screen of the original app.
---

# Observe a screen of the original app

## 1. Find the window
```bash
python scripts/ui_tree.py --list
```
Prints every top-level window title and process. Pick the one from state/project.json.

## 2. Dump the control tree
```bash
python scripts/ui_tree.py --title "<part of window title>" --out docs/raw/screens/<screen-name>.md
```
Writes a Markdown file with every control (type, name, automation id, position).
No screenshot is taken by default: the twin is built from the control tree, the
data and the probes, not from pictures. Add `--depth 6` for very large screens.

## 3. If the tree is empty or useless
Some apps (old VB6, Java, custom-drawn, some Delphi) do not expose controls.
Then:
- Re-run with `--screenshot` so there is evidence, and read the PNG. Describe
  the controls by eye.
- Use a Windows computer-use MCP server (for example Windows-MCP) to see and
  click, if installed. Note in docs/decisions.md that this app needs vision mode.
- Use the app's own help (F1, Help menu) and any PDF manual in the install folder.
  Manuals list every screen and field.

## 4. Fill the record
Copy docs/templates/screen.md into the output file if the script did not already,
and fill every section. One file per screen or dialog. Name files after the menu
path, for example `sales-invoice-new.md`.

## 5. Do not
- Press anything that saves, posts, sends, prints to a real printer, or deletes.
- Change settings in the original app.
