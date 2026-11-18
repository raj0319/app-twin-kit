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
python scripts/ui_tree.py --title "<part of window title>" --out docs/raw/screens/<screen-name>.md --screenshot
```
Writes a Markdown file with every control (type, name, automation id, position)
and one PNG of the window next to it. The positions are what the twin's layout is
copied from (`scripts/layout.py`); the PNG is the layout reference for the designer.
Keep the window at its normal size while dumping. Add `--depth 6` for very large screens.
Screens exported by App Watcher already have both (pictures in `docs/raw/screens/shots/`).

## 3. If the tree is empty or useless
Some apps (old VB6, Java, custom-drawn, some Delphi) do not expose controls.
Then:
- Read the PNG and describe the controls by eye, with their approximate
  position and size in pixels, in a control tree table of the same format, so
  `scripts/layout.py` can still use it.
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
