@echo off
setlocal

set "ROOT=%~dp0"
set "COMPOSE_FILE=%ROOT%docker-compose.networkis.yml"
set "DOCKER_DESKTOP=C:\Program Files\Docker\Docker\Docker Desktop.exe"
set "FRONTEND_PORT=13500"
set "BACKEND_PORT=15050"
set "DOCKER_DIAG=%TEMP%\networkis-docker-info.log"

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker CLI wurde nicht gefunden. Bitte Docker Desktop installieren.
  exit /b 1
)

docker info > "%DOCKER_DIAG%" 2>&1
if errorlevel 1 (
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
  echo Bitte Docker Desktop einmal manuell starten und diesen Batch erneut ausfuehren.
  exit /b 1
)

:docker_ready
for %%P in (%FRONTEND_PORT% %BACKEND_PORT%) do (
  powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %%P -State Listen -ErrorAction SilentlyContinue) { exit 1 }"
  if errorlevel 1 (
    echo Port %%P ist bereits belegt. NetworkIS wird nicht gestartet.
    exit /b 1
  )
)

echo Starte NetworkIS inklusive Engineering-Datenbank...
docker compose -f "%COMPOSE_FILE%" up -d --build
if errorlevel 1 exit /b 1

echo.
echo NetworkIS laeuft unter:
echo   http://127.0.0.1:%FRONTEND_PORT%
echo.
echo Logs:
echo   docker logs -f NetworkIS
echo.
exit /b 0
