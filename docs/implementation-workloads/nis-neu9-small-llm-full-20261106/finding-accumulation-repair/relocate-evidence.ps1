$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath 'I:/PycharmProjects/My_first_Network_Simulator').Path.TrimEnd('\')
$archive = 'F:\CodexOrdner\visualizations\2026\10\09\01a11f88-d6c9-7b63-bec3-26450a86e52c\nis-neu9-small-llm-20261106\space-recovery-20261108'
$report = Join-Path $root 'docs/implementation-workloads/nis-neu9-small-llm-full-20261106/finding-accumulation-repair/evidence-relocation.json'
$relativeTargets = @(
 'backend/test-output/release-gates/studio-toolbar-performance-full/42a674cad1bc/browser',
 'backend/test-output/release-gates/delivery-d922081664af/897531633817/browser',
 'backend/test-output/release-gates/delivery-6ca4ab5fb4eb/bb493012fb1c/browser',
 'work/archived-candidates/robotics-document-handoff-20261016'
)
if (Test-Path -LiteralPath $report) { throw 'Existing relocation report: inspect before resuming' }
$state = [ordered]@{ at=[DateTime]::UtcNow.ToString('o'); status='COPYING'; before_free=(Get-PSDrive I).Free; targets=@(); no_image_removed=$true; receipts_and_logs_unchanged=$true }
function Save-Report { $state | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $report -Encoding utf8 }
foreach ($relative in $relativeTargets) {
 $source = (Resolve-Path -LiteralPath (Join-Path $root $relative)).Path
 if (-not $source.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Source escapes workspace' }
 $item = Get-Item -LiteralPath $source -Force
 if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Source is reparse point' }
 $all = @(Get-ChildItem -LiteralPath $source -Recurse -Force)
 if (@($all | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw 'Nested reparse point' }
 $active = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -notin @('pwsh.exe','powershell.exe') -and $_.CommandLine -and $_.CommandLine.Contains($source) })
 if ($active.Count) { throw 'Active process references target' }
 $destination = [IO.Path]::GetFullPath((Join-Path $archive $relative))
 if (-not $destination.StartsWith($archive+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Archive escapes named directory' }
 if (Test-Path -LiteralPath $destination) { throw 'Destination already exists' }
 $row = [ordered]@{ source=$source; destination=$destination; status='HASHING'; bytes=0; files=@() }
 foreach ($file in @($all | Where-Object { -not $_.PSIsContainer })) {
  $row.files += [ordered]@{ relative=$file.FullName.Substring($source.Length+1); bytes=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
  $row.bytes += $file.Length
 }
 $state.targets += $row; Save-Report
 New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
 Copy-Item -LiteralPath $source -Destination $destination -Recurse
 $copied = @(Get-ChildItem -LiteralPath $destination -Recurse -Force -File)
 if ($copied.Count -ne $row.files.Count) { throw 'Archive file count mismatch' }
 foreach ($file in $row.files) {
  $copy = Join-Path $destination $file.relative
  if ((Get-Item -LiteralPath $copy).Length -ne $file.bytes -or (Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) { throw 'Archive hash mismatch' }
  if ((Get-FileHash -LiteralPath (Join-Path $source $file.relative) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) { throw 'Source changed while copying' }
 }
 $row.status='COPY_VERIFIED'; Save-Report
 # All destructive targets were resolved above; no computed cross-shell deletion.
 if ((Resolve-Path -LiteralPath $source).Path -ne $source -or -not $source.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Source resolution changed' }
 Remove-Item -LiteralPath $source -Recurse
 New-Item -ItemType Junction -Path $source -Target $destination | Out-Null
 foreach ($file in $row.files) {
  if ((Get-FileHash -LiteralPath (Join-Path $source $file.relative) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) { throw 'Restored path hash mismatch' }
 }
 $row.status='RELOCATED_PATH_PRESERVED_HASH_VERIFIED'; Save-Report
 Write-Output ($row | Select-Object source,destination,status,bytes | ConvertTo-Json -Compress)
}
$state.status='COMPLETE'; $state.after_free=(Get-PSDrive I).Free; Save-Report
Write-Output ('FREE_BYTES='+$state.after_free)
