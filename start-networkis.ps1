$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigFile = Join-Path $Root "config\networkis.resources.json"
if (-not (Test-Path -LiteralPath $ConfigFile)) {
  throw "Config nicht gefunden: $ConfigFile"
}

$Config = Get-Content -LiteralPath $ConfigFile -Raw | ConvertFrom-Json
$ComposeFile = Join-Path $Root $Config.docker.compose_file
$GpuComposeFile = if ($Config.docker.gpu_compose_file) { Join-Path $Root $Config.docker.gpu_compose_file } else { $null }
$Docker = [string]$Config.paths.docker_cli
$Compose = [string]$Config.paths.docker_compose
$DockerDesktop = [string]$Config.paths.docker_desktop
$Ollama = [string]$Config.paths.ollama_cli
$FrontendPort = [int]$Config.docker.frontend_port
$BackendPort = [int]$Config.docker.backend_port
$HostMetricsPort = if ($Config.docker.host_metrics_port) { [int]$Config.docker.host_metrics_port } else { 13502 }
$DockerDiag = Join-Path $env:TEMP "networkis-docker-info.log"

function Test-ReadablePath($Path) {
  try {
    return [bool](Test-Path -LiteralPath $Path)
  } catch {
    return $true
  }
}

if (-not (Test-ReadablePath $Docker)) {
  $Docker = (Get-Command docker -ErrorAction SilentlyContinue).Source
}
if (-not $Docker) {
  throw "Docker CLI wurde nicht gefunden."
}
if (-not (Test-ReadablePath $Compose)) {
  throw "Docker Compose wurde nicht gefunden: $Compose"
}

$env:AI_PROVIDER = [string]$Config.ai.active_provider
$env:LOCAL_AI_BASE_URL = [string]$Config.ai.providers.ollama.base_url_docker
$env:LOCAL_AI_MODEL = [string]$Config.ai.providers.ollama.model
$env:LOCAL_AI_FAST_MODEL = [string]$Config.ai.providers.ollama.fast_model
$env:LOCAL_AI_API_KEY = [string]$Config.ai.providers.ollama.api_key
$env:CLOUD_ESCALATION = [string]$Config.ai.cloud_escalation
$env:NVIDIA_AI_MODEL = [string]$Config.ai.providers.nvidia.model
$env:OLLAMA_MODELS = [string]$Config.paths.ollama_models
$env:OLLAMA_CONTEXT_LENGTH = [string]$Config.resources.ollama_context_length
$env:OLLAMA_KEEP_ALIVE = [string]$Config.resources.ollama_keep_alive
$env:OLLAMA_FAST_KEEP_ALIVE = [string]$Config.resources.ollama_fast_keep_alive
$env:NUMERIC_ACCELERATOR = [string]$Config.resources.numeric_accelerator
$env:NUMERIC_ACCELERATOR_MIN_ITEMS = [string]$Config.resources.numeric_accelerator_min_items
$env:WAITRESS_THREADS = [string]$Config.resources.waitress_threads
$env:SIMULATION_EXECUTOR = [string]$Config.resources.simulation_executor
$env:SIMULATION_WORKERS = [string]$Config.resources.simulation_workers
$env:NETWORKIS_SERVICE_RESTARTS = [string]$Config.resources.service_restarts
$NumericThreads = [string]$Config.resources.numeric_threads
$env:OMP_NUM_THREADS = $NumericThreads
$env:OPENBLAS_NUM_THREADS = $NumericThreads
$env:MKL_NUM_THREADS = $NumericThreads
$env:NUMEXPR_NUM_THREADS = $NumericThreads

function Wait-DockerEngine {
  & $Docker info *> $DockerDiag
  if ($LASTEXITCODE -eq 0) {
    return
  }

  if (Test-ReadablePath $DockerDesktop) {
    Write-Host "Docker Desktop wird gestartet..."
    Start-Process -FilePath $DockerDesktop -WindowStyle Hidden
  } else {
    throw "Docker laeuft nicht und Docker Desktop wurde nicht gefunden: $DockerDesktop"
  }

  Write-Host "Warte auf Docker Engine..."
  $ready = $false
  for ($i = 0; $i -lt 60; $i++) {
    & $Docker info *> $DockerDiag
    if ($LASTEXITCODE -eq 0) {
      $ready = $true
      break
    }
    Start-Sleep -Seconds 2
  }
  if (-not $ready) {
    Get-Content -LiteralPath $DockerDiag -ErrorAction SilentlyContinue
    throw "Docker Engine wurde nicht rechtzeitig bereit."
  }
}

