# Self-authored disposable WinForms fixture: a menu bar, a native confirmation dialog, a keyboard
# shortcut and an owner-drawn control with no accessible children. It writes only inside FixtureDirectory.
param(
    [Parameter(Mandatory)][string]$Title,
    [Parameter(Mandatory)][string]$FixtureDirectory
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$store = Join-Path $FixtureDirectory 'notes.txt'

$form = [Windows.Forms.Form]::new()
$form.Text = $Title
$form.Width = 520
$form.Height = 360
$form.KeyPreview = $true

$menu = [Windows.Forms.MenuStrip]::new()
$file = [Windows.Forms.ToolStripMenuItem]::new('File')
$new = [Windows.Forms.ToolStripMenuItem]::new('New')
$save = [Windows.Forms.ToolStripMenuItem]::new('Save')
[void]$file.DropDownItems.Add($new)
[void]$file.DropDownItems.Add($save)
[void]$menu.Items.Add($file)
$form.MainMenuStrip = $menu

$note = [Windows.Forms.TextBox]::new()
$note.Name = 'note'
$note.AccessibleName = 'Note'
$note.Top = 40; $note.Left = 16; $note.Width = 300

$status = [Windows.Forms.Label]::new()
$status.Name = 'status'
$status.Top = 76; $status.Left = 16; $status.Width = 460
$status.Text = 'Ready'

# Owner-drawn: three painted "keys" with no UIA children; a click is mapped by position only.
$pad = [Windows.Forms.Panel]::new()
$pad.Name = 'pad'
$pad.AccessibleName = 'Priority pad'
$pad.Top = 120; $pad.Left = 16; $pad.Width = 330; $pad.Height = 70
$pad.BackColor = [Drawing.Color]::White
$labels = @('LOW', 'MEDIUM', 'HIGH')
$pad.Add_Paint({
    param($sender, $e)
    $font = [Drawing.Font]::new('Segoe UI', 14, [Drawing.FontStyle]::Bold)
    for ($i = 0; $i -lt 3; $i++) {
        $rect = [Drawing.Rectangle]::new(10 + $i * 105, 10, 95, 50)
        $e.Graphics.DrawRectangle([Drawing.Pens]::Black, $rect)
        $format = [Drawing.StringFormat]::new()
        $format.Alignment = 'Center'; $format.LineAlignment = 'Center'
        $e.Graphics.DrawString($labels[$i], $font, [Drawing.Brushes]::Black, [Drawing.RectangleF]$rect, $format)
    }
})
$pad.Add_MouseClick({
    param($sender, $e)
    $index = [Math]::Floor(($e.X - 10) / 105)
    if ($e.Y -ge 10 -and $e.Y -le 60 -and $index -ge 0 -and $index -le 2) {
        $status.Text = "Priority $($labels[$index])"
    }
})

$new.Add_Click({ $note.Text = ''; $status.Text = 'New note' })
$save.Add_Click({
    $answer = [Windows.Forms.MessageBox]::Show($form, 'Save this note?', 'Confirm save', 'YesNo', 'Question')
    if ($answer -eq 'Yes') {
        Set-Content -LiteralPath $store -Value $note.Text -Encoding UTF8
        $status.Text = 'Saved'
    } else {
        $status.Text = 'Save cancelled'
    }
})
$form.Add_KeyDown({
    param($sender, $e)
    if ($e.Control -and $e.KeyCode -eq 'K') { $status.Text = 'Shortcut Ctrl+K'; $e.Handled = $true }
})

$form.Controls.AddRange(@($note, $status, $pad, $menu))
[void]$form.ShowDialog()
