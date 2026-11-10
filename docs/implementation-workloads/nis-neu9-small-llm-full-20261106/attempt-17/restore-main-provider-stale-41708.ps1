$ErrorActionPreference = 'Stop'
$taskOutput = $PSScriptRoot
function Save-Phase($name, $value) {
  $value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskOutput $name) -Encoding utf8
}
$main = Get-CimInstance Win32_Process -Filter 'ProcessId=67880'
$desktop = Get-CimInstance Win32_Process -Filter 'ProcessId=67856'
$worker = Get-CimInstance Win32_Process -Filter 'ProcessId=41708'
if ($main.Name -ne 'ollama.exe' -or $main.ParentProcessId -ne 67856 -or
    $desktop.Name -ne 'ollama app.exe' -or $worker.Name -ne 'llama-server.exe' -or
    $worker.ParentProcessId -ne 67880 -or
    $main.CreationDate.ToUniversalTime().ToString('O') -ne '2026-11-08T15:33:27.1540040Z') { throw 'Process identity drift' }
$owners = @(Get-NetTCPConnection -LocalPort 11434 | Where-Object { $_.RemotePort -eq 0 } | Select-Object -ExpandProperty OwningProcess -Unique)
if ($owners.Count -ne 1 -or $owners[0] -ne 67880) { throw 'Main listener identity drift' }
$slots = @(Invoke-RestMethod http://127.0.0.1:63235/slots -TimeoutSec 15)
if (@($slots | Where-Object { $_.is_processing }).Count -ne 0) { throw 'Main worker busy; no change' }
$loaded = Invoke-RestMethod http://127.0.0.1:11434/api/ps -TimeoutSec 15
if ($loaded.models.Count -ne 1 -or $loaded.models[0].name -ne 'qwen3.5:9b') { throw 'Loaded model drift' }
Save-Phase 'provider-restore-before.json' @{
  at = [DateTime]::UtcNow.ToString('O'); main = $main | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine,CreationDate
  desktop = $desktop | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CreationDate
  worker = $worker | Select-Object ProcessId,ParentProcessId,Name,CommandLine,CreationDate
  slots = $slots | Select-Object id,id_task,is_processing,n_ctx; loaded = $loaded
  global_environment_changed = $false
}
$unload = Invoke-RestMethod http://127.0.0.1:11434/api/generate -Method Post -ContentType 'application/json' -Body '{"model":"qwen3.5:9b","prompt":"","stream":false,"keep_alive":0}' -TimeoutSec 120
Save-Phase 'provider-regular-unload.json' $unload
if (-not $unload.done -or $unload.response) { throw 'Unexpected unload response' }
for ($attempt=0; $attempt -lt 50; $attempt++) {
  $remaining = @(Get-CimInstance Win32_Process -Filter 'ParentProcessId=67880' | Where-Object Name -eq 'llama-server.exe')
  if ($remaining.Count -eq 0) { break }
  Start-Sleep -Milliseconds 200
}
if ($remaining.Count -ne 0 -or (Invoke-RestMethod http://127.0.0.1:11434/api/ps -TimeoutSec 15).models.Count -ne 0) { throw 'Worker has not unloaded; no process stop' }
# The exact idle desktop owner otherwise respawns a server with its old environment.
Stop-Process -Id 67856
$oldMain = Get-CimInstance Win32_Process -Filter 'ProcessId=67880'
if ($oldMain) {
  if ($oldMain.Name -ne $main.Name -or $oldMain.CreationDate -ne $main.CreationDate) { throw 'Main identity changed after desktop exit' }
  Stop-Process -Id 67880
}
for ($attempt=0; $attempt -lt 50; $attempt++) {
  $listeners = @(Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue | Where-Object { $_.RemotePort -eq 0 })
  if ($listeners.Count -eq 0) { break }
  Start-Sleep -Milliseconds 200
}
if ($listeners.Count -ne 0) { throw 'Listener remained; do not launch another provider' }
$env:OLLAMA_KV_CACHE_TYPE = 'q8_0'
$env:OLLAMA_FLASH_ATTENTION = '1'
$started = Start-Process -FilePath $desktop.ExecutablePath -WorkingDirectory (Get-Location).Path -WindowStyle Hidden -PassThru
Save-Phase 'provider-desktop-relaunch.json' @{ at=[DateTime]::UtcNow.ToString('O'); desktop_pid=$started.Id; process_environment=@{OLLAMA_KV_CACHE_TYPE='q8_0';OLLAMA_FLASH_ATTENTION='1'}; global_environment_changed=$false }
$ready = $false
for ($attempt=0; $attempt -lt 60; $attempt++) {
  try { $version=Invoke-RestMethod http://127.0.0.1:11434/api/version -TimeoutSec 1; $ready=$true; break } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready -or $version.version -ne '0.33.1') { throw 'Relaunched provider not ready at expected version' }
$load = Invoke-RestMethod http://127.0.0.1:11434/api/generate -Method Post -ContentType 'application/json' -Body '{"model":"qwen3.5:9b","prompt":"","stream":false,"keep_alive":"10m","options":{"num_ctx":131072}}' -TimeoutSec 1200
Save-Phase 'provider-restored-load.json' $load
if (-not $load.done -or $load.response -or $load.eval_count) { throw 'Unexpected load generation' }
$owners = @(Get-NetTCPConnection -LocalPort 11434 | Where-Object { $_.RemotePort -eq 0 } | Select-Object -ExpandProperty OwningProcess -Unique)
if ($owners.Count -ne 1) { throw 'Ambiguous restored main listener' }
$newMain = Get-CimInstance Win32_Process -Filter "ProcessId=$($owners[0])"
$workers = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($owners[0])" | Where-Object Name -eq 'llama-server.exe')
if ($workers.Count -ne 1 -or $newMain.Name -ne 'ollama.exe') { throw 'Unexpected restored worker topology' }
$line = $workers[0].CommandLine
if ($line -notmatch '--cache-type-k q8_0' -or $line -notmatch '--cache-type-v q8_0' -or
    $line -notmatch '--flash-attn on' -or $line -notmatch '-c 131072' -or $line -notmatch '--port (\d+)') { throw 'Restored worker options do not match verified fast baseline' }
$workerPort = [regex]::Match($line, '--port (\d+)').Groups[1].Value
$finalSlots = @(Invoke-RestMethod "http://127.0.0.1:$workerPort/slots" -TimeoutSec 15)
if (@($finalSlots | Where-Object { $_.is_processing -or $_.n_ctx -ne 131072 }).Count) { throw 'Restored worker not idle at exact context' }
Save-Phase 'provider-restoration-result.json' @{
  status='PREVIOUS_FAST_MAIN_PROVIDER_OPTIONS_RESTORED'; at=[DateTime]::UtcNow.ToString('O')
  main=$newMain | Select-Object ProcessId,ParentProcessId,Name,CommandLine,CreationDate
  worker=$workers[0] | Select-Object ProcessId,ParentProcessId,Name,CommandLine,CreationDate
  slots=$finalSlots | Select-Object id,id_task,is_processing,n_ctx
  global_environment_changed=$false; nis_eip_docker_restarted=$false
}
Write-Output 'PREVIOUS_FAST_MAIN_PROVIDER_OPTIONS_RESTORED'
