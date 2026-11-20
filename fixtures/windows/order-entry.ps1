# Self-authored disposable WPF order entry fixture.
param(
    [Parameter(Mandatory)][string]$FixtureDirectory,
    [Parameter(Mandatory)][string]$Title
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
$fixturePath = Join-Path $FixtureDirectory 'orders.json'
[xml]$markup = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Width="570" Height="420" WindowStartupLocation="CenterScreen">
    <StackPanel Margin="22">
        <StackPanel Orientation="Horizontal">
            <Button Name="Entry" AutomationProperties.AutomationId="entry" Padding="14,5" Margin="0,0,8,0">Entry</Button>
            <Button Name="Records" AutomationProperties.AutomationId="records" Padding="14,5">Records</Button>
        </StackPanel>
        <StackPanel Name="Form" Margin="0,12,0,0">
            <Label Target="{Binding ElementName=OrderCode}">Code</Label>
            <TextBox Name="OrderCode" AutomationProperties.AutomationId="code"/>
            <Label Target="{Binding ElementName=Quantity}">Quantity</Label>
            <TextBox Name="Quantity" AutomationProperties.AutomationId="quantity"/>
            <Label Target="{Binding ElementName=UnitPrice}">Unit price</Label>
            <TextBox Name="UnitPrice" AutomationProperties.AutomationId="unit_price"/>
            <StackPanel Orientation="Horizontal" Margin="0,14,0,0">
                <Button Name="Calculate" AutomationProperties.AutomationId="calculate" Padding="14,5" Margin="0,0,8,0">Calculate</Button>
                <Button Name="Save" AutomationProperties.AutomationId="save" Padding="14,5" Margin="0,0,8,0">Save</Button>
                <Button Name="Confirm" AutomationProperties.AutomationId="confirm_save" Padding="14,5" Visibility="Collapsed">Confirm</Button>
            </StackPanel>
            <Label>Total</Label>
            <TextBlock Name="Total" AutomationProperties.AutomationId="total"/>
        </StackPanel>
        <StackPanel Name="History" Visibility="Collapsed" Margin="0,12,0,0">
            <Label>Latest saved order</Label>
            <TextBlock Name="LatestCode" AutomationProperties.AutomationId="latest_code"/>
            <TextBlock Name="LatestTotal" AutomationProperties.AutomationId="latest_total"/>
        </StackPanel>
        <TextBlock Name="Status" Margin="0,14,0,0" AutomationProperties.AutomationId="status"/>
    </StackPanel>
</Window>
'@
$window = [Windows.Markup.XamlReader]::Load([System.Xml.XmlNodeReader]::new($markup))
$window.Title = $Title
foreach ($name in @('Entry','Records','Form','OrderCode','Quantity','UnitPrice','Calculate',
                   'Save','Confirm','Total','History','LatestCode','LatestTotal','Status')) {
    Set-Variable -Scope Script -Name $name -Value $window.FindName($name)
}

function Read-Orders {
    if (Test-Path -LiteralPath $fixturePath) {
        Get-Content -LiteralPath $fixturePath -Raw | ConvertFrom-Json
    }
}
function Evaluate-Order {
    param([bool]$Persist)
    $script:Total.Text = ''
    [int]$count = 0
    [int]$price = 0
    if (!$script:OrderCode.Text) { $script:Status.Text = 'Code failed required validation'; return }
    if (![int]::TryParse($script:Quantity.Text, [ref]$count)) { $script:Status.Text = 'Enter an integer for Quantity'; return }
    if ($count -lt 1) { $script:Status.Text = 'Quantity failed min validation'; return }
    if (![int]::TryParse($script:UnitPrice.Text, [ref]$price)) { $script:Status.Text = 'Enter an integer for Unit price'; return }
    if ($price -lt 0) { $script:Status.Text = 'Unit price failed min validation'; return }
    $value = [long]$count * $price
    if ($value -gt [int]::MaxValue) { $script:Status.Text = 'Calculated value exceeds the supported integer range'; return }
    if ($Persist) {
        $rows = @(Read-Orders)
        if (@($rows | Where-Object { $_.code -ceq $script:OrderCode.Text }).Count) {
            $script:Status.Text = 'Record conflicts with a unique field or required reference'; return
        }
        $rows += [pscustomobject]@{code=$script:OrderCode.Text; quantity=$count; unit_price=$price; total=$value}
        ConvertTo-Json -InputObject $rows | Set-Content -LiteralPath "$fixturePath.tmp" -Encoding UTF8
        Move-Item -LiteralPath "$fixturePath.tmp" -Destination $fixturePath -Force
    }
    $script:Total.Text = "$value"
    $script:Status.Text = if ($Persist) { 'Saved' } else { 'Calculated' }
}
$Entry.Add_Click({
    $Form.Visibility = 'Visible'
    $History.Visibility = 'Collapsed'
    foreach ($field in @($OrderCode,$Quantity,$UnitPrice,$Total,$Status)) { $field.Text = '' }
})
$Records.Add_Click({
    $History.Visibility = 'Visible'
    $Form.Visibility = 'Collapsed'
    $last = @(Read-Orders) | Select-Object -Last 1
    $LatestCode.Text = $last.code
    $LatestTotal.Text = [string]$last.total
    $Status.Text = ''
})
$Calculate.Add_Click({ Evaluate-Order $false })
$Save.Add_Click({ $Confirm.Visibility = 'Visible' })
$Confirm.Add_Click({ $Confirm.Visibility = 'Collapsed'; Evaluate-Order $true })
[void]$window.ShowDialog()
