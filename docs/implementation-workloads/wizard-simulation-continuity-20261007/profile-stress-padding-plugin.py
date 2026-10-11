"""Capture the failed stress fixture at its unchanged channel assertion."""
import json
from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def capture_stress(monkeypatch, request):
    if request.node.name != 'test_full_captured_model_and_all_routing_validate_without_rewriting_inputs':
        return
    from backend.nis.agent.tools import wizard_generation as generation, model
    from backend.nis.engineering.capacity.service import CapacityTimingService
    from backend.nis.workflow.services.service import WorkflowStatusService
    from backend.nis.engineering.projects.project_context import current_project_id
    original = generation.generate_capacity_network_repair
    def capture(arguments):
        project = current_project_id()
        state = WorkflowStatusService(project).get()
        plan = generation.plan_capacity_remediation(arguments)
        result = original(arguments)
        (Path(__file__).parent/'stress-padding-diagnostic.json').write_text(json.dumps({
            'parameters': state['parameters'], 'capacity': CapacityTimingService(project).latest(),
            'distribution': plan, 'proposal': result,
            'messages': model.objects('Message'),
        }, default=str, indent=2), encoding='utf-8')
        return result
    monkeypatch.setattr(generation, 'generate_capacity_network_repair', capture)
