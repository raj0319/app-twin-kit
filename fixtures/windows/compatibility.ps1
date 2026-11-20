# A second framework fixture for native accessibility checks.
param([Parameter(Mandatory)][string]$Title)
Add-Type -AssemblyName System.Windows.Forms
$form = [Windows.Forms.Form]::new()
$form.Text = $Title
$field = [Windows.Forms.TextBox]::new()
$field.AccessibleName = 'Reference'
$field.Name = 'Reference'
$field.Top = 12
$field.Left = 16
$button = [Windows.Forms.Button]::new()
$button.Text = 'Lookup'
$button.Top = 50
$button.Left = 16
$form.Controls.AddRange(@($field, $button))
[void]$form.ShowDialog()
