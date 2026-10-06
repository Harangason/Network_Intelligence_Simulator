"""Replay the confirmed routing request in a rolled-back transaction."""

import sys as _entry_sys
from pathlib import Path as _EntryPath
_entry_sys.path.insert(0, str(_EntryPath(__file__).resolve().parents[1]))
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.nis.infrastructure.persistence.db import RequestUnit
from backend.nis.infrastructure.persistence.db import get_connection
from backend.nis.infrastructure.persistence.db import close_pool
from backend.nis.engineering.projects.project_context import activate_project
from backend.nis.engineering.projects.project_context import reset_project
from backend.nis.agent.tools.wizard_generation import generate_routing
from backend.nis.agent.tools.proposal_service import validate
from backend.nis.simulation.numeric_acceleration import acceleration_status
project = 'network-project-20260909132301897-134da9ff'
token = activate_project(project)
unit = RequestUnit(project)
try:
    with get_connection() as connection:
        row = connection.execute('SELECT context FROM engineering_workflow_projects WHERE project_id=%s', (project,)).fetchone()
    prompt = (row['context'].get('agent_wizard_status') or {}).get('agent_prompt')
    if not prompt:
        raise RuntimeError('Der bestätigte Wizard-Prompt fehlt.')
    start = time.perf_counter()
    result = generate_routing({'prompt': prompt})
    generated_seconds = round(time.perf_counter()-start, 3)
    result = validate(result['proposal_id'])
    print(json.dumps({'generation_seconds': generated_seconds, 'elapsed_seconds': round(time.perf_counter()-start, 3), 'status': result.get('status'),
        'route_count': len(result.get('changes') or []), 'validation': result.get('validation_result'),
        'acceleration': acceleration_status(), 'persisted_changes': False}, default=str))
finally:
    unit.close()
    reset_project(token)
    close_pool()
