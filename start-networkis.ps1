param([string]$ReleaseReceipt)
& (Join-Path $PSScriptRoot "scripts\dev\start-networkis.ps1") @PSBoundParameters
exit $LASTEXITCODE
