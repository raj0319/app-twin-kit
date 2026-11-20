# Create a review package from a committed tree. Sign the setup script when a certificate is supplied.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$OutputDirectory,
    [string]$Revision = 'HEAD',
    [string]$CertificateThumbprint
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Choose a new output directory' }
$commit = & git -C $PSScriptRoot rev-parse --verify --end-of-options "$Revision^{commit}"
if ($LASTEXITCODE -or $commit -notmatch '^[0-9a-f]{40}$') { throw 'Invalid committed revision' }
$output = (New-Item -ItemType Directory -Path $OutputDirectory).FullName
$zip = Join-Path $output 'app-twin-kit-source.zip'
& git -C $PSScriptRoot archive --format=zip --output=$zip $commit
if ($LASTEXITCODE) { throw 'Git archive failed' }
Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $output 'review')
$setup = Join-Path $output 'review/setup-windows.ps1'
if ($CertificateThumbprint) {
    if ($CertificateThumbprint -notmatch '^[0-9a-fA-F]{40}$') { throw 'Invalid certificate thumbprint' }
    $certificate = Get-Item -LiteralPath "Cert:\CurrentUser\My\$CertificateThumbprint"
    $signature = Set-AuthenticodeSignature -LiteralPath $setup -Certificate $certificate -HashAlgorithm SHA256
    if ($signature.Status -ne 'Valid') { throw "Installer signature failed verification: $($signature.Status)" }
}
$setupHash = (Get-FileHash $setup -Algorithm SHA256).Hash
$sourceHash = (Get-FileHash $zip -Algorithm SHA256).Hash
[pscustomobject]@{
    Commit = $commit
    SourceSHA256 = $sourceHash
    SetupSHA256 = $setupHash
    SetupSigned = [bool]$CertificateThumbprint
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'manifest.json') -Encoding UTF8
