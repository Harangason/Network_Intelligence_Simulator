@echo off
setlocal

set "ROOT=%~dp0"
set "COMPOSE_FILE=%ROOT%docker-compose.engineering-db.yml"
set "DOCKER_DESKTOP=C:\Program Files\Docker\Docker\Docker Desktop.exe"
set "DOCKER_DIAG=%TEMP%\networkis-docker-info.log"

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker CLI wurde nicht gefunden. Bitte Docker Desktop installieren.
  exit /b 1
)

docker info > "%DOCKER_DIAG%" 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "$svc = Get-Service com.docker.service -ErrorAction SilentlyContinue; if ($svc -and $svc.Status -ne 'Running') { exit 2 }; exit 0" >nul
  if errorlevel 2 (
    echo Docker Desktop Service ist gestoppt.
    echo Versuche Start ueber Docker Desktop CLI...
    start "" /b docker desktop start >nul 2>nul
  )

  if exist "%DOCKER_DESKTOP%" (
    echo Docker Desktop wird gestartet...
    start "" "%DOCKER_DESKTOP%"
  ) else (
    echo Docker laeuft nicht und Docker Desktop wurde nicht unter "%DOCKER_DESKTOP%" gefunden.
    exit /b 1
  )

  echo Warte auf Docker Engine...
  for /l %%I in (1,1,60) do (
    docker info > "%DOCKER_DIAG%" 2>&1
    if not errorlevel 1 goto docker_ready
    powershell -NoProfile -Command "Start-Sleep -Seconds 2" >nul
  )

  echo Docker Engine wurde nicht rechtzeitig bereit.
  echo Letzte Docker-Diagnose:
  type "%DOCKER_DIAG%"
  findstr /i "dockerInference Inference" "%DOCKER_DIAG%" >nul 2>nul
  if not errorlevel 1 (
    echo.
    echo Hinweis: Docker Desktop haengt wahrscheinlich am dockerInference-Listener.
    echo Docker Desktop vollstaendig beenden, neu starten und die Inference-/AI-Komponente
    echo in Docker Desktop reparieren oder deaktivieren.
  )
  echo Falls Docker Desktop sichtbar ist, oeffne es einmal manuell und pruefe, ob der Dienst
  echo "Docker Desktop Service" gestartet werden darf. Danach diesen Batch erneut ausfuehren.
  exit /b 1
)

:docker_ready
echo Starte Engineering-Postgres...
docker compose -f "%COMPOSE_FILE%" up -d
if errorlevel 1 exit /b 1

echo Warte auf Datenbank-Healthcheck...
for /l %%I in (1,1,60) do (
  docker exec network-simulator-engineering-db pg_isready -U eip_user -d eip_blocker >nul 2>nul
  if not errorlevel 1 goto db_ready
  powershell -NoProfile -Command "Start-Sleep -Seconds 1" >nul
)

echo Datenbankcontainer laeuft, aber pg_isready wurde nicht rechtzeitig gruen.
docker ps --filter "name=network-simulator-engineering-db"
exit /b 1

:db_ready
echo Engineering-Datenbank ist erreichbar:
echo postgresql+psycopg://eip_user:localDockerOnly7a1c9e4f2b8d6a3c5e0f@127.0.0.1:5432/eip_blocker
exit /b 0
