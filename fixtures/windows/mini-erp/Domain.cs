// Mini ERP business rules. Self-authored test fixture: every rule here is written down in EXPECTED.md.
using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace MiniErp;

public sealed class Customer
{
    public string Code { get; set; } = "";
    public string Name { get; set; } = "";
    public string Gstin { get; set; } = "";
    public decimal CreditLimit { get; set; }
}

public sealed class Item
{
    public string Code { get; set; } = "";
    public string Name { get; set; } = "";
    public decimal Price { get; set; }
    public decimal TaxRate { get; set; }
    public int Stock { get; set; }
}

public sealed class Line
{
    public string ItemCode { get; set; } = "";
    public int Qty { get; set; }
    public decimal Price { get; set; }
    public decimal DiscountPct { get; set; }
    public decimal TaxRate { get; set; }
    public decimal Net { get; set; }
    public decimal Tax { get; set; }
}

public sealed class Invoice
{
    public string Number { get; set; } = "";
    public DateTime Date { get; set; } = DateTime.Today;
    public string CustomerCode { get; set; } = "";
    public decimal DocDiscountPct { get; set; }
    public List<Line> Lines { get; set; } = new();
    public string Status { get; set; } = "Draft";
    public decimal Subtotal { get; set; }
    public decimal Discount { get; set; }
    public decimal Tax { get; set; }
    public decimal Total { get; set; }
}

public sealed class LedgerEntry
{
    public DateTime Date { get; set; }
    public string Document { get; set; } = "";
    public string Account { get; set; } = "";
    public decimal Debit { get; set; }
    public decimal Credit { get; set; }
}

public sealed class StockMove
{
    public string Document { get; set; } = "";
    public string ItemCode { get; set; } = "";
    public int Qty { get; set; }
}

public sealed class AuditRow
{
    public string Time { get; set; } = "";
    public string User { get; set; } = "";
    public string Action { get; set; } = "";
    public string Document { get; set; } = "";
}

public sealed class CompanyData
{
    public List<Customer> Customers { get; set; } = new();
    public List<Item> Items { get; set; } = new();
    public List<Invoice> Invoices { get; set; } = new();
    public List<LedgerEntry> Ledger { get; set; } = new();
    public List<StockMove> StockMoves { get; set; } = new();
    public List<AuditRow> Audit { get; set; } = new();
    public Dictionary<string, int> Sequences { get; set; } = new();
    public DateTime? ClosedThrough { get; set; }
}

public sealed class Database
{
    public Dictionary<string, CompanyData> Companies { get; set; } = new();
}

/// <summary>A refused action. The message is shown to the user word for word.</summary>
public sealed class RuleException(string message) : Exception(message);

public sealed class Erp
{
    public static readonly string[] Users = { "admin", "clerk" };
    public static readonly string[] CompanyNames = { "Main", "Branch" };
    public static readonly decimal[] TaxRates = { 0m, 5m, 12m, 18m };
    static readonly Regex Gstin = new(@"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$");
    static readonly Regex Code = new(@"^[A-Z0-9_-]{1,20}$");

    readonly string _path;
    readonly Database _db;
    public string User { get; }
    public string Company { get; }
    public CompanyData Data => _db.Companies[Company];
    public Func<DateTime> Clock { get; set; } = () => DateTime.Now;

    public Erp(string folder, string user, string company)
    {
        if (!Users.Contains(user)) throw new RuleException("Unknown user");
        if (!CompanyNames.Contains(company)) throw new RuleException("Unknown company");
        _path = Path.Combine(folder, "erp.json");
        _db = File.Exists(_path) ? JsonSerializer.Deserialize<Database>(File.ReadAllText(_path)) ?? new Database() : new Database();
        foreach (var name in CompanyNames) _db.Companies.TryAdd(name, new CompanyData());
        User = user;
        Company = company;
    }

    public bool IsAdmin => User == "admin";

