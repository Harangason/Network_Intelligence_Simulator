"""Check the numeric-context delta and existing intake regressions in isolation."""
from pathlib import Path
import subprocess
import sys

base = Path(__file__).parent
command = [sys.executable, '-u', str(base / 'isolated_diagnostics.py'), '--',
           '-p', 'docs.implementation-workloads.robotics-document-handoff-20261016.staged_overlay_plugin',
           '--import-mode=importlib', str(base / 'staged/backend/tests/test_qwen_document_intake.py'),
           str(base / 'staged/backend/tests/test_wizard_generation.py'),
           '-k', 'test_qwen_document_intake or reviewed_document_functions or typed_document_duties or typed_function_preserves or numeric_controller_heading',
           '-q', '--junitxml=' + str(base / 'staged-numbered-backend.xml')]
with (base / 'staged-numbered-backend.log').open('w', encoding='utf-8') as log:
    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
print({'preparation_only': True, 'exit_code': result.returncode})
raise SystemExit(result.returncode)
