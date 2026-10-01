from backend.engineering.agent_tools.run_status import execution_step


def test_routing_resume_does_not_reset_completed_model():
    summary = {'active_step': 'engineering_model', 'statuses': {'engineering_model': 'COMPLETE', 'routing': 'EMPTY'}}
    assert execution_step(summary) == 'routing'
    assert summary['active_step'] == 'engineering_model'


def test_incomplete_or_outdated_model_is_not_skipped():
    for status in ('EMPTY', 'IN_PROGRESS', 'OUTDATED', 'ERROR'):
        assert execution_step({'active_step': 'engineering_model', 'statuses': {'engineering_model': status}}) == 'engineering_model'


def test_continuation_skips_only_finished_steps():
    assert execution_step({'active_step': 'network_editor', 'statuses': {
        'network_editor': 'COMPLETE', 'parameters': 'APPROVED', 'capacity_timing': 'EMPTY'}}) == 'capacity_timing'
