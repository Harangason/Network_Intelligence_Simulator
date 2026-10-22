"""Isolated preparation checks only; the final gate uses canonical sources."""
from pathlib import Path
import subprocess
import sys

base = Path(__file__).parent
args = [sys.executable, '-u', str(base / 'isolated_diagnostics.py'), '--',
        '-p', 'docs.implementation-workloads.robotics-document-handoff-20261016.staged_overlay_plugin',
        '--import-mode=importlib', str(base / 'staged/backend/tests/test_qwen_document_intake.py'),
        str(base / 'staged/backend/tests/test_wizard_generation.py'),
        str(base / 'staged/backend/tests/test_agent_chat_ux.py'),
        '-k', 'robotics_markdown or markdown_test_sections or reviewed_document or typed_document_duties or typed_function_preserves or safety_and_context or safety_plc or markdown_context_validation or same_component_name or complete_reviewed_document_request or durable_continuation_rejects',
        '-vv', '-o', 'faulthandler_timeout=90']
with (base / 'staged-targeted-current.log').open('w', encoding='utf-8') as log:
    result = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT)
print({'preparation_only': True, 'exit_code': result.returncode})
raise SystemExit(result.returncode)
