"""Import order must also work in a fresh application process, outside pytest."""
import os
from pathlib import Path
import subprocess
import sys


def test_application_cold_start_registers_executable_agent_tools():
    assert os.environ.get('ENGINEERING_TEST_DATABASE_URL') == os.environ.get('DATABASE_URL')
    result = subprocess.run([sys.executable, '-c', '''
from backend.app import create_app
from backend.engineering.agent_tools.services import TOOLS
app = create_app()
required = {'plan_model_import', 'export_project_bundle', 'plan_project_bundle_restore', 'plan_fault_activation',
            'plan_structure_transfer', 'update_project_draft', 'plan_project_model',
            'create_objects_via_proposal', 'generate_functions', 'inspect_project', 'start_simulation'}
assert required <= TOOLS.keys()
assert any(rule.rule.endswith('/agent/project-draft') for rule in app.url_map.iter_rules())
'''], cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
