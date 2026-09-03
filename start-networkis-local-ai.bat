@echo off
setlocal

set "ROOT=%~dp0"
set "CONFIG_FILE=%ROOT%config\networkis.resources.json"
if exist "%CONFIG_FILE%" (
  for /f "usebackq tokens=1,* delims==" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$c = Get-Content -LiteralPath '%CONFIG_FILE%' -Raw | ConvertFrom-Json; 'AI_PROVIDER=' + $c.ai.active_provider; 'LOCAL_AI_BASE_URL=' + $c.ai.providers.ollama.base_url_windows; 'LOCAL_AI_MODEL=' + $c.ai.providers.ollama.model; 'LOCAL_AI_FAST_MODEL=' + $c.ai.providers.ollama.fast_model; 'LOCAL_AI_API_KEY=' + $c.ai.providers.ollama.api_key; 'CLOUD_ESCALATION=' + $c.ai.cloud_escalation; 'OLLAMA_MODELS=' + $c.paths.ollama_models; 'OLLAMA_CONTEXT_LENGTH=' + $c.resources.ollama_context_length; 'OLLAMA_KEEP_ALIVE=' + $c.resources.ollama_keep_alive; 'WAITRESS_THREADS=' + $c.resources.waitress_threads; 'SIMULATION_EXECUTOR=' + $c.resources.simulation_executor; 'SIMULATION_WORKERS=' + $c.resources.simulation_workers; 'NETWORKIS_SERVICE_RESTARTS=' + $c.resources.service_restarts; 'NUMERIC_THREADS=' + $c.resources.numeric_threads"`) do if not defined %%A set "%%A=%%B"
)
if not defined AI_PROVIDER set "AI_PROVIDER=hybrid-demand"
if not defined LOCAL_AI_BASE_URL set "LOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1"
if not defined LOCAL_AI_MODEL set "LOCAL_AI_MODEL=qwen3.8:27b"
if not defined LOCAL_AI_FAST_MODEL set "LOCAL_AI_FAST_MODEL=llama3.1:8b"
if not defined CLOUD_ESCALATION set "CLOUD_ESCALATION=on_failure"
if not defined OLLAMA_MODELS set "OLLAMA_MODELS=I:\engineering-intelligence-platform\models\ollama"
if not defined OLLAMA_CONTEXT_LENGTH set "OLLAMA_CONTEXT_LENGTH=8192"
if not defined OLLAMA_KEEP_ALIVE set "OLLAMA_KEEP_ALIVE=10m"
if not defined NETWORKIS_SHARED_ENV_FILE set "NETWORKIS_SHARED_ENV_FILE=%USERPROFILE%\PycharmProjects\.env"
if not defined WAITRESS_THREADS set "WAITRESS_THREADS=16"
if not defined SIMULATION_EXECUTOR set "SIMULATION_EXECUTOR=process"
if not defined SIMULATION_WORKERS set "SIMULATION_WORKERS=12"
if not defined NETWORKIS_SERVICE_RESTARTS set "NETWORKIS_SERVICE_RESTARTS=5"
if not defined UV_CACHE_DIR set "UV_CACHE_DIR=%ROOT%.uv-cache"
if not defined NUMERIC_THREADS set "NUMERIC_THREADS=1"
set "OMP_NUM_THREADS=%NUMERIC_THREADS%"
set "OPENBLAS_NUM_THREADS=%NUMERIC_THREADS%"
set "MKL_NUM_THREADS=%NUMERIC_THREADS%"
set "NUMEXPR_NUM_THREADS=%NUMERIC_THREADS%"

cd /d "%ROOT%"
if exist "%ROOT%backend\.venv\Scripts\python.exe" (
  "%ROOT%backend\.venv\Scripts\python.exe" generate_realistic_communication_tool.py doctor
  "%ROOT%backend\.venv\Scripts\python.exe" generate_realistic_communication_tool.py web
) else (
  uv run --project backend python generate_realistic_communication_tool.py doctor
  uv run --project backend python generate_realistic_communication_tool.py web
)
