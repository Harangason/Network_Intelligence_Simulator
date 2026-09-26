from copy import deepcopy
import pytest

from backend.tests.test_acceptance_scenarios import case_config, assert_timing_model_unavailable
from hardware_profile import normalize_hardware_config
from universal_trace import generate_universal_events
from backend.engineering.reasoning.engine import EngineeringReasoningEngine


def cascade_config(path, technology):
    config = case_config(path, [technology, technology, technology])
    config.update(duration_s=.1, deadline_ms=9, warning_threshold=90)
    records, behaviors = [], []
    for i, name in enumerate(("Input", "Control", "Output")):
        records.append({"id": f"s{i}", "name": name, "message_id": f"m{i}", "start_bit": 0, "length_bits": 16,
            "factor": 1, "min_value": 0, "max_value": 1000, "dependencies": [f"s{i-1}"] if i else []})
        parameters = {"value": 10}
        if i:
            parameters = {"formula": "upstream * 2", "transport_inputs": {"upstream": {"signal_id": f"s{i-1}", "max_age_ms": 15, "fallback": 0, "on_stale": "fallback"}}}
        behaviors.append({"signal_id": f"s{i}", "behavior_type": "FORMULA" if i else "CONSTANT", "dependencies": [f"s{i-1}"] if i else [], "parameters": parameters})
        config["communications"][i].update(signal_ids=[f"s{i}"], message_ids=[f"m{i}"], jitter_ratio=0, phase_ms=i*2)
    config["engineering_model"] = {"signals": records, "behaviors": behaviors, "messages": [{"id": f"m{i}", "cycle_ms": 10} for i in range(3)]}
    config["scenario"] = {"mode": "USER_DEFINED_FAULT", "faults": [{"type": "MESSAGE_LOSS", "scope": "MESSAGE", "target": {"id": "route-0"}, "start_s": .02, "end_s": .06}]}
    return config


def run(config):
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    context = {"configuration": config, "faults": config["scenario"]["faults"], "snapshot_available": True, "trusted_simulation": True, "routes": []}
    return events, EngineeringReasoningEngine().analyze(project_id="cascade-qa", job_id="cascade", events=events, context=context)


@pytest.mark.parametrize("technology", ["can_fd", "profinet", "dds_rtps", "ethernet"])
def test_loss_recovery_cascade_or_explicit_model_gap(tmp_path, technology):
    config = cascade_config(tmp_path, technology)
    if technology in {'profinet', 'dds_rtps'}:
        assert_timing_model_unavailable(config, [technology])
        return
    events, reasoning = run(config)
    outputs = [e for e in events if e["route_id"] == "route-2"]
    assert any(e["signals"][0]["value"] == 0 and e["signals"][0]["golden_value"] == 40 for e in outputs)
    assert outputs[-1]["signals"][0]["value"] == 40, "Recovered input must propagate to the output"
    assert reasoning.completion_status == "COMPLETE", reasoning.data_gaps
    assert any(f["code"] == "CASCADE_FAILURE" for f in reasoning.findings), reasoning.findings
    assert any(link.relation == "VALIDATED_TRANSPORT_DEPENDENCY" for link in reasoning.causal_chain)
    normal = deepcopy(config)
    normal["scenario"] = {"mode": "NORMAL", "faults": []}
    _, normal_reasoning = run(normal)
    assert not any(f["code"] == "CASCADE_FAILURE" for f in normal_reasoning.findings)


def test_forged_dependency_claims_or_missing_source_cannot_prove_causality(tmp_path):
    config = cascade_config(tmp_path, "can_fd")
    events, _ = run(config)
    for event in events:
        for sample in event["signals"]:
            if sample.get("dependency_evidence"):
                for item in sample["dependency_evidence"]["inputs"]:
                    item["source_event_id"] = "nonexistent"
                    item["last_attempt_event_id"] = "nonexistent"
    result = EngineeringReasoningEngine().analyze(project_id="qa", job_id="qa", events=events,
        context={"configuration": config, "faults": config["scenario"]["faults"], "snapshot_available": True, "trusted_simulation": True})
    assert not any(f["code"] == "CASCADE_FAILURE" for f in result.findings)


def test_malformed_dependency_evidence_cannot_crash_or_confirm(tmp_path):
    from backend.engineering.reasoning.dependencies import validate_dependency_effect
    config = cascade_config(tmp_path, 'can_fd')
    events, _ = run(config)
    target = next(e for e in events if e['route_id'] == 'route-1')
    sample = deepcopy(target['signals'][0])
    sample['dependency_evidence'] = {'inputs': ['not-an-input-object']}
    assert validate_dependency_effect(sample, target, {e['event_id']: e for e in events}, config) is None


@pytest.mark.parametrize('technology,kind,details', [
    ('can_fd', 'BURST_TRAFFIC', {'factor': 100}),
    ('profinet', 'GATEWAY_DELAY', {'delay_ms': 45}),
    ('dds_rtps', 'MESSAGE_DELAY', {'delay_ms': 45}),
    ('ethernet', 'GATEWAY_DELAY', {'delay_ms': 45}),
    ('ethernet', 'MESSAGE_DELAY', {'delay_ms': 45}),
])
def test_delayed_delivery_cascade_or_explicit_model_gap(tmp_path, technology, kind, details):
    config = cascade_config(tmp_path, technology)
    scope = 'NETWORK' if kind == 'GATEWAY_DELAY' else 'MESSAGE'
    target = 'node-1' if kind == 'GATEWAY_DELAY' else 'route-0'
    config['scenario']['faults'] = [{'type': kind, 'scope': scope, 'target': {'id': target}, 'start_s': .02, 'end_s': .05, **details}]
    if technology in {'profinet', 'dds_rtps'}:
        assert_timing_model_unavailable(config, [technology])
        return
    events, result = run(config)
    assert any(e['faults'] for e in events)
    assert any(effect.get('causality_proven') for effect in result.downstream_effects), result.data_gaps
    assert any(f['code'] == 'VALIDATED_DEPENDENCY_CHAIN' for f in result.findings)
