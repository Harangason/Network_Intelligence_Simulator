from backend.engineering.simulation_coverage import simulation_coverage, assess_simulation


def model():
    return {
        "messages": [{"id": "m1"}, {"id": "m2"}],
        "signals": [{"id": "s1", "message_id": "m1"}, {"id": "s2", "message_id": "m2"}],
    }


def test_partial_transport_cannot_shrink_default_scope():
    result = simulation_coverage(**model(), transports=[{"payload": {"message_id": "m1"}}])
    assert result["complete"] is False
    assert result["missing_message_ids"] == ["m2"]
    assert result["missing_signal_ids"] == ["s2"]
    assert result["signal_coverage_percent"] == 50


def test_explicit_selection_records_exclusions_and_rejects_unknown_ids():
    transports = [{"payload": {"message_id": "m1"}}]
    selected = simulation_coverage(**model(), transports=transports, scope={"mode": "SIGNAL", "signal_ids": ["s1"]})
    assert selected["complete"] is True
    assert selected["excluded_signals"] == selected["excluded_messages"] == 1
    invalid = simulation_coverage(**model(), transports=transports, scope={"mode": "SIGNAL", "signal_ids": ["typo"]})
    assert invalid["complete"] is False and invalid["errors"]


def test_partial_signal_payload_does_not_pretend_to_transport_entire_frame():
    result = simulation_coverage([{"id": "m"}], [{"id": "a", "message_id": "m"}, {"id": "b", "message_id": "m"}],
                                 [{"message_ids": ["m"], "signal_ids": ["a"]}])
    assert result["missing_signal_ids"] == ["b"]


def test_inactive_route_is_not_coverage_and_inactive_signal_is_not_required():
    result = simulation_coverage([{"id": "m"}], [{"id": "a", "message_id": "m"}, {"id": "old", "message_id": "m", "lifecycle_state": "deprecated"}],
                                 [{"status": "OUTDATED", "payload": {"message_id": "m"}}])
    assert result["required_signal_ids"] == ["a"]
    assert result["covered_signals"] == 0


def configuration():
    return {"engineering_model": model(), "networks": [{"id": "bus"}], "communications": [
        {"id": "c1", "routing_entry_id": "r1", "message_ids": ["m1"]},
        {"id": "c2", "routing_entry_id": "r2", "message_ids": ["m2"]},
    ]}


def result():
    return {"runtime_metrics": {"available": True, "networks": [{"network_id": "bus"}], "routes": [
        {"route_id": "c1", "status": "PASS"}, {"route_id": "c2", "status": "PASS"},
    ]}, "model_simulation": {"signals": [{"signal_id": "s1"}, {"signal_id": "s2"}]}}


def test_completed_job_requires_actual_signal_and_network_evidence():
    complete = assess_simulation(configuration(), result())
    assert complete["conformance"] == "PASS" and complete["status"] == "COMPLETE"
    partial = result()
    partial["model_simulation"]["signals"].pop()
    incomplete = assess_simulation(configuration(), partial)
    assert incomplete["status"] == "WARNING"
    assert incomplete["missing_observed_signal_ids"] == ["s2"]
    partial["runtime_metrics"]["networks"] = []
    assert assess_simulation(configuration(), partial)["missing_observed_network_ids"] == ["bus"]


def test_runtime_failure_and_unchecked_requirements_are_not_complete():
    failed = result()
    failed["runtime_metrics"]["routes"][0]["status"] = "FAIL"
    assert assess_simulation(configuration(), failed)["status"] == "ERROR"
    failed["runtime_metrics"]["routes"][0]["status"] = "NOT_EVALUATED"
    assert assess_simulation(configuration(), failed)["conformance"] == "NOT_EVALUATED"


def test_warning_text_alone_does_not_prove_successful_simulation():
    assessment = assess_simulation(configuration(), {"warnings": ["No events"]})
    assert assessment["status"] == "WARNING" and assessment["conformance"] == "NOT_EVALUATED"


def test_selected_scope_requires_only_its_participating_networks():
    from backend.engineering.simulation import _apply_simulation_scope

    config = configuration()
    config["networks"] = [{"id": "selected-bus"}, {"id": "excluded-bus"}]
    for communication, network in zip(config["communications"], config["networks"]):
        communication["network_id"] = network["id"]
    config["simulation_scope"] = {"mode": "MESSAGE", "message_ids": ["m1"], "reason": "First subsystem only"}
    _apply_simulation_scope(config)
    selected_result = {"runtime_metrics": {"available": True, "networks": [{"network_id": "selected-bus"}],
        "routes": [{"route_id": "c1", "status": "PASS"}]},
        "model_simulation": {"signals": [{"signal_id": "s1"}]}}
    assessment = assess_simulation(config, selected_result)
    assert assessment["scope_coverage"]["excluded_messages"] == 1
    assert assessment["missing_observed_network_ids"] == []
    assert assessment["conformance"] == "PASS" and assessment["status"] == "COMPLETE"

    # ALL still requires evidence for the full configured network inventory.
    all_config = configuration()
    all_config["networks"].append({"id": "unobserved-bus"})
    all_assessment = assess_simulation(all_config, result())
    assert all_assessment["missing_observed_network_ids"] == ["unobserved-bus"]
    assert all_assessment["conformance"] == "NOT_EVALUATED"


def test_selected_scope_requires_gateway_intermediate_network_evidence():
    config = {"simulation_scope": {"mode": "MESSAGE", "message_ids": ["m1"], "reason": "Gateway subsystem"},
        "engineering_model": model(),
        "networks": [{"id": "source"}, {"id": "backbone"}, {"id": "target"}, {"id": "excluded"}],
        "communications": [{"id": "c1", "routing_entry_id": "r1", "message_ids": ["m1"],
            "network_id": "source", "segments": [{"network_id": "source"}, {"network_id": "backbone"}, {"network_id": "target"}]}]}
    observed = {"runtime_metrics": {"available": True,
        "networks": [{"network_id": "source"}, {"network_id": "target"}],
        "routes": [{"route_id": "c1", "status": "PASS"}]},
        "model_simulation": {"signals": [{"signal_id": "s1"}]}}
    missing = assess_simulation(config, observed)
    assert missing["missing_observed_network_ids"] == ["backbone"]
    assert missing["status"] == "WARNING" and missing["conformance"] == "NOT_EVALUATED"
    observed["runtime_metrics"]["networks"].append({"network_id": "backbone"})
    complete = assess_simulation(config, observed)
    assert complete["missing_observed_network_ids"] == []
    assert complete["status"] == "COMPLETE" and complete["conformance"] == "PASS"
