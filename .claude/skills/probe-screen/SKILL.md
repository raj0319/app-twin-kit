---
name: probe-screen
description: How to learn a screen's behaviour by typing test values into its search, filter and form fields and reading what comes back. Use in DISCOVER mode whenever a screen has input fields.
---

# Probe a screen

The explorer tells you what is on a screen. Probing tells you what it does.

## 1. Pick example values from real data
Read docs/raw/data-model.md. Use a value you know exists (a real customer name),
one that does not, a partial one, and a wrong type.

## 2. One try per command
```bash
python scripts/probe.py --title "<window>" --field "Search" --value "Acme" --enter --out docs/raw/probes/customers.md
python scripts/probe.py --title "<window>" --field "Search" --value "acm" --enter --out docs/raw/probes/customers.md
python scripts/probe.py --title "<window>" --field "Search" --value "zzzz" --enter --out docs/raw/probes/customers.md
python scripts/probe.py --title "<window>" --field "Search" --value "" --enter --out docs/raw/probes/customers.md
```
Each run appends: the input, how many result items appeared, the first few, and
any dialog or message. It closes dialogs it caused and clears the field.

## 3. Read the file, write rules
Open docs/raw/probes/<screen>.md, compare the tries, and write the "Rules learned"
section in plain lines. Copy those lines into docs/rules.md under the screen name.

## 4. Where probing is not allowed
- Fields on the do-not-touch list in state/project.json.
- Any screen where Enter means Save or Post. Check the screen record's actions first.
- Payment, email, SMS, and printing screens.

## 5. If the field is not found
The script searches by label and AutomationId. Try the AutomationId from the
screen record, or a shorter part of the label. If still nothing, note it as
"needs vision" and move on.
