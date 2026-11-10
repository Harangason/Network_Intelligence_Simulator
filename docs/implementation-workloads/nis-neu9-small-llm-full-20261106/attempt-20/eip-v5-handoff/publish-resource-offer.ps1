[CmdletBinding()]
param([switch]$Publish)
$ErrorActionPreference = 'Stop'
$OfferPath = Join-Path $PSScriptRoot 'nis-v5-resource-file-02.json'
$EipRoot = 'F:\CodexOrdner\visualizations\2026\11\04\01a1a894-af58-7ec3-b311-956176734b9c\native-tcp-listener-20261108\control-v5'
$ReadyPath = Join-Path $EipRoot 'wait-receipts\control-live-05-file-02\wait-start.json'
$BridgePath = Join-Path $EipRoot 'wait-for-file-handoff-v5.ps1'
$BridgeHash = '1599D610E04024CCD53F8DF5BB7079E55E4B2A1B9500331ED861F9AF7FC8A0DB'
$RunnerHash = 'F1F56E135FA48FC1DB97C431F2D657996C7D71FA0B70BC0E7734A81EF025FBE2'
$AdapterHash = '4280623C2FEC9F925E3A3B80D86883E03C03CD424D63CB6E8D4B7E354A3F2B2C'
$Format = "yyyy-MM-dd'T'HH:mm:ss.fffffff'Z'"
if (-not $Publish) { throw 'Explicit agreed publisher start required; no action performed.' }
foreach ($path in @($ReadyPath, $OfferPath, "$OfferPath.revoked", (Join-Path $PSScriptRoot 'capture.json'))) {
    if (Test-Path -LiteralPath $path) { throw "Fresh one-time path already exists: $path" }
}
if ((Get-FileHash -LiteralPath $BridgePath -Algorithm SHA256).Hash -cne $BridgeHash) { throw 'Bridge pin changed' }
function Write-AtomicNewJson([string]$Path, $Value) {
    if (Test-Path -LiteralPath $Path) { throw 'Never overwrite a coordination receipt' }
    $temporary = "$Path.$([Guid]::NewGuid().ToString('N')).tmp"
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $Value -Depth 8) + "`n")
    $stream = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    [IO.File]::Move($temporary, $Path)
}
$waitUntil = [DateTimeOffset]::UtcNow.AddSeconds(120)
Write-Output 'NIS_PUBLISHER_WAITING_FOR_NEW_PINNED_READY; no socket/model operation'
while (-not (Test-Path -LiteralPath $ReadyPath)) {
    if ([DateTimeOffset]::UtcNow -ge $waitUntil) { throw 'No new Ready within publisher window; no GO' }
    Start-Sleep -Milliseconds 200
}
$readyBytes = [IO.File]::ReadAllBytes($ReadyPath)
$readyHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($readyBytes))
$ready = [Text.Encoding]::UTF8.GetString($readyBytes) | ConvertFrom-Json -DateKind String
$readyKeys = @('schemaVersion','status','scope','readyAtUtc','readyNonce','waiterSha256','runnerSha256','adapterSha256','offerPath','goPath','receiptDirectory','timeoutSeconds') | Sort-Object
if ((@($ready.PSObject.Properties.Name | Sort-Object) -join '|') -cne ($readyKeys -join '|')) { throw 'Ready schema mismatch' }
if ($ready.schemaVersion -ne 1 -or $ready.status -cne 'READY' -or $ready.scope -cne 'eip-loopback-control-v5' -or $ready.timeoutSeconds -ne 120) { throw 'Ready identity mismatch' }
if ($ready.readyNonce -cnotmatch '^[0-9a-f]{32}$' -or $ready.offerPath -cne $OfferPath -or $ready.goPath -cne (Join-Path $EipRoot 'control-live-05-go.json') -or $ready.receiptDirectory -cne (Join-Path $EipRoot 'control-live-05')) { throw 'Ready path/nonce mismatch' }
if ($ready.waiterSha256 -cne $BridgeHash -or $ready.runnerSha256 -cne $RunnerHash -or $ready.adapterSha256 -cne $AdapterHash) { throw 'Ready executable pins mismatch' }
$readyAt = [DateTimeOffset]::ParseExact($ready.readyAtUtc,$Format,[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::AssumeUniversal)
if ($readyAt -gt [DateTimeOffset]::UtcNow -or ([DateTimeOffset]::UtcNow-$readyAt).TotalSeconds -ge 120) { throw 'Ready not fresh' }
$main = Get-CimInstance Win32_Process -Filter 'ProcessId=72512'
if ($main.Name -ne 'ollama.exe') { throw 'Main provider identity changed; no GO' }
$workers = @(Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" | Where-Object ParentProcessId -eq 72512 | Select-Object ProcessId,ParentProcessId,CommandLine)
if ($workers.Count -ne 1) { throw 'Main worker set changed; no GO' }
$native = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'native_original_document_driver.py.*attempt-20.*plan-reference' } | Select-Object ProcessId,ParentProcessId)
if ($native.Count -lt 1) { throw 'NIS native client state changed; fresh coordination required' }
$docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
$raw = & $docker inspect NetworkIS NetworkIS-db nis-e2e-app-b7864223eb8f nis-e2e-db-b7864223eb8f
if ($LASTEXITCODE -ne 0) { throw 'Container binding inspection failed' }
$containers = @($raw | ConvertFrom-Json)
if ($containers.Count -ne 4 -or @($containers | Where-Object { -not $_.State.Running }).Count) { throw 'Protected stack state changed' }
if (($containers | Where-Object Name -eq '/NetworkIS').Image -ne 'sha256:c7edda158398ce6c13b5563f56df70575aa61345539fbc23a5aeb847164fca33') { throw 'Production identity changed' }
if (($containers | Where-Object Name -eq '/nis-e2e-app-b7864223eb8f').Image -ne 'sha256:a029cb048847f85d9f901f115463d69446cd307ad9e7e134130d334426552a5f') { throw 'Candidate identity changed' }
$nisPorts = @(11434,13500,13502,13503,15050,56369,64439)
foreach ($worker in $workers) {
    if ($worker.CommandLine -match '--port\s+(\d+)') { $nisPorts += [int]$Matches[1] } else { throw 'Unknown main worker port' }
}
$bindings = @()
foreach ($container in $containers) {
    $bindings += [ordered]@{name=$container.Name;image=$container.Image;ports=$container.NetworkSettings.Ports}
    foreach ($property in $container.NetworkSettings.Ports.PSObject.Properties) {
        foreach ($bound in $property.Value) { if ($bound.HostPort) { $nisPorts += [int]$bound.HostPort } }
    }
}
$nisPorts = @($nisPorts | Sort-Object -Unique)
$allPorts = @(@($nisPorts + @(3000,5000,5100,5433,6379,8002,8013,11435)) | Sort-Object -Unique)
$captured = [DateTimeOffset]::UtcNow
$expires = $captured.AddSeconds(30)
if ($expires -gt $readyAt.AddSeconds(120)) { $expires = $readyAt.AddSeconds(120) }
if ($expires -le [DateTimeOffset]::UtcNow.AddSeconds(5)) { throw 'Insufficient remaining fresh window; no GO' }
Write-AtomicNewJson (Join-Path $PSScriptRoot 'capture.json') ([ordered]@{at=$captured.ToString($Format);main_pid=72512;workers=$workers;native_clients=$native;bindings=$bindings;nisProtectedPorts=$nisPorts;protectedPorts=$allPorts;readySha256=$readyHash;request_interrupted=$false})
if ((Get-FileHash -LiteralPath $ReadyPath -Algorithm SHA256).Hash -cne $readyHash -or (Get-FileHash -LiteralPath $BridgePath -Algorithm SHA256).Hash -cne $BridgeHash -or (Test-Path -LiteralPath "$OfferPath.revoked")) { throw 'Ready/pin changed or revoked; no GO' }
$issued = [DateTimeOffset]::UtcNow
if ($issued -ge $expires) { throw 'Capture expired before publication; no GO' }
$offer = [ordered]@{schemaVersion=1;scope='eip-loopback-control-v5';offerId='nis-v5-resource-file-02';readyPath=$ReadyPath;readySha256=$readyHash;readyNonce=$ready.readyNonce;waiterSha256=$BridgeHash;runnerSha256=$RunnerHash;adapterSha256=$AdapterHash;issuedAtUtc=$issued.ToString($Format);expiresAtUtc=$expires.ToString($Format);protectedPortsCapturedAtUtc=$captured.ToString($Format);protectedPortsMaxAgeSeconds=30;protectedPortsConfirmedComplete=$true;nisProtectedPorts=$nisPorts;protectedPorts=$allPorts;requestInterrupted=$false}
Write-AtomicNewJson $OfferPath $offer
Write-Output (ConvertTo-Json -InputObject ([ordered]@{status='ONE_TIME_ATOMIC_OFFER_PUBLISHED';path=$OfferPath;sha256=(Get-FileHash -LiteralPath $OfferPath -Algorithm SHA256).Hash;capturedAt=$offer.protectedPortsCapturedAtUtc;expiresAt=$offer.expiresAtUtc;request_interrupted=$false}) -Compress)
