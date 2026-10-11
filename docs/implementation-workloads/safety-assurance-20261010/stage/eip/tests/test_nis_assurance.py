"""Original NIS calculator export, conservative Core import, no approval inference."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import pytest
from core.assurance_methods import evaluate
from core.nis_assurance import evidence_hash


def bundle():
    return json.loads((Path(__file__).parent / "fixtures/nis_safety_evidence.json").read_text(encoding="utf-8"))


def rehash(value):
    value["sha256"] = evidence_hash(value["payload"])
    return value


def analysis(value=None):
    return {"nisProjectId": "nis-1", "eipProjectId": "eip-1", "bundle": value or bundle()}


def test_original_nis_export_import_keeps_measurement_separate_from_review():
    result = evaluate("nis-evidence", analysis(), {"SR-1": 2})
    assert result["result"]["requirements"][0]["providerTechnicalStatus"] == "PASS"
    assert result["result"]["sourceAuthenticity"] == "UNVERIFIED_OPERATOR_IMPORT"
    assert result["result"]["liveNisFreshness"] == "UNVERIFIED"
    assert result["releaseApproved"] is False and result["reviewRequired"] is True
    assert result["riskAcceptance"] == "not_assessed"


@pytest.mark.parametrize("mutation", ["hash", "nis_project", "eip_project", "stale_revision", "approval", "normative", "execution", "missing_job", "extra_source", "requirement_vector", "schema"])
def test_invalid_scope_or_forged_proof_is_rejected(mutation):
    value = bundle(); data = analysis(value); sources = {"SR-1": 2}
    if mutation == "hash": value["sha256"] = "0" * 64
    if mutation == "nis_project": data["nisProjectId"] = "wrong"
    if mutation == "eip_project": data["eipProjectId"] = "wrong"
    if mutation == "stale_revision": sources["SR-1"] = 3
    if mutation == "approval": value["payload"]["release_approved"] = True; rehash(value)
    if mutation == "normative": value["payload"]["assessment"]["normative_status"] = "PASS"; rehash(value)
    if mutation == "execution": value["payload"]["execution_status"] = "RUNNING"; rehash(value)
    if mutation == "missing_job": value["payload"]["job_id"] = None; rehash(value)
    if mutation == "extra_source": sources["SR-2"] = 1
    if mutation == "requirement_vector": value["payload"]["requirement_revisions"]["safety-1"] = 2; rehash(value)
    if mutation == "schema": value["payload"]["rule_version"] = "unknown"; rehash(value)
    with pytest.raises(ValueError): evaluate("nis-evidence", data, sources)


def test_historical_evidence_remains_historical_after_import():
    value = bundle(); value["payload"]["freshness"] = "OUTDATED"; rehash(value)
    result = evaluate("nis-evidence", analysis(value), {"SR-1": 2})
    assert "provider_evidence_outdated" in result["gaps"]
    assert result["releaseApproved"] is False


def test_browser_reserialized_integral_numbers_retain_hash_and_security_import_remains_draft():
    value = bundle()
    value["payload"]["assessment"]["requirements"][0]["checks"][0]["observed_max_latency_ms"] = 2
    assert evaluate("nis-security-evidence", analysis(value), {"SR-1": 2})["releaseApproved"] is False
    value["payload"]["assessment"]["requirements"][0]["configuration"] = []
    rehash(value)
    with pytest.raises(ValueError): evaluate("nis-evidence", analysis(value), {"SR-1": 2})
