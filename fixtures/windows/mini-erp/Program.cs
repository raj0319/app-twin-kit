// Mini ERP: self-authored WinForms fixture. Usage: MiniErp.exe --data <folder> [--user admin --company Main]
using System.Drawing.Printing;
using System.Globalization;

namespace MiniErp;

static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        string Arg(string name) => args.SkipWhile(a => a != name).Skip(1).FirstOrDefault();
        var folder = Arg("--data") ?? throw new ArgumentException("--data <folder> is required");
        Directory.CreateDirectory(folder);
        ApplicationConfiguration.Initialize();
        // A test fixture must never hide its own bugs: log unhandled errors next to the data and show them.
        Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);
        Application.ThreadException += (_, e) =>
        {
            File.AppendAllText(Path.Combine(folder, "crash.txt"), e.Exception + Environment.NewLine);
            MessageBox.Show(e.Exception.Message, "Mini ERP error", MessageBoxButtons.OK, MessageBoxIcon.Error);
        };
        string user = Arg("--user"), company = Arg("--company");
        if (user is null || company is null)
        {
            using var login = new LoginForm();
            if (login.ShowDialog() != DialogResult.OK) return;
            (user, company) = (login.User, login.Company);
        }
        Application.Run(new MainForm(new Erp(folder, user, company), folder));
    }
}

sealed class LoginForm : Form
{
    readonly ComboBox _user = new() { Name = "loginUser", AccessibleName = "User", DropDownStyle = ComboBoxStyle.DropDownList, Left = 110, Top = 20, Width = 160 };
    readonly ComboBox _company = new() { Name = "loginCompany", AccessibleName = "Company", DropDownStyle = ComboBoxStyle.DropDownList, Left = 110, Top = 56, Width = 160 };
    public string User => (string)_user.SelectedItem;
    public string Company => (string)_company.SelectedItem;

    public LoginForm()
    {
        Text = "ZZTEST Mini ERP Login";
        ClientSize = new Size(300, 140);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        StartPosition = FormStartPosition.CenterScreen;
        _user.Items.AddRange(Erp.Users);
        _company.Items.AddRange(Erp.CompanyNames);
        _user.SelectedIndex = 0;
        _company.SelectedIndex = 0;
        var ok = new Button { Name = "login", Text = "Log in", Left = 110, Top = 96, Width = 80, DialogResult = DialogResult.OK };
        Controls.AddRange(new Control[] { new Label { Text = "User", Left = 20, Top = 23, Width = 80 }, _user, new Label { Text = "Company", Left = 20, Top = 59, Width = 80 }, _company, ok });
        AcceptButton = ok;
    }
}

sealed class MainForm : Form
{
    const int PageSize = 5;
    readonly Erp _erp;
    readonly string _folder;
    readonly Label _status = new() { Name = "status", Dock = DockStyle.Bottom, Height = 24, TextAlign = ContentAlignment.MiddleLeft, BorderStyle = BorderStyle.FixedSingle, Text = "Ready" };
    readonly TabControl _tabs = new() { Name = "tabs", Left = 8, Top = 58, Width = 984, Height = 590 };
    bool _customerIsNew = true, _itemIsNew = true;
    Invoice _draft = new();
    int _page;
    string _sort = "Number";

    // customers
    TextBox _custCode, _custName, _custGstin, _custCredit;
    DataGridView _customers;
    // items
    TextBox _itemCode, _itemName, _itemPrice, _itemStock;
    ComboBox _itemTax;
    DataGridView _items;
    // invoice
    Label _invNumber, _invStatus, _subtotal, _discount, _tax, _total;
    TextBox _invDate, _docDiscount, _lineQty, _lineDiscount;
    ComboBox _invCustomer, _lineItem;
    DataGridView _lines;
    // lists and reports
    TextBox _search, _closeDate;
    ComboBox _statusFilter, _sortBy;
    DataGridView _invoiceList, _report, _ledger, _audit;
    Label _pageLabel, _reportTotal, _ledgerCheck, _closedThrough;

