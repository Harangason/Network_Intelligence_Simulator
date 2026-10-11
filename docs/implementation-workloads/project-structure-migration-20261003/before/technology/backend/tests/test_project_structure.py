"""Regression checks for the navigable NIS source structure."""

from backend.communication.technologies.catalog import MODEL_TYPES, technology_definitions
from backend.engineering.workflow.models import WORKFLOW_LABELS as LEGACY_LABELS
from backend.engineering.workflow.models import WORKFLOW_STEPS as LEGACY_STEPS
from backend.nis import architecture_catalog
from backend.specializations.industries import ALL as INDUSTRIES
from backend.specializations.technologies import ALL as TECHNOLOGIES
from backend.workflow.definition import WORKFLOW_LABELS, WORKFLOW_STAGES, WORKFLOW_STEPS


def test_workflow_structure_is_the_legacy_runtime_source() -> None:
    assert len(WORKFLOW_STAGES) == 9
    assert WORKFLOW_STEPS == LEGACY_STEPS
    assert WORKFLOW_LABELS == LEGACY_LABELS
    assert [stage.position for stage in WORKFLOW_STAGES] == list(range(1, 10))
    assert all(stage.backend_sources and stage.frontend_feature for stage in WORKFLOW_STAGES)


def test_every_model_type_has_an_industry_source() -> None:
    assert {item["id"] for item in MODEL_TYPES} == {item.id for item in INDUSTRIES}


def test_every_builtin_technology_has_a_specialized_source_group() -> None:
    expected = {item["id"] for item in technology_definitions()}
    grouped = {technology_id for item in TECHNOLOGIES for technology_id in item.technology_ids}
    assert expected <= grouped
    assert all(item.source_modules for item in TECHNOLOGIES)


def test_architecture_catalog_exposes_all_primary_origins() -> None:
    catalog = architecture_catalog()
    assert len(catalog["workflow"]) == 9
    assert len(catalog["industries"]) == len(MODEL_TYPES)
    assert {item["id"] for item in catalog["capabilities"]} == {
        "domain", "automation", "simulation", "intelligence", "interfaces", "infrastructure",
    }