Write-Host "Pruefe Docker Engine..."
Wait-DockerEngine
Write-Host "Docker Engine ist bereit."

$HostMetricsScript = Join-Path $Root "host_metrics_bridge.py"
$HostMetricsHealthUrl = "http://127.0.0.1:$HostMetricsPort/health"
$HostMetricsReady = $false
try {
  $HostMetricsReady = (Invoke-RestMethod -Uri $HostMetricsHealthUrl -TimeoutSec 1).ok -eq $true
} catch {}
if (-not $HostMetricsReady) {
  $HostPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
  if (-not (Test-ReadablePath $HostPython)) {
    $HostPython = (Get-Command python -ErrorAction SilentlyContinue).Source
  }
  if (-not $HostPython) {
    throw "Python fuer die Windows-Hosttelemetrie wurde nicht gefunden."
  }
  Write-Host "Starte Windows-Hosttelemetrie..."
  Start-Process -FilePath $HostPython -ArgumentList @($HostMetricsScript, "--port", $HostMetricsPort) -WorkingDirectory $Root -WindowStyle Hidden
  for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 250
    try {
      if ((Invoke-RestMethod -Uri $HostMetricsHealthUrl -TimeoutSec 1).ok -eq $true) {
        $HostMetricsReady = $true
        break
      }
    } catch {}
  }
}
if (-not $HostMetricsReady) {
  throw "Windows-Hosttelemetrie ist auf Port $HostMetricsPort nicht erreichbar."
}
$env:NETWORKIS_HOST_METRICS_URL = "http://host.docker.internal:$HostMetricsPort/metrics"
Write-Host "Windows-Hosttelemetrie ist bereit."

if (Test-ReadablePath $Ollama) {
  try {
    Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
  } catch {
    Write-Host "Ollama wird gestartet..."
    Start-Process -FilePath $Ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
  }
  try {
    $WarmPayload = @{
      model = [string]$Config.ai.providers.ollama.fast_model
      prompt = ""
      stream = $false
      keep_alive = [string]$Config.resources.ollama_fast_keep_alive
    } | ConvertTo-Json -Compress
    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:11434/api/generate" -ContentType "application/json" -Body $WarmPayload -TimeoutSec 180 | Out-Null
    Write-Host "Lokales Semantikmodell ist vorgewärmt ($($Config.ai.providers.ollama.fast_model))."
  } catch {
    Write-Warning "Semantikmodell konnte nicht vorgewärmt werden: $($_.Exception.Message)"
  }
}

$networkisRunning = (& $Docker ps --filter "name=^/NetworkIS$" --format "{{.Names}}") -contains "NetworkIS"
if (-not $networkisRunning) {
  foreach ($Port in @($FrontendPort, $BackendPort)) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
      throw "Port $Port ist bereits belegt. NetworkIS wird nicht gestartet."
    }
  }
}

Write-Host "Starte NetworkIS inklusive Engineering-Datenbank..."
Push-Location $Root
try {
  $ComposeArguments = @("-f", $ComposeFile)
  $GpuRuntimeAvailable = ((& $Docker info --format "{{json .Runtimes}}" 2>$null) -match '"nvidia"')
  if ($GpuRuntimeAvailable -and $GpuComposeFile -and (Test-ReadablePath $GpuComposeFile)) {
    $ComposeArguments += @("-f", $GpuComposeFile)
    Write-Host "CUDA-Rechenpfad wird für NetworkIS aktiviert."
  } else {
    $env:NUMERIC_ACCELERATOR = "cpu"
    Write-Host "Keine Docker-CUDA-Runtime verfügbar; CPU-Fallback bleibt aktiv."
  }
  & $Compose @ComposeArguments up -d --build
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "NetworkIS laeuft unter:"
Write-Host "  http://127.0.0.1:$FrontendPort"
Write-Host ""
Write-Host "Logs:"
Write-Host "  docker logs -f NetworkIS"
