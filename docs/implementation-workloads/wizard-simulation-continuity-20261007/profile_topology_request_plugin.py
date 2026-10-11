"""Observe the real large SQL topology validation; stop explicitly as a diagnostic."""
import cProfile
import json
import pstats
import time
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def observe_topology_request(monkeypatch, request):
    if request.node.name != 'test_full_captured_model_and_all_routing_validate_without_rewriting_inputs':
        return
    from backend.nis.agent.tools import proposal_service
    from backend.nis.workflow.services.service import WorkflowStatusService
    from backend.nis.engineering.projects.project_context import current_project_id
    original = proposal_service.validate
    output = Path(__file__).parent

    def observed(proposal_id):
        row = proposal_service.legacy.get_proposal(proposal_id)
        if row['proposal_type'] != 'WIZARD_NETWORK_TOPOLOGY':
            return original(proposal_id)
        # A saved parameter revision makes the existing topology proposal stale,
        # as in the browser return. This write targets only the isolated SQL DB.
        saved = json.loads((output/'topology-return-saved-parameters.json').read_text(encoding='utf-8'))['parameters']
        service = WorkflowStatusService(current_project_id())
        previous_parameters = service.get()['parameters']
        service.save_parameters({**previous_parameters, **{key:saved[key] for key in
            ('technology_parameters','simulation_parameter_assumptions','seed') if key in saved}})
        assert service.get()['parameters'].get('networks') == previous_parameters.get('networks')
        from flask import Flask
        from backend.nis.interfaces.http.engineering import parameter_review_route
        review_profiler = cProfile.Profile()
        review_start = time.perf_counter()
        with Flask(__name__).test_request_context('/api/engineering/workflow/parameters/review?proposal='+proposal_id,
                headers={'X-Project-ID':current_project_id()}):
            response = review_profiler.runcall(parameter_review_route)
            body = response[0].get_json() if isinstance(response,tuple) else response.get_json()
        review_profiler.dump_stats(str(output/'topology-native-review-route.prof'))
        with (output/'topology-native-review-route-profile.txt').open('w',encoding='utf-8') as stream:
            stream.write(json.dumps({'elapsed_s':time.perf_counter()-review_start,
                'findings':len(body.get('findings',[])), 'groups':len(body.get('simulation_capacity',[]))})+'\n')
            pstats.Stats(review_profiler,stream=stream).sort_stats('cumulative').print_stats(85)
        (output/'topology-native-review-route-result.json').write_text(json.dumps(body,default=str),encoding='utf-8')
        snapshot = proposal_service.model()
        (output/'topology-native-review-input.json').write_text(json.dumps({'workflow':WorkflowStatusService(current_project_id()).get(),
                'model':snapshot,'proposal':proposal_service.get(proposal_id)},default=str),encoding='utf-8')
        profiler = cProfile.Profile()
        started = time.perf_counter()
        result = profiler.runcall(original, proposal_id)
        profiler.dump_stats(str(output/'topology-native-return.prof'))
        (output/'topology-native-return-validation-result.json').write_text(json.dumps(result['validation_result'],default=str),encoding='utf-8')
        with (output/'topology-native-return-profile.txt').open('w',encoding='utf-8') as stream:
            stream.write(json.dumps({'elapsed_s':time.perf_counter()-started,
                'status':result['status'], 'changes':len(result['changes']),
                'valid':result['validation_result']['valid']})+'\n')
            pstats.Stats(profiler,stream=stream).sort_stats('cumulative').print_stats(90)
        pytest.fail('DIAGNOSTIC COMPLETE: topology request measured; this is not a passing regression.')

    monkeypatch.setattr(proposal_service,'validate',observed)
