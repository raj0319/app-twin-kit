# Mini ERP: expected behaviour (ground truth)

Self-authored, disposable WinForms fixture. All data lives in `erp.json` inside
the folder passed with `--data`. Nothing is licensed and nothing leaves that
folder. The twin is measured against this file and
`docs/inventory/erp-capabilities.json`, never against itself.

Start: `MiniErp.exe --data <folder> [--user admin|clerk --company Main|Branch]`.
Without `--user`/`--company`, the login window "ZZTEST Mini ERP Login" opens
first. The main window title is `ZZTEST Mini ERP - <company> - <user>`.

## Screens and automation IDs

| Tab (id) | Controls |
|---|---|
| Customers (`customersPage`) | `custCode`, `custName`, `custGstin`, `custCredit`, `custNew`, `custSave`, `custDelete`, grid `customers` |
| Items (`itemsPage`) | `itemCode`, `itemName`, `itemPrice`, `itemTax` (0/5/12/18), `itemStock`, `itemNew`, `itemSave`, grid `items` |
| Invoice (`invoicePage`) | `invNumber`, `invStatus`, `invDate`, `invCustomer`, `invDocDiscount`, `lineItem`, `lineQty`, `lineDiscount`, `addLine`, `updateLine`, `removeLine`, grid `lines`, `invSubtotal`, `invDiscount`, `invTax`, `invTotal`, `invNew`, `invSave`, `invConfirm`, `invPost`, `invCancel` |
| Invoices (`listPage`) | `search`, `statusFilter`, `sortBy`, `searchButton`, grid `invoiceList`, `prevPage`, `nextPage`, `page`, `openInvoice` |
| Sales report (`reportPage`) | `refreshReport`, grid `salesReport`, `reportTotal` |
| Ledger (`ledgerPage`) | `refreshLedger`, grid `ledger`, `ledgerCheck` |
| Admin (`adminPage`) | `closeDate`, `closePeriod`, `closedThrough` |
| Audit log (`auditPage`) | grid `audit` (newest first) |

Every window also has: menu `File` (Export invoices CSV, Print invoice PDF,
Import customers, Exit), `Masters` (Customers, Items), `Sales` (New invoice,
Invoice list), `Reports` (Sales by customer, Ledger), `Admin` (Close period,
Audit log). The toolbar has New invoice, Save and Post. Ctrl+S saves the
current tab and Ctrl+N starts a new invoice. The `status` line shows the last
result. Every refused action also shows a "Mini ERP" message box with the
same text.

## Rules (messages are exact)

**Customers.**
- Code is required ("Customer code is required").
- Code may use A-Z, 0-9, - and _ only ("Customer code may use A-Z, 0-9, - and _ only").
- New codes must be unique ("Customer code already exists").
- Name is required ("Customer name is required").
- GSTIN is optional, but when given it must match `^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$` ("GSTIN format is invalid").
- Credit limit must be 0 or more ("Credit limit must be 0 or more"); 0 means no limit.
- Delete asks "Delete customer X?" (dialog "Confirm delete", Yes/No). It is admin only ("Your role cannot delete customers") and refused when the customer is on an invoice ("Customer is used on invoices and cannot be deleted").

**Items.**
- Code: same rules as customers ("Item code ...").
- Price must be 0 or more ("Price must be 0 or more").
- Tax rate is one of 0, 5, 12 or 18.
- Opening stock must be 0 or more ("Stock must be 0 or more"). It is set only when the item is created.

**Invoice lines.**
- Pick an item ("Select an item").
- Quantity must be 1 or more ("Quantity must be 1 or more").
- Line discount must be 0–100 ("Discount must be between 0 and 100").
- Price and tax rate are copied from the item when the line is added.

**Header.**
- Date is entered as yyyy-MM-dd ("Date must be yyyy-MM-dd").
- A customer is required ("Select a customer").
- At least one line is required ("Add at least one line").
- Document discount must be 0–50 ("Document discount must be between 0 and 50").

**Maths.** Every value is rounded half away from zero to 2 decimals.
- `net = round(qty * price * (1 - lineDisc/100))`
- `subtotal = sum(net)`
- `docShare = round(net * docDisc/100)`, and `discount = sum(docShare)`
- `lineTax = round((net - docShare) * rate/100)`, and `tax = sum(lineTax)`
- `total = subtotal - discount + tax`

**Numbering.** `INV-<year of invoice date>-<0001...>`, one sequence per company
and year, assigned on the first save. Numbers are never reused, including
after a cancel.

**Status flow.**
- *Save draft:* only drafts can be changed ("Only draft invoices can be changed").
- *Draft → Confirmed (Confirm):* only drafts can be confirmed ("Only draft invoices can be confirmed"). If the credit limit is above 0 and posted totals for the customer plus this total would exceed it, Confirm is refused ("Credit limit exceeded for CODE").
- *Confirmed → Posted (Post):* admin only ("Your role cannot post invoices"). A draft gives "Confirm the invoice before posting", and other states give "Only confirmed invoices can be posted". A date on or before the closed-through date gives "Period is closed for this date". Each item needs enough stock ("Not enough stock for CODE"). Posting reduces stock, writes stock moves, and writes Receivable debit = total, Sales credit = subtotal - discount, and Tax credit = tax.
- *Any → Cancelled (Cancel invoice):* asks "Cancel invoice N?" (dialog "Confirm cancel", Yes/No). A cancelled invoice gives "Invoice is already cancelled". Cancelling a posted invoice is admin only ("Your role cannot cancel posted invoices") and is also blocked by the period lock. It restores stock and adds reversing ledger entries.

**Periods.** Admin > Close period closes through the end of the month of the
date entered. It is admin only ("Your role cannot close periods").

**Companies.** "Main" and "Branch" keep fully separate customers, items,
invoices, sequences, ledgers and audit logs.

**List.** Search matches the invoice number or customer code. The status
filter is All, Draft, Confirmed, Posted or Cancelled. Sort by Number
(ascending), Date, Customer, or Total (descending), with ties broken by
number. There are 5 rows per page, and the page label reads
"Page P of N (C invoices)".

**Report.** The sales report shows posted invoices only, one row per customer
(code, count, total) sorted by code, and a grand total.

**Ledger.** It shows balances per account. `ledgerCheck` reads "Balanced" when
debits equal credits.

**Files.** All files are written to the data folder:
- Export: `invoices-<company>.csv` with Number, Date, Customer, Status, Subtotal, Discount, Tax and Total.
- Print: `<number>.pdf` through "Microsoft Print to PDF", with no dialog.
- Import: reads `import-customers.csv` (Code,Name,GSTIN,CreditLimit plus a header row), adds valid rows, writes `import-report.txt` with "Line N: message" for each rejected row, and the status reads "Imported X, rejected Y".

**Audit.** Every save, create, confirm, post, cancel, delete, export, import
and period close writes the time, user, action and document.

## Worked example (used by the tests)

Items:
- A: price 100.00, tax 18%, stock 10
- B: price 45.50, tax 5%, stock 5

Customer C1 with no credit limit. Invoice dated 2026-11-20, document discount 5%.

| Line | Qty | Disc % | Net | Doc share | Tax |
|---|---|---|---|---|---|
| A | 3 | 10 | 270.00 | 13.50 | 46.17 |
| B | 2 | 0 | 91.00 | 4.55 | 4.32 |

The totals are: subtotal 361.00, discount 18.05, tax 50.49, **total 393.44**.
After posting:
- stock A is 7 and stock B is 3
- Receivable has a debit of 393.44
- Sales has a credit of 342.95
- Tax has a credit of 50.49
- the ledger is "Balanced"
