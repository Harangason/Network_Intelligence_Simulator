"""Verify real project files against a fresh disposable test database."""
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).parent
command = [sys.executable, '-u', 'scripts/run-isolated-tests.py', '--',
           'backend/tests/test_qwen_document_intake.py', 'backend/tests/test_agent_chat_ux.py',
           'backend/tests/test_wizard_generation.py', 'backend/tests/test_functional_device_design.py',
           'backend/tests/test_project_structure.py',
           '-k', 'not combined_wizard_creates_validated_model_without_reasoner',
           '-q', '--junitxml=' + str(OUT / 'targeted-backend.xml')]
# The mass-model case runs in the mandatory full release gate, together with
# all other backend and browser/HTTP cases; it is not duplicated here.
with (OUT / 'targeted-backend.log').open('w', encoding='utf-8') as log:
    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
print({'canonical_project_files': True, 'exit_code': result.returncode})
raise SystemExit(result.returncode)
