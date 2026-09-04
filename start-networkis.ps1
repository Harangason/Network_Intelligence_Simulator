$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigFile = Join-Path $Root "config\networkis.resources.json"
if (-not (Test-Path -LiteralPath $ConfigFile)) {
  throw "Config nicht gefunden: $ConfigFile"
}

$Config = Get-Content -LiteralPath $ConfigFile -Raw | ConvertFrom-Json
$ComposeFile = Join-Path $Root $Config.docker.compose_file
$Docker = [string]$Config.paths.docker_cli
$Compose = [string]$Config.paths.docker_compose
$DockerDesktop = [string]$Config.paths.docker_desktop
$Ollama = [string]$Config.paths.ollama_cli
$FrontendPort = [int]$Config.docker.frontend_port
$BackendPort = [int]$Config.docker.backend_port
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

if (Test-ReadablePath $Ollama) {
  try {
    Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
  } catch {
    Write-Host "Ollama wird gestartet..."
    Start-Process -FilePath $Ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
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
  & $Compose -f $ComposeFile up -d --build
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
