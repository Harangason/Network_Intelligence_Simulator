from __future__ import annotations

import sqlite3

import pytest

from backend.knowledge import (
    HybridRetrievalService,
    KnowledgeIngestionPipeline,
    LocalTransformerService,
    PostgresSourceAdapter,
    SourceAdapterRegistry,
    SourceIngestionService,
    SourceRequest,
)
from backend.knowledge import sources


@pytest.mark.parametrize(
    ("source_type", "content"),
    [
        ("csv", "name,unit\nBatteryVoltage,V\n"),
        ("json", '{"signals":[{"name":"BatteryVoltage","unit":"V"}]}'),
        ("yaml", "signals:\n  - name: BatteryVoltage\n    unit: V\n"),
        ("xml", "<signals><signal><name>BatteryVoltage</name><unit>V</unit></signal></signals>"),
    ],
)
def test_structured_source_adapters_stage_canonical_entities(source_type, content):
    retrieval = HybridRetrievalService(transformer=LocalTransformerService(dimensions=64))
    service = SourceIngestionService(KnowledgeIngestionPipeline(retrieval))
    request = SourceRequest("battery-source", content=content, options={"object_type": "Signal"})

    result = service.ingest(source_type, request)

    assert result["raw_count"] == 1
    assert result["staged"][0].object_type == "Signal"
    assert result["staged"][0].knowledge_level == "L1_IMPORTED"
    assert retrieval.retrieve("BatteryVoltage")[0]["object_type"] == "Signal"


def test_sqlite_adapter_reads_all_user_tables_without_mutating_source(tmp_path):
    path = tmp_path / "engineering.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE signals (name TEXT, unit TEXT)")
    connection.execute("INSERT INTO signals VALUES ('StateOfCharge', '%')")
    connection.commit()
    connection.close()

    retrieval = HybridRetrievalService(transformer=LocalTransformerService(dimensions=64))
    service = SourceIngestionService(KnowledgeIngestionPipeline(retrieval))
    staged = service.stage("sqlite", SourceRequest("sqlite-source", content=path.read_bytes()))

    assert len(staged) == 1
    assert staged[0].object_type == "Signal"
    assert staged[0].payload["name"] == "StateOfCharge"


def test_registry_exposes_required_initial_sources_and_postgres_is_read_only():
    registry = SourceAdapterRegistry()
    assert set(registry.supported_types) == {"csv", "json", "postgresql", "rest", "sqlite", "xml", "yaml"}
    with pytest.raises(ValueError, match="read-only SELECT"):
        PostgresSourceAdapter().load(
            SourceRequest(
                "unsafe",
                location="postgresql://example.invalid/test",
                options={"query": "DELETE FROM engineering_signals"},
            )
        )


def test_rest_adapter_uses_get_and_content_type_parser(monkeypatch):
    class Headers:
        @staticmethod
        def get_content_type():
            return "application/json"

    class Response:
        headers = Headers()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        @staticmethod
        def read():
            return b'{"signals":[{"name":"RestSignal"}]}'

    observed = {}

    def fake_urlopen(request, timeout):
        observed.update(method=request.method, timeout=timeout)
        return Response()

    monkeypatch.setattr(sources, "urlopen", fake_urlopen)
    retrieval = HybridRetrievalService(transformer=LocalTransformerService(dimensions=64))
    service = SourceIngestionService(KnowledgeIngestionPipeline(retrieval))

    staged = service.stage("rest", SourceRequest("rest-source", location="https://engineering.example/api"))

    assert observed == {"method": "GET", "timeout": 10.0}
    assert staged[0].object_type == "Signal"
    assert staged[0].payload["name"] == "RestSignal"


def test_postgres_adapter_maps_read_only_rows(monkeypatch):
    class Cursor:
        def __init__(self):
            self.query = ""

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def execute(self, query):
            self.query = query

        @staticmethod
        def fetchmany(limit):
            assert limit == 10000
            return [{"name": "DatabaseSignal", "unit": "V"}]

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        @staticmethod
        def cursor(**_):
            return Cursor()

    monkeypatch.setattr(sources.psycopg, "connect", lambda *_args, **_kwargs: Connection())

    rows = PostgresSourceAdapter().load(
        SourceRequest("postgres-source", location="postgresql://local/test", options={"table": "signals"})
    )

    assert rows[0].entity_type == "Signal"
    assert rows[0].payload["name"] == "DatabaseSignal"
