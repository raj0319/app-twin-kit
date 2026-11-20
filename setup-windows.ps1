# Local, non-administrator setup. Run with PowerShell 7 or Windows PowerShell 5.1.
[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('auto','codex','claude')][string]$Agent = 'auto',
    [string]$Python,
    [string]$EnvironmentPath = (Join-Path $PSScriptRoot '.venv'),
    [switch]$Install,
    [switch]$Browser
)
$ErrorActionPreference = 'Stop'
if (!$Python) {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $Python = & $launcher.Source -3 -c "import sys; print(sys.executable)"
    } else {
        $candidate = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($candidate) { $Python = $candidate.Source }
    }
}
if (!$Python) { throw 'Python 3.11+ is required' }
& $Python -c "import sys; raise SystemExit(sys.version_info < (3, 11))"
if ($LASTEXITCODE) { throw 'Python 3.11+ is required' }
$candidates = if ($Agent -eq 'auto') { @('codex','claude') } else { @($Agent) }
$available = @($candidates | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue })
[pscustomobject]@{
    Python = $Python
    Node = [bool](Get-Command node.exe -ErrorAction SilentlyContinue)
    PostgreSQL = [bool](Get-Command psql.exe -ErrorAction SilentlyContinue)
    Docker = [bool](Get-Command docker.exe -ErrorAction SilentlyContinue)
    MicrosoftEdge = Test-Path -LiteralPath "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    Agents = $available -join ', '
}
if ($Browser -and !$Install) { throw '-Browser requires -Install' }
if ($Install -and $PSCmdlet.ShouldProcess($PSScriptRoot, 'Install pinned toolkit dependencies in .venv')) {
    $venv = $EnvironmentPath
    $envPython = Join-Path $venv 'Scripts/python.exe'
    if (!(Test-Path -LiteralPath $envPython)) {
        & $Python -m venv $venv
        if ($LASTEXITCODE) { throw 'Virtual environment creation failed' }
    }
    & $envPython -m pip install "$PSScriptRoot[windows,browser,dev]"
    if ($LASTEXITCODE) { throw 'Dependency installation failed' }
    if ($Browser) {
        & $envPython -m playwright install chromium
        if ($LASTEXITCODE) { throw 'Chromium installation failed' }
    }
    & $envPython -m twin doctor --agent $Agent
}
