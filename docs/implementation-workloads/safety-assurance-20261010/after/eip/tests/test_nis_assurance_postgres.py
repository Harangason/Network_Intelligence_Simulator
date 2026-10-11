from uuid import uuid4
import pytest
from tests.test_agent_mailbox_handoff_postgres import handoff
from tests.test_factory_command_contract import pg_factory
from tests.test_nis_assurance import bundle, rehash
from core.assurance_methods import save_draft
from core.persistence.repository import CommandContext, RevisionConflict


@pytest.mark.parametrize("method,source_type", [("nis-evidence", "SafetyRequirement"), ("nis-security-evidence", "SecurityRequirement")])
def test_nis_import_original_core_revision_replay_project_mismatch_and_staleness(handoff, method, source_type):
    f, repo, _ = handoff
    def ctx(): return CommandContext("factory-alice", "nis-assurance", uuid4().hex)
    source = repo.upsert_engineering_object(f.keys[0], "SR-1", source_type, "Lenkung sicher abschalten", status="draft", context=ctx(), expected_revision=0, connection=f.connection)
    value = bundle(); value["payload"]["assessment"]["requirements"][0]["configuration"]["eip"] = {
        "project_id": f.keys[0], "requirement_ref": "SR-1", "source_revisions": {"SR-1": source["revision"]}}
    rehash(value)
    payload = {"id": "ASM-NIS", "title": "Original NIS evidence", "method": method, "reason": "SCRIPTED_TEST operator import", "sourceRevisions": {"SR-1": 1},
        "analysis": {"nisProjectId": "nis-1", "eipProjectId": f.keys[0], "bundle": value}}
    attempt = ctx()
    result = save_draft(f.keys[0], payload, attempt, expected_revision=0, repository=repo, auth_db_factory=f.auth_factory)
    assert result["releaseApproved"] is False
    stored = repo.object_by_key(f.keys[0], "ASM-NIS", connection=f.connection)
    assert stored["status"] == "draft"
    assert stored["technical_metadata"]["analysis"]["bundle"]["sha256"] == value["sha256"]
    assert save_draft(f.keys[0], payload, attempt, expected_revision=0, repository=repo, auth_db_factory=f.auth_factory)["idempotentReplay"] is True
    with pytest.raises(ValueError, match="project"):
        save_draft(f.keys[1], payload, ctx(), expected_revision=0, repository=repo, auth_db_factory=f.auth_factory)
    repo.upsert_engineering_object(f.keys[0], "SR-1", source_type, "Changed requirement", status="draft", context=ctx(), expected_revision=1, connection=f.connection)
    payload["id"] = "ASM-STALE"
    with pytest.raises(RevisionConflict):
        save_draft(f.keys[0], payload, ctx(), expected_revision=0, repository=repo, auth_db_factory=f.auth_factory)
    assert repo.object_by_key(f.keys[0], "ASM-STALE", connection=f.connection) is None