    public MainForm(Erp erp, string folder)
    {
        _erp = erp;
        _folder = folder;
        Text = $"ZZTEST Mini ERP - {erp.Company} - {erp.User}";
        ClientSize = new Size(1000, 680);
        StartPosition = FormStartPosition.CenterScreen;
        KeyPreview = true;
        BuildMenu();
        _tabs.TabPages.AddRange(new[] { CustomersPage(), ItemsPage(), InvoicePage(), ListPage(), ReportPage(), LedgerPage(), AdminPage(), AuditPage() });
        Controls.Add(_tabs);
        Controls.Add(_status);
        KeyDown += OnShortcut;
        RefreshAll();
    }

    // ------------------------------------------------------------ helpers
    void Run(Action action)
    {
        try { action(); }
        catch (RuleException exc)
        {
            _status.Text = exc.Message;
            MessageBox.Show(this, exc.Message, "Mini ERP", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    void Done(string message)
    {
        _status.Text = message;
        RefreshAll();
    }

    static TextBox Field(Control parent, string name, string label, int x, int y, int width = 180)
    {
        parent.Controls.Add(new Label { Text = label, Left = x, Top = y + 3, Width = 110 });
        var box = new TextBox { Name = name, AccessibleName = label, Left = x + 115, Top = y, Width = width };
        parent.Controls.Add(box);
        return box;
    }

    static ComboBox Combo(Control parent, string name, string label, int x, int y, int width = 180)
    {
        parent.Controls.Add(new Label { Text = label, Left = x, Top = y + 3, Width = 110 });
        var combo = new ComboBox { Name = name, AccessibleName = label, Left = x + 115, Top = y, Width = width, DropDownStyle = ComboBoxStyle.DropDownList };
        parent.Controls.Add(combo);
        return combo;
    }

    static Button ButtonAt(Control parent, string name, string text, int x, int y, EventHandler click, int width = 90)
    {
        var button = new Button { Name = name, Text = text, Left = x, Top = y, Width = width, Height = 28 };
        button.Click += click;
        parent.Controls.Add(button);
        return button;
    }

    static Label Value(Control parent, string name, string label, int x, int y)
    {
        parent.Controls.Add(new Label { Text = label, Left = x, Top = y, Width = 110 });
        var value = new Label { Name = name, Left = x + 115, Top = y, Width = 140, TextAlign = ContentAlignment.TopRight };
        parent.Controls.Add(value);
        return value;
    }

    static DataGridView Grid(Control parent, string name, int x, int y, int width, int height, params string[] columns)
    {
        var grid = new DataGridView
        {
            Name = name, AccessibleName = name, Left = x, Top = y, Width = width, Height = height, ReadOnly = true,
            AllowUserToAddRows = false, AllowUserToDeleteRows = false, SelectionMode = DataGridViewSelectionMode.FullRowSelect,
            MultiSelect = false, RowHeadersVisible = false, AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
        };
        foreach (var column in columns) grid.Columns.Add(column.Replace(" ", "").Replace("%", "Pct"), column);
        parent.Controls.Add(grid);
        return grid;
    }

    static string Money(decimal value) => value.ToString("0.00", CultureInfo.InvariantCulture);

    // ------------------------------------------------------------ menu, toolbar, shortcuts
    void BuildMenu()
    {
        var menu = new MenuStrip { Name = "menu" };
        ToolStripMenuItem Item(string text, EventHandler click) => new(text, null, click);
        int Tab(string name) => _tabs.TabPages.IndexOfKey(name);
        menu.Items.Add(new ToolStripMenuItem("File", null,
            Item("Export invoices CSV", (_, _) => Run(() => Done($"Exported {Path.GetFileName(_erp.ExportCsv(_folder))}"))),
            Item("Print invoice PDF", (_, _) => Run(PrintPdf)),
            Item("Import customers", (_, _) => Run(() => { var (ok, bad) = _erp.ImportCustomers(_folder); Done($"Imported {ok}, rejected {bad}"); })),
            Item("Exit", (_, _) => Close())));
        menu.Items.Add(new ToolStripMenuItem("Masters", null,
            Item("Customers", (_, _) => _tabs.SelectedIndex = Tab("customersPage")),
            Item("Items", (_, _) => _tabs.SelectedIndex = Tab("itemsPage"))));
        menu.Items.Add(new ToolStripMenuItem("Sales", null,
            Item("New invoice", (_, _) => NewInvoice()),
            Item("Invoice list", (_, _) => _tabs.SelectedIndex = Tab("listPage"))));
        menu.Items.Add(new ToolStripMenuItem("Reports", null,
            Item("Sales by customer", (_, _) => _tabs.SelectedIndex = Tab("reportPage")),
            Item("Ledger", (_, _) => _tabs.SelectedIndex = Tab("ledgerPage"))));
        menu.Items.Add(new ToolStripMenuItem("Admin", null,
            Item("Close period", (_, _) => _tabs.SelectedIndex = Tab("adminPage")),
            Item("Audit log", (_, _) => _tabs.SelectedIndex = Tab("auditPage"))));
        var tools = new ToolStrip { Name = "toolbar", Top = 26, Dock = DockStyle.None, Left = 0, Width = 1000 };
        tools.Items.Add(new ToolStripButton("New invoice", null, (_, _) => NewInvoice()) { Name = "toolNewInvoice" });
        tools.Items.Add(new ToolStripButton("Save", null, (_, _) => SaveCurrent()) { Name = "toolSave" });
        tools.Items.Add(new ToolStripButton("Post", null, (_, _) => Run(PostInvoice)) { Name = "toolPost" });
        MainMenuStrip = menu;
        Controls.Add(tools);
        Controls.Add(menu);
    }

    void OnShortcut(object sender, KeyEventArgs e)
    {
        if (e.Control && e.KeyCode == Keys.S) { SaveCurrent(); e.Handled = true; }
        if (e.Control && e.KeyCode == Keys.N) { NewInvoice(); e.Handled = true; }
    }

    void SaveCurrent()
    {
        switch (_tabs.SelectedTab?.Name)
        {
            case "customersPage": Run(SaveCustomer); break;
            case "itemsPage": Run(SaveItem); break;
            case "invoicePage": Run(SaveInvoice); break;
            default: _status.Text = "Nothing to save on this tab"; break;
        }
    }

    // ------------------------------------------------------------ customers
    TabPage CustomersPage()
    {
        var page = new TabPage("Customers") { Name = "customersPage" };
        _custCode = Field(page, "custCode", "Code", 16, 20);
        _custName = Field(page, "custName", "Name", 16, 56);
        _custGstin = Field(page, "custGstin", "GSTIN", 16, 92);
        _custCredit = Field(page, "custCredit", "Credit limit", 16, 128);
        ButtonAt(page, "custNew", "New", 16, 172, (_, _) => ClearCustomer());
        ButtonAt(page, "custSave", "Save", 112, 172, (_, _) => Run(SaveCustomer));
        ButtonAt(page, "custDelete", "Delete", 208, 172, (_, _) => Run(DeleteCustomer));
        _customers = Grid(page, "customers", 340, 20, 620, 520, "Code", "Name", "GSTIN", "Credit limit");
        _customers.SelectionChanged += (_, _) =>
        {
            if (_customers.CurrentRow?.Cells[0].Value is not string code) return;
            var c = _erp.Data.Customers.First(x => x.Code == code);
            (_custCode.Text, _custName.Text, _custGstin.Text, _custCredit.Text) = (c.Code, c.Name, c.Gstin, Money(c.CreditLimit));
            _customerIsNew = false;
        };
        return page;
    }

    void ClearCustomer()
    {
        _custCode.Text = _custName.Text = _custGstin.Text = _custCredit.Text = "";
        _customerIsNew = true;
        _status.Text = "New customer";
    }

    void SaveCustomer()
    {
        _erp.SaveCustomer(_custCode.Text, _custName.Text, _custGstin.Text, _custCredit.Text, _customerIsNew);
        _customerIsNew = false;
        Done($"Customer {_custCode.Text.Trim().ToUpperInvariant()} saved");
    }

    void DeleteCustomer()
    {
        var code = _custCode.Text.Trim().ToUpperInvariant();
        if (code.Length == 0) throw new RuleException("Select a customer first");
        if (MessageBox.Show(this, $"Delete customer {code}?", "Confirm delete", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
        {
            _status.Text = "Delete cancelled";
            return;
        }
        _erp.DeleteCustomer(code);
        ClearCustomer();
        Done($"Customer {code} deleted");
    }

    // ------------------------------------------------------------ items
    TabPage ItemsPage()
    {
        var page = new TabPage("Items") { Name = "itemsPage" };
        _itemCode = Field(page, "itemCode", "Code", 16, 20);
        _itemName = Field(page, "itemName", "Name", 16, 56);
        _itemPrice = Field(page, "itemPrice", "Price", 16, 92);
        _itemTax = Combo(page, "itemTax", "Tax rate %", 16, 128);
        _itemTax.Items.AddRange(Erp.TaxRates.Select(r => (object)r.ToString(CultureInfo.InvariantCulture)).ToArray());
        _itemTax.SelectedIndex = 3;
        _itemStock = Field(page, "itemStock", "Opening stock", 16, 164);
        ButtonAt(page, "itemNew", "New", 16, 208, (_, _) => ClearItem());
        ButtonAt(page, "itemSave", "Save", 112, 208, (_, _) => Run(SaveItem));
        _items = Grid(page, "items", 340, 20, 620, 520, "Code", "Name", "Price", "Tax %", "Stock");
        _items.SelectionChanged += (_, _) =>
        {
            if (_items.CurrentRow?.Cells[0].Value is not string code) return;
            var i = _erp.Data.Items.First(x => x.Code == code);
            (_itemCode.Text, _itemName.Text, _itemPrice.Text, _itemStock.Text) = (i.Code, i.Name, Money(i.Price), i.Stock.ToString(CultureInfo.InvariantCulture));
            _itemTax.SelectedItem = i.TaxRate.ToString(CultureInfo.InvariantCulture);
            _itemIsNew = false;
        };
        return page;
    }

    void ClearItem()
    {
        _itemCode.Text = _itemName.Text = _itemPrice.Text = _itemStock.Text = "";
        _itemTax.SelectedIndex = 3;
        _itemIsNew = true;
        _status.Text = "New item";
    }

    void SaveItem()
    {
        _erp.SaveItem(_itemCode.Text, _itemName.Text, _itemPrice.Text, decimal.Parse((string)_itemTax.SelectedItem, CultureInfo.InvariantCulture), _itemStock.Text, _itemIsNew);
        _itemIsNew = false;
        Done($"Item {_itemCode.Text.Trim().ToUpperInvariant()} saved");
    }

    // ------------------------------------------------------------ invoice
    TabPage InvoicePage()
    {
        var page = new TabPage("Invoice") { Name = "invoicePage" };
        _invNumber = Value(page, "invNumber", "Number", 16, 20);
        _invStatus = Value(page, "invStatus", "Status", 300, 20);
        _invDate = Field(page, "invDate", "Date (yyyy-MM-dd)", 16, 48, 120);
        _invCustomer = Combo(page, "invCustomer", "Customer", 300, 48, 160);
        _docDiscount = Field(page, "invDocDiscount", "Doc discount %", 600, 48, 80);
        _lineItem = Combo(page, "lineItem", "Item", 16, 92, 120);
        _lineQty = Field(page, "lineQty", "Qty", 300, 92, 60);
        _lineDiscount = Field(page, "lineDiscount", "Line discount %", 520, 92, 60);
        ButtonAt(page, "addLine", "Add line", 16, 128, (_, _) => Run(AddLine));
        ButtonAt(page, "updateLine", "Update line", 112, 128, (_, _) => Run(UpdateLine));
        ButtonAt(page, "removeLine", "Remove line", 208, 128, (_, _) => Run(RemoveLine));
        _lines = Grid(page, "lines", 16, 168, 944, 220, "Item", "Qty", "Price", "Disc %", "Tax %", "Net", "Tax");
        _lines.SelectionChanged += (_, _) =>
        {
            var index = _lines.CurrentRow?.Index ?? -1;
            if (index < 0 || index >= _draft.Lines.Count) return;
            var line = _draft.Lines[index];
            _lineItem.SelectedItem = line.ItemCode;
            _lineQty.Text = line.Qty.ToString(CultureInfo.InvariantCulture);
            _lineDiscount.Text = line.DiscountPct.ToString(CultureInfo.InvariantCulture);
        };
        _subtotal = Value(page, "invSubtotal", "Subtotal", 700, 400);
        _discount = Value(page, "invDiscount", "Discount", 700, 424);
        _tax = Value(page, "invTax", "Tax", 700, 448);
        _total = Value(page, "invTotal", "Total", 700, 472);
        _docDiscount.Leave += (_, _) => Run(Recalculate);
        ButtonAt(page, "invNew", "New", 16, 500, (_, _) => NewInvoice());
        ButtonAt(page, "invSave", "Save draft", 112, 500, (_, _) => Run(SaveInvoice));
        ButtonAt(page, "invConfirm", "Confirm", 208, 500, (_, _) => Run(() => { _erp.Confirm(_draft.Number); Reload("confirmed"); }));
        ButtonAt(page, "invPost", "Post", 304, 500, (_, _) => Run(PostInvoice));
        ButtonAt(page, "invCancel", "Cancel invoice", 400, 500, (_, _) => Run(CancelInvoice), 110);
        return page;
    }

    void NewInvoice()
    {
        _draft = new Invoice { Date = DateTime.Today };
        _invDate.Text = _draft.Date.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
        _docDiscount.Text = "0";
        _lineQty.Text = "1";
        _lineDiscount.Text = "0";
        _tabs.SelectedTab = _tabs.TabPages["invoicePage"];
        ShowInvoice();
        _status.Text = "New invoice";
    }

    void ReadHeader()
    {
        if (!DateTime.TryParseExact(_invDate.Text.Trim(), "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var date))
            throw new RuleException("Date must be yyyy-MM-dd");
        _draft.Date = date;
        _draft.CustomerCode = (string)_invCustomer.SelectedItem ?? "";
        _draft.DocDiscountPct = Erp.ParseDocDiscount(_docDiscount.Text);
    }

    void RequireDraft()
    {
        if (_draft.Status != "Draft") throw new RuleException("Only draft invoices can be changed");
    }

    void Recalculate()
    {
        if (_draft.Status != "Draft") return;
        _draft.DocDiscountPct = Erp.ParseDocDiscount(_docDiscount.Text);
        // Keep what the user has chosen on screen; redrawing must not reset the header.
        if (DateTime.TryParseExact(_invDate.Text.Trim(), "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var date))
            _draft.Date = date;
        _draft.CustomerCode = (string)_invCustomer.SelectedItem ?? "";
        Erp.Calculate(_draft);
        ShowInvoice();
    }

    void AddLine()
    {
        RequireDraft();
        _draft.Lines.Add(_erp.MakeLine((string)_lineItem.SelectedItem ?? "", _lineQty.Text, _lineDiscount.Text));
        Recalculate();
        _status.Text = $"Line {_draft.Lines.Count} added";
    }

    void UpdateLine()
    {
        RequireDraft();
        var index = _lines.CurrentRow?.Index ?? -1;
        if (index < 0 || index >= _draft.Lines.Count) throw new RuleException("Select a line first");
        _draft.Lines[index] = _erp.MakeLine((string)_lineItem.SelectedItem ?? "", _lineQty.Text, _lineDiscount.Text);
        Recalculate();
        _status.Text = $"Line {index + 1} updated";
    }

    void RemoveLine()
    {
        RequireDraft();
        var index = _lines.CurrentRow?.Index ?? -1;
        if (index < 0 || index >= _draft.Lines.Count) throw new RuleException("Select a line first");
        _draft.Lines.RemoveAt(index);
        Recalculate();
        _status.Text = $"Line {index + 1} removed";
    }

    void SaveInvoice()
    {
        RequireDraft();
        ReadHeader();
        var saved = _erp.SaveDraft(Clone(_draft));
        _draft = Clone(saved);
        Done($"Invoice {saved.Number} saved");
        ShowInvoice();
    }

    void PostInvoice()
    {
        _erp.Post(_draft.Number);
        Reload("posted");
    }

    void CancelInvoice()
    {
        if (_draft.Number.Length == 0) throw new RuleException("Save the invoice first");
        if (MessageBox.Show(this, $"Cancel invoice {_draft.Number}?", "Confirm cancel", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
        {
            _status.Text = "Cancel aborted";
            return;
        }
        _erp.Cancel(_draft.Number);
        Reload("cancelled");
    }

    void Reload(string verb)
    {
        _draft = Clone(_erp.Find(_draft.Number));
        Done($"Invoice {_draft.Number} {verb}");
        ShowInvoice();
    }

    static Invoice Clone(Invoice source) => System.Text.Json.JsonSerializer.Deserialize<Invoice>(System.Text.Json.JsonSerializer.Serialize(source));

    void ShowInvoice()
    {
        _invNumber.Text = _draft.Number.Length == 0 ? "(new)" : _draft.Number;
        _invStatus.Text = _draft.Status;
        _invDate.Text = _draft.Date.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
        _invCustomer.SelectedItem = _draft.CustomerCode.Length == 0 ? null : _draft.CustomerCode;
        _docDiscount.Text = _draft.DocDiscountPct.ToString(CultureInfo.InvariantCulture);
        _lines.Rows.Clear();
        foreach (var l in _draft.Lines)
            _lines.Rows.Add(l.ItemCode, l.Qty, Money(l.Price), l.DiscountPct.ToString(CultureInfo.InvariantCulture), l.TaxRate.ToString(CultureInfo.InvariantCulture), Money(l.Net), Money(l.Tax));
        (_subtotal.Text, _discount.Text, _tax.Text, _total.Text) = (Money(_draft.Subtotal), Money(_draft.Discount), Money(_draft.Tax), Money(_draft.Total));
    }

    // ------------------------------------------------------------ list, reports, ledger, admin, audit
    TabPage ListPage()
    {
        var page = new TabPage("Invoices") { Name = "listPage" };
        _search = Field(page, "search", "Search", 16, 20, 160);
        _statusFilter = Combo(page, "statusFilter", "Status", 320, 20, 120);
        _statusFilter.Items.AddRange(new object[] { "All", "Draft", "Confirmed", "Posted", "Cancelled" });
        _statusFilter.SelectedIndex = 0;
        _sortBy = Combo(page, "sortBy", "Sort by", 580, 20, 120);
        _sortBy.Items.AddRange(new object[] { "Number", "Date", "Customer", "Total" });
        _sortBy.SelectedIndex = 0;
        ButtonAt(page, "searchButton", "Search", 860, 18, (_, _) => { _page = 0; _sort = (string)_sortBy.SelectedItem; ShowList(); });
        _invoiceList = Grid(page, "invoiceList", 16, 60, 944, 400, "Number", "Date", "Customer", "Status", "Total");
        _invoiceList.ColumnHeaderMouseClick += (_, e) => { _sort = _invoiceList.Columns[e.ColumnIndex].HeaderText; _sortBy.SelectedItem = _sort; ShowList(); };
        ButtonAt(page, "prevPage", "< Prev", 16, 472, (_, _) => { if (_page > 0) _page--; ShowList(); });
        ButtonAt(page, "nextPage", "Next >", 112, 472, (_, _) => { _page++; ShowList(); });
        _pageLabel = new Label { Name = "page", Left = 216, Top = 478, Width = 160 };
        page.Controls.Add(_pageLabel);
        ButtonAt(page, "openInvoice", "Open", 860, 472, (_, _) => Run(OpenSelected));
        return page;
    }

    void ShowList()
    {
        var rows = _erp.Search(_search.Text, (string)_statusFilter.SelectedItem ?? "All");
        rows = _sort switch
        {
            "Date" => rows.OrderBy(i => i.Date).ThenBy(i => i.Number).ToList(),
            "Customer" => rows.OrderBy(i => i.CustomerCode).ThenBy(i => i.Number).ToList(),
            "Total" => rows.OrderByDescending(i => i.Total).ThenBy(i => i.Number).ToList(),
            _ => rows.OrderBy(i => i.Number).ToList(),
        };
        var pages = Math.Max(1, (rows.Count + PageSize - 1) / PageSize);
        _page = Math.Clamp(_page, 0, pages - 1);
        _invoiceList.Rows.Clear();
        foreach (var i in rows.Skip(_page * PageSize).Take(PageSize))
            _invoiceList.Rows.Add(i.Number, i.Date.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture), i.CustomerCode, i.Status, Money(i.Total));
        _pageLabel.Text = $"Page {_page + 1} of {pages} ({rows.Count} invoices)";
    }

    void OpenSelected()
    {
        if (_invoiceList.CurrentRow?.Cells[0].Value is not string number) throw new RuleException("Select an invoice first");
        _draft = Clone(_erp.Find(number));
        _tabs.SelectedTab = _tabs.TabPages["invoicePage"];
        ShowInvoice();
        _status.Text = $"Invoice {number} opened";
    }

    TabPage ReportPage()
    {
        var page = new TabPage("Sales report") { Name = "reportPage" };
        ButtonAt(page, "refreshReport", "Refresh", 16, 16, (_, _) => ShowReport());
        _report = Grid(page, "salesReport", 16, 56, 600, 400, "Customer", "Invoices", "Total");
        _reportTotal = Value(page, "reportTotal", "Grand total", 400, 470);
        return page;
    }

    void ShowReport()
    {
        _report.Rows.Clear();
        var rows = _erp.SalesByCustomer();
        foreach (var r in rows) _report.Rows.Add(r.Customer, r.Count, Money(r.Total));
        _reportTotal.Text = Money(rows.Sum(r => r.Total));
    }

    TabPage LedgerPage()
    {
        var page = new TabPage("Ledger") { Name = "ledgerPage" };
        ButtonAt(page, "refreshLedger", "Refresh", 16, 16, (_, _) => ShowLedger());
        _ledger = Grid(page, "ledger", 16, 56, 600, 300, "Account", "Debit", "Credit", "Balance");
        _ledgerCheck = new Label { Name = "ledgerCheck", Left = 16, Top = 370, Width = 300 };
        page.Controls.Add(_ledgerCheck);
        return page;
    }

    void ShowLedger()
    {
        _ledger.Rows.Clear();
        var rows = _erp.Balances();
        foreach (var r in rows) _ledger.Rows.Add(r.Account, Money(r.Debit), Money(r.Credit), Money(r.Balance));
        _ledgerCheck.Text = rows.Sum(r => r.Balance) == 0 ? "Balanced" : "Out of balance";
    }

    TabPage AdminPage()
    {
        var page = new TabPage("Admin") { Name = "adminPage" };
        _closeDate = Field(page, "closeDate", "Close month of", 16, 20, 120);
        ButtonAt(page, "closePeriod", "Close period", 300, 18, (_, _) => Run(() =>
        {
            if (!DateTime.TryParseExact(_closeDate.Text.Trim(), "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var date))
                throw new RuleException("Date must be yyyy-MM-dd");
            _erp.ClosePeriod(date);
            Done($"Period closed through {_erp.Data.ClosedThrough:yyyy-MM-dd}");
        }), 110);
        _closedThrough = new Label { Name = "closedThrough", Left = 16, Top = 64, Width = 400 };
        page.Controls.Add(_closedThrough);
        return page;
    }

    TabPage AuditPage()
    {
        var page = new TabPage("Audit log") { Name = "auditPage" };
        _audit = Grid(page, "audit", 16, 16, 944, 500, "Time", "User", "Action", "Document");
        return page;
    }

    void RefreshAll()
    {
        _customers.Rows.Clear();
        foreach (var c in _erp.Data.Customers.OrderBy(c => c.Code)) _customers.Rows.Add(c.Code, c.Name, c.Gstin, Money(c.CreditLimit));
        _items.Rows.Clear();
        foreach (var i in _erp.Data.Items.OrderBy(i => i.Code)) _items.Rows.Add(i.Code, i.Name, Money(i.Price), i.TaxRate.ToString(CultureInfo.InvariantCulture), i.Stock);
        var customer = (string)_invCustomer.SelectedItem;
        _invCustomer.Items.Clear();
        _invCustomer.Items.AddRange(_erp.Data.Customers.OrderBy(c => c.Code).Select(c => (object)c.Code).ToArray());
        if (customer is not null && _invCustomer.Items.Contains(customer)) _invCustomer.SelectedItem = customer;
        var item = (string)_lineItem.SelectedItem;
        _lineItem.Items.Clear();
        _lineItem.Items.AddRange(_erp.Data.Items.OrderBy(i => i.Code).Select(i => (object)i.Code).ToArray());
        if (item is not null && _lineItem.Items.Contains(item)) _lineItem.SelectedItem = item;
        ShowList();
        ShowReport();
        ShowLedger();
        _closedThrough.Text = _erp.Data.ClosedThrough is { } closed ? $"Closed through {closed:yyyy-MM-dd}" : "No period closed";
        _audit.Rows.Clear();
        foreach (var a in _erp.Data.Audit.AsEnumerable().Reverse()) _audit.Rows.Add(a.Time, a.User, a.Action, a.Document);
        if (_invNumber.Text.Length == 0) NewInvoice();
    }

    // ------------------------------------------------------------ print to PDF
    void PrintPdf()
    {
        if (_draft.Number.Length == 0) throw new RuleException("Save the invoice first");
        const string printer = "Microsoft Print to PDF";
        if (!PrinterSettings.InstalledPrinters.Cast<string>().Contains(printer)) throw new RuleException("Microsoft Print to PDF is not installed");
        var path = Path.Combine(_folder, $"{_draft.Number}.pdf");
        var lines = new List<string>
        {
            $"Mini ERP ({_erp.Company})", $"Invoice {_draft.Number}", $"Date {_draft.Date:yyyy-MM-dd}", $"Customer {_draft.CustomerCode}", $"Status {_draft.Status}", "",
        };
        lines.AddRange(_draft.Lines.Select(l => $"{l.ItemCode}  qty {l.Qty}  price {Money(l.Price)}  disc {l.DiscountPct}%  tax {l.TaxRate}%  net {Money(l.Net)}"));
        lines.AddRange(new[] { "", $"Subtotal {Money(_draft.Subtotal)}", $"Discount {Money(_draft.Discount)}", $"Tax {Money(_draft.Tax)}", $"Total {Money(_draft.Total)}" });
        using var document = new PrintDocument { PrintController = new StandardPrintController() };
        document.PrinterSettings.PrinterName = printer;
        document.PrinterSettings.PrintToFile = true;
        document.PrinterSettings.PrintFileName = path;
        using var font = new Font("Consolas", 10);
        document.PrintPage += (_, e) =>
        {
            var y = 60f;
            foreach (var line in lines) { e.Graphics.DrawString(line, font, Brushes.Black, 60, y); y += 18; }
        };
        document.Print();
        Done($"Printed {Path.GetFileName(path)}");
    }
}
