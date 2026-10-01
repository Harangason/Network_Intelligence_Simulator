from contextlib import contextmanager

from backend.engineering import system_merge


CANONICAL_ID = "00000000-0000-0000-0000-000000000001"
DUPLICATE_ID = "00000000-0000-0000-0000-000000000002"
RELATION_ID = "00000000-0000-0000-0000-000000000003"
PROPOSAL_ID = "00000000-0000-0000-0000-000000000004"


class FakeResult:
    def __init__(self, *, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.hardware = {
            CANONICAL_ID: {
                "id": CANONICAL_ID,
                "project_id": "merge-test",
                "name": "ADAS",
                "version": 2,
                "confidence": 0.7,
                "provenance": {},
                "lifecycle_state": "active",
            },
            DUPLICATE_ID: {
                "id": DUPLICATE_ID,
                "project_id": "merge-test",
                "name": "Fahrerassistenz-ECU",
                "version": 1,
                "confidence": 0.5,
                "provenance": {},
                "lifecycle_state": "active",
            },
        }

    def execute(self, query, params=None):
        statement = str(query)
        self.executed.append((statement, params))
        if statement.startswith("SELECT * FROM engineering_hardware_nodes"):
            return FakeResult(many=list(self.hardware.values()))
        if statement.startswith("UPDATE engineering_hardware_nodes SET provenance"):
            row = self.hardware[CANONICAL_ID]
            row.update(provenance=params[0].obj, confidence=max(row["confidence"], params[1]), version=row["version"] + 1)
            return FakeResult(one=dict(row))
        if statement.startswith("UPDATE engineering_hardware_nodes SET lifecycle_state"):
            row = self.hardware[DUPLICATE_ID]
            row.update(lifecycle_state="superseded", provenance=params[0].obj, version=row["version"] + 1)
            return FakeResult(one=dict(row))
        if statement.startswith("INSERT INTO engineering_relations"):
            return FakeResult(one={"id": RELATION_ID})
        if statement.startswith("INSERT INTO engineering_ai_proposals"):
            return FakeResult(one={"proposal_id": PROPOSAL_ID})
        return FakeResult()


def test_merge_system_duplicate_creates_reversible_alias_without_deleting(monkeypatch):
    connection = FakeConnection()

    @contextmanager
    def fake_connection():
        yield connection

    candidate = {
        "candidate_key": f"{CANONICAL_ID}:{DUPLICATE_ID}",
        "canonical_hardware": {"id": CANONICAL_ID, "name": "ADAS", "child_count": 12},
        "duplicate_hardware": {"id": DUPLICATE_ID, "name": "Fahrerassistenz-ECU", "child_count": 0},
        "confidence": 0.82,
        "reason": "Kontrollierte Fachsynonyme.",
    }
    monkeypatch.setattr(system_merge, "analyze_system_duplicates", lambda: {"items": [candidate]})
    monkeypatch.setattr(system_merge, "get_connection", fake_connection)
    monkeypatch.setattr(system_merge, "current_project_id", lambda: "merge-test")

    result = system_merge.merge_system_duplicate(
        {
            "candidate_key": candidate["candidate_key"],
            "canonical_hardware_id": CANONICAL_ID,
            "duplicate_hardware_id": DUPLICATE_ID,
            "actor": "tester",
        }
    )

    assert result["reversible"] is True
    assert result["relation_id"] == RELATION_ID
    assert connection.hardware[DUPLICATE_ID]["lifecycle_state"] == "superseded"
    assert connection.hardware[DUPLICATE_ID]["provenance"]["canonical_system_merge"]["canonical_id"] == CANONICAL_ID
    assert any(statement.startswith("INSERT INTO engineering_relations") for statement, _ in connection.executed)
    assert not any(statement.startswith("DELETE") for statement, _ in connection.executed)
