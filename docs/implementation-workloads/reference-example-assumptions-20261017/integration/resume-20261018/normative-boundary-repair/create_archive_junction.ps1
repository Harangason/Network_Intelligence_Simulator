param([Parameter(Mandatory=$true)][string]$Source, [Parameter(Mandatory=$true)][string]$Target)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Source) { throw 'Legacy path must be absent after reversible directory rename.' }
if (-not (Test-Path -LiteralPath $Target -PathType Container)) { throw 'Verified destination directory missing.' }
New-Item -ItemType Junction -Path $Source -Target $Target | Out-Null
