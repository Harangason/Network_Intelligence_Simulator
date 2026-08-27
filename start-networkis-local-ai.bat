@echo off
setlocal

set "ROOT=%~dp0"
if not defined AI_PROVIDER set "AI_PROVIDER=hybrid-demand"
if not defined LOCAL_AI_BASE_URL set "LOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1"
if not defined LOCAL_AI_MODEL set "LOCAL_AI_MODEL=qwen3.8:27b"
if not defined CLOUD_ESCALATION set "CLOUD_ESCALATION=on_failure"
if not defined OLLAMA_MODELS set "OLLAMA_MODELS=I:\engineering-intelligence-platform\models\ollama"
if not defined OLLAMA_CONTEXT_LENGTH set "OLLAMA_CONTEXT_LENGTH=8192"
if not defined OLLAMA_KEEP_ALIVE set "OLLAMA_KEEP_ALIVE=10m"
if not defined NETWORKIS_SHARED_ENV_FILE set "NETWORKIS_SHARED_ENV_FILE=%USERPROFILE%\PycharmProjects\.env"
if not defined WAITRESS_THREADS set "WAITRESS_THREADS=16"
if not defined SIMULATION_EXECUTOR set "SIMULATION_EXECUTOR=process"
if not defined SIMULATION_WORKERS set "SIMULATION_WORKERS=12"
set "OMP_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
set "NUMEXPR_NUM_THREADS=1"

cd /d "%ROOT%"
if exist "%ROOT%backend\.venv\Scripts\python.exe" (
  "%ROOT%backend\.venv\Scripts\python.exe" generate_realistic_communication_tool.py web
) else (
  uv run --project backend python generate_realistic_communication_tool.py web
)