    void Save()
    {
        var temp = _path + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(_db, new JsonSerializerOptions { WriteIndented = true }));
        File.Move(temp, _path, true);
    }

    void Log(string action, string document)
    {
        Data.Audit.Add(new AuditRow { Time = Clock().ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture), User = User, Action = action, Document = document });
    }

    public static decimal Round(decimal value) => Math.Round(value, 2, MidpointRounding.AwayFromZero);

    // ---------------------------------------------------------------- master data
    public void SaveCustomer(string code, string name, string gstin, string creditLimit, bool isNew)
    {
        code = code.Trim().ToUpperInvariant();
        if (code.Length == 0) throw new RuleException("Customer code is required");
        if (!Code.IsMatch(code)) throw new RuleException("Customer code may use A-Z, 0-9, - and _ only");
        if (name.Trim().Length == 0) throw new RuleException("Customer name is required");
        gstin = gstin.Trim().ToUpperInvariant();
        if (gstin.Length > 0 && !Gstin.IsMatch(gstin)) throw new RuleException("GSTIN format is invalid");
        if (!decimal.TryParse(creditLimit.Trim().Length == 0 ? "0" : creditLimit, NumberStyles.Number, CultureInfo.InvariantCulture, out var limit) || limit < 0)
            throw new RuleException("Credit limit must be 0 or more");
        var existing = Data.Customers.FirstOrDefault(c => c.Code == code);
        if (isNew && existing is not null) throw new RuleException("Customer code already exists");
        if (!isNew && existing is null) throw new RuleException("Select a customer first");
        if (existing is null) Data.Customers.Add(existing = new Customer { Code = code });
        existing.Name = name.Trim();
        existing.Gstin = gstin;
        existing.CreditLimit = Round(limit);
        Log("Customer saved", code);
        Save();
    }

    public bool CustomerInUse(string code) => Data.Invoices.Any(i => i.CustomerCode == code);

    public void DeleteCustomer(string code)
    {
        if (!IsAdmin) throw new RuleException("Your role cannot delete customers");
        if (CustomerInUse(code)) throw new RuleException("Customer is used on invoices and cannot be deleted");
        if (Data.Customers.RemoveAll(c => c.Code == code) == 0) throw new RuleException("Select a customer first");
        Log("Customer deleted", code);
        Save();
    }

    public void SaveItem(string code, string name, string price, decimal taxRate, string stock, bool isNew)
    {
        code = code.Trim().ToUpperInvariant();
        if (code.Length == 0) throw new RuleException("Item code is required");
        if (!Code.IsMatch(code)) throw new RuleException("Item code may use A-Z, 0-9, - and _ only");
        if (name.Trim().Length == 0) throw new RuleException("Item name is required");
        if (!decimal.TryParse(price, NumberStyles.Number, CultureInfo.InvariantCulture, out var p) || p < 0)
            throw new RuleException("Price must be 0 or more");
        if (!TaxRates.Contains(taxRate)) throw new RuleException("Tax rate must be 0, 5, 12 or 18");
        if (!int.TryParse(stock.Trim().Length == 0 ? "0" : stock, NumberStyles.Integer, CultureInfo.InvariantCulture, out var s) || s < 0)
            throw new RuleException("Stock must be 0 or more");
        var existing = Data.Items.FirstOrDefault(i => i.Code == code);
        if (isNew && existing is not null) throw new RuleException("Item code already exists");
        if (!isNew && existing is null) throw new RuleException("Select an item first");
        if (isNew) Data.Items.Add(existing = new Item { Code = code, Stock = s });
        existing.Name = name.Trim();
        existing.Price = Round(p);
        existing.TaxRate = taxRate;
        Log(isNew ? "Item created" : "Item saved", code);
        Save();
    }

    // ---------------------------------------------------------------- invoices
    public static void Calculate(Invoice invoice)
    {
        decimal subtotal = 0, tax = 0, discount = 0;
        foreach (var line in invoice.Lines)
        {
            var gross = line.Qty * line.Price;
            line.Net = Round(gross * (1 - line.DiscountPct / 100m));
            subtotal += line.Net;
        }
        foreach (var line in invoice.Lines)
        {
            var docShare = Round(line.Net * invoice.DocDiscountPct / 100m);
            discount += docShare;
            line.Tax = Round((line.Net - docShare) * line.TaxRate / 100m);
            tax += line.Tax;
        }
        invoice.Subtotal = Round(subtotal);
        invoice.Discount = Round(discount);
        invoice.Tax = Round(tax);
        invoice.Total = Round(invoice.Subtotal - invoice.Discount + invoice.Tax);
    }

    public Line MakeLine(string itemCode, string qty, string discountPct)
    {
        var item = Data.Items.FirstOrDefault(i => i.Code == itemCode) ?? throw new RuleException("Select an item");
        if (!int.TryParse(qty, NumberStyles.Integer, CultureInfo.InvariantCulture, out var q) || q < 1)
            throw new RuleException("Quantity must be 1 or more");
        if (!decimal.TryParse(discountPct.Trim().Length == 0 ? "0" : discountPct, NumberStyles.Number, CultureInfo.InvariantCulture, out var d) || d < 0 || d > 100)
            throw new RuleException("Discount must be between 0 and 100");
        return new Line { ItemCode = item.Code, Qty = q, Price = item.Price, DiscountPct = d, TaxRate = item.TaxRate };
    }

    public static decimal ParseDocDiscount(string text)
    {
        if (!decimal.TryParse(text.Trim().Length == 0 ? "0" : text, NumberStyles.Number, CultureInfo.InvariantCulture, out var d) || d < 0 || d > 50)
            throw new RuleException("Document discount must be between 0 and 50");
        return d;
    }

    public Invoice Find(string number) => Data.Invoices.FirstOrDefault(i => i.Number == number);

    public Invoice SaveDraft(Invoice draft)
    {
        if (draft.Status != "Draft") throw new RuleException("Only draft invoices can be changed");
        if (Data.Customers.All(c => c.Code != draft.CustomerCode)) throw new RuleException("Select a customer");
        if (draft.Lines.Count == 0) throw new RuleException("Add at least one line");
        Calculate(draft);
        if (draft.Number.Length == 0)
        {
            var key = $"INV-{draft.Date:yyyy}";
            Data.Sequences[key] = Data.Sequences.GetValueOrDefault(key) + 1;
            draft.Number = $"{key}-{Data.Sequences[key]:0000}";
            Data.Invoices.Add(draft);
            Log("Invoice created", draft.Number);
        }
        else
        {
            var index = Data.Invoices.FindIndex(i => i.Number == draft.Number);
            if (index < 0) throw new RuleException("Invoice not found");
            if (Data.Invoices[index].Status != "Draft") throw new RuleException("Only draft invoices can be changed");
            Data.Invoices[index] = draft;
            Log("Invoice saved", draft.Number);
        }
        Save();
        return draft;
    }

    decimal Outstanding(string customer) =>
        Data.Invoices.Where(i => i.CustomerCode == customer && i.Status == "Posted").Sum(i => i.Total);

    public void Confirm(string number)
    {
        var invoice = Find(number) ?? throw new RuleException("Save the invoice first");
        if (invoice.Status != "Draft") throw new RuleException("Only draft invoices can be confirmed");
        var customer = Data.Customers.First(c => c.Code == invoice.CustomerCode);
        if (customer.CreditLimit > 0 && Outstanding(customer.Code) + invoice.Total > customer.CreditLimit)
            throw new RuleException($"Credit limit exceeded for {customer.Code}");
        invoice.Status = "Confirmed";
        Log("Invoice confirmed", number);
        Save();
    }

    public void Post(string number)
    {
        if (!IsAdmin) throw new RuleException("Your role cannot post invoices");
        var invoice = Find(number) ?? throw new RuleException("Save the invoice first");
        if (invoice.Status == "Draft") throw new RuleException("Confirm the invoice before posting");
        if (invoice.Status != "Confirmed") throw new RuleException("Only confirmed invoices can be posted");
        if (Data.ClosedThrough is { } closed && invoice.Date.Date <= closed.Date) throw new RuleException("Period is closed for this date");
        foreach (var group in invoice.Lines.GroupBy(l => l.ItemCode))
        {
            var item = Data.Items.First(i => i.Code == group.Key);
            if (item.Stock < group.Sum(l => l.Qty)) throw new RuleException($"Not enough stock for {item.Code}");
        }
        foreach (var line in invoice.Lines)
        {
            Data.Items.First(i => i.Code == line.ItemCode).Stock -= line.Qty;
            Data.StockMoves.Add(new StockMove { Document = number, ItemCode = line.ItemCode, Qty = -line.Qty });
        }
        Data.Ledger.Add(new LedgerEntry { Date = invoice.Date, Document = number, Account = "Receivable", Debit = invoice.Total });
        Data.Ledger.Add(new LedgerEntry { Date = invoice.Date, Document = number, Account = "Sales", Credit = Round(invoice.Subtotal - invoice.Discount) });
        Data.Ledger.Add(new LedgerEntry { Date = invoice.Date, Document = number, Account = "Tax", Credit = invoice.Tax });
        invoice.Status = "Posted";
        Log("Invoice posted", number);
        Save();
    }

    public void Cancel(string number)
    {
        var invoice = Find(number) ?? throw new RuleException("Save the invoice first");
        if (invoice.Status == "Cancelled") throw new RuleException("Invoice is already cancelled");
        if (invoice.Status == "Posted")
        {
            if (!IsAdmin) throw new RuleException("Your role cannot cancel posted invoices");
            if (Data.ClosedThrough is { } closed && invoice.Date.Date <= closed.Date) throw new RuleException("Period is closed for this date");
            foreach (var line in invoice.Lines)
            {
                Data.Items.First(i => i.Code == line.ItemCode).Stock += line.Qty;
                Data.StockMoves.Add(new StockMove { Document = number, ItemCode = line.ItemCode, Qty = line.Qty });
            }
            foreach (var entry in Data.Ledger.Where(e => e.Document == number).ToList())
                Data.Ledger.Add(new LedgerEntry { Date = invoice.Date, Document = number, Account = entry.Account, Debit = entry.Credit, Credit = entry.Debit });
        }
        invoice.Status = "Cancelled";
        Log("Invoice cancelled", number);
        Save();
    }

    public void ClosePeriod(DateTime through)
    {
        if (!IsAdmin) throw new RuleException("Your role cannot close periods");
        var monthEnd = new DateTime(through.Year, through.Month, DateTime.DaysInMonth(through.Year, through.Month));
        Data.ClosedThrough = monthEnd;
        Log("Period closed", monthEnd.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture));
        Save();
    }

    // ---------------------------------------------------------------- lists, reports, files
    public List<Invoice> Search(string text, string status)
    {
        text = text.Trim().ToUpperInvariant();
        return Data.Invoices
            .Where(i => text.Length == 0 || i.Number.Contains(text) || i.CustomerCode.Contains(text))
            .Where(i => status == "All" || i.Status == status)
            .ToList();
    }

    public List<(string Customer, int Count, decimal Total)> SalesByCustomer() =>
        Data.Invoices.Where(i => i.Status == "Posted")
            .GroupBy(i => i.CustomerCode)
            .OrderBy(g => g.Key)
            .Select(g => (g.Key, g.Count(), Round(g.Sum(i => i.Total))))
            .ToList();

    public List<(string Account, decimal Debit, decimal Credit, decimal Balance)> Balances() =>
        Data.Ledger.GroupBy(e => e.Account).OrderBy(g => g.Key)
            .Select(g => (g.Key, g.Sum(e => e.Debit), g.Sum(e => e.Credit), g.Sum(e => e.Debit - e.Credit)))
            .ToList();

    public string ExportCsv(string folder)
    {
        var path = Path.Combine(folder, $"invoices-{Company}.csv");
        var rows = new List<string> { "Number,Date,Customer,Status,Subtotal,Discount,Tax,Total" };
        rows.AddRange(Data.Invoices.Select(i => string.Join(",", i.Number, i.Date.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture), i.CustomerCode, i.Status,
            i.Subtotal.ToString("0.00", CultureInfo.InvariantCulture), i.Discount.ToString("0.00", CultureInfo.InvariantCulture),
            i.Tax.ToString("0.00", CultureInfo.InvariantCulture), i.Total.ToString("0.00", CultureInfo.InvariantCulture))));
        File.WriteAllLines(path, rows);
        Log("Invoices exported", Path.GetFileName(path));
        Save();
        return path;
    }

    public (int Imported, int Rejected) ImportCustomers(string folder)
    {
        var source = Path.Combine(folder, "import-customers.csv");
        if (!File.Exists(source)) throw new RuleException("import-customers.csv was not found in the data folder");
        int imported = 0, rejected = 0;
        var report = new List<string>();
        foreach (var (row, index) in File.ReadAllLines(source).Skip(1).Select((r, i) => (r, i + 2)))
        {
            var cells = row.Split(',');
            try
            {
                if (cells.Length != 4) throw new RuleException("Expected 4 columns");
                SaveCustomer(cells[0], cells[1], cells[2], cells[3], isNew: true);
                imported++;
            }
            catch (RuleException exc)
            {
                rejected++;
                report.Add($"Line {index}: {exc.Message}");
            }
        }
        File.WriteAllLines(Path.Combine(folder, "import-report.txt"), report);
        Log("Customers imported", $"{imported} imported, {rejected} rejected");
        Save();
        return (imported, rejected);
    }
}
