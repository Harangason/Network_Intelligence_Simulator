from backend.app import create_app
from backend.engineering.semantic_intelligence import ConceptOntology, SemanticClassificationService


def test_ontology_resolves_aliases_and_common_ancestor():
    ontology = ConceptOntology()

    assert ontology.resolve_alias("rpm").id == "ROTATIONAL_SPEED"
    assert ontology.resolve_parent("ROTATIONAL_SPEED").id == "PHYSICAL_QUANTITY"
    assert ontology.find_common_ancestor("TEMPERATURE", "PRESSURE").id == "PHYSICAL_QUANTITY"
    assert ontology.validate_concept_relation("WARNING", "ERROR") is True


def test_temperature_unit_classifies_as_physical_quantity_proposal():
    result = SemanticClassificationService().classify(
        {
            "object_type": "Signal",
            "name": "ProcessTemperature",
            "unit": "degC",
            "data_type": "signed",
            "min_value": -40,
            "max_value": 140,
            "length_bits": 16,
        }
    )

    assert result["selected_concept_id"] == "TEMPERATURE"
    assert result["semantic_type"] == "NUMERIC"
    assert result["decision_state"] in {"CONFIRMED", "HIGH_CONFIDENCE"}
    assert result["requires_review"] is False


def test_rotational_speed_uses_unit_and_alias_without_industry_specific_terms():
    result = SemanticClassificationService().classify(
        {
            "object_type": "Signal",
            "name": "RotationalSpeed",
            "unit": "1/min",
            "data_type": "unsigned",
            "min_value": 0,
            "max_value": 12000,
        }
    )

    assert result["selected_concept_id"] == "ROTATIONAL_SPEED"
    assert result["semantic_type"] == "NUMERIC"
    assert result["confidence"] >= 0.72


def test_status_signal_becomes_state_proposal_instead_of_open_numeric_optimization():
    result = SemanticClassificationService().classify(
        {
            "object_type": "Signal",
            "name": "ProcessStatus",
            "unit": "not_applicable",
            "data_type": "unsigned",
            "data": {"enum_values": {"OK": 0, "WARNING": 1, "ERROR": 2, "NOT_AVAILABLE": 3}},
        }
    )

    assert result["selected_concept_id"] in {"OPERATING_STATE", "STATUS"}
    assert result["semantic_type"] == "STATE"
    assert result["decision_state"] in {"CONFIRMED", "HIGH_CONFIDENCE"}
    assert result["model_states"]["llm"] == "PROPOSAL_ONLY_NOT_CALLED"


def test_unknown_signal_requires_review_and_does_not_invent_truth():
    result = SemanticClassificationService().classify({"object_type": "Signal", "name": "XQ17"})

    assert result["selected_concept_id"] is None
    assert result["semantic_type"] == "UNKNOWN"
    assert result["decision_state"] == "UNKNOWN"
    assert result["requires_review"] is True


def test_semantic_classification_api_returns_proposal():
    client = create_app(testing=True).test_client()
    response = client.post(
        "/api/engineering/semantics/classify",
        json={"object_type": "Signal", "name": "LinePressure", "unit": "bar", "data_type": "unsigned"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["selected_concept_id"] == "PRESSURE"
    assert "human_review_gate" in payload["pipeline"]
