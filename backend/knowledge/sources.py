"""Provider-neutral source adapters and staging for engineering knowledge."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
import csv
import io
import json
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Any, Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import psycopg
import yaml

from .ingestion import EngineeringChunk, EngineeringChunker, KnowledgeIngestionPipeline


CANONICAL_TYPE_ALIASES = {
    "hardware": "HardwareNode",
    "hardware_node": "HardwareNode",
    "hardware_nodes": "HardwareNode",
    "node": "HardwareNode",
    "nodes": "HardwareNode",
    "ecu": "HardwareNode",
    "function": "Function",
    "functions": "Function",
    "interface": "Interface",
    "interfaces": "Interface",
    "message": "Message",
    "messages": "Message",
    "signal": "Signal",
    "signals": "Signal",
    "requirement": "Requirement",
    "requirements": "Requirement",
    "document": "Document",
    "documents": "Document",
}


@dataclass(frozen=True)
class SourceRequest:
    source_id: str
    content: bytes | str | None = None
    location: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawEntity:
    source_id: str
    source_type: str
    ordinal: int
    entity_type: str
    payload: dict[str, Any]
    provenance: dict[str, Any]


@dataclass(frozen=True)
class StagedEntity:
    staging_id: str
    source_id: str
    object_type: str
    payload: dict[str, Any]
    knowledge_level: str
    provenance: dict[str, Any]


class SourceAdapter(ABC):
    """Load source-specific data into neutral raw entities."""

    source_type: str

    @abstractmethod
    def load(self, request: SourceRequest) -> list[RawEntity]:
        raise NotImplementedError


def _text(request: SourceRequest) -> str:
    if request.content is not None:
        return request.content.decode(request.options.get("encoding", "utf-8-sig")) if isinstance(request.content, bytes) else request.content
    if request.location:
        return Path(request.location).read_text(encoding=request.options.get("encoding", "utf-8-sig"))
    raise ValueError("content or location is required.")


def _canonical_type(value: Any, fallback: str = "Document") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return CANONICAL_TYPE_ALIASES.get(normalized, str(value).strip() if value else fallback)


def _records_from_value(value: Any, *, fallback_type: str = "Document") -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                records.append((_canonical_type(item.get("object_type") or item.get("entity_type"), fallback_type), dict(item)))
            else:
                records.append((fallback_type, {"value": item}))
        return records
    if isinstance(value, dict):
        expanded = False
        for key, items in value.items():
            if isinstance(items, list):
                expanded = True
                object_type = _canonical_type(key, fallback_type)
                for item in items:
                    records.append((object_type, dict(item) if isinstance(item, dict) else {"value": item}))
        if expanded:
            scalar_values = {key: item for key, item in value.items() if not isinstance(item, list)}
            if scalar_values:
                records.append((fallback_type, scalar_values))
            return records
        return [(_canonical_type(value.get("object_type") or value.get("entity_type"), fallback_type), dict(value))]
    return [(fallback_type, {"value": value})]


def _raw_entities(source_type: str, request: SourceRequest, records: Iterable[tuple[str, dict[str, Any]]]) -> list[RawEntity]:
    result = []
    for ordinal, (entity_type, payload) in enumerate(records):
        provenance = {
            "source_id": request.source_id,
            "source_type": source_type,
            "location": request.location,
            "ordinal": ordinal,
        }
        result.append(RawEntity(request.source_id, source_type, ordinal, entity_type, payload, provenance))
    return result


class CsvSourceAdapter(SourceAdapter):
    source_type = "csv"

    def load(self, request: SourceRequest) -> list[RawEntity]:
        reader = csv.DictReader(io.StringIO(_text(request)), delimiter=str(request.options.get("delimiter") or ","))
        object_type = _canonical_type(request.options.get("object_type"), "Document")
        return _raw_entities(self.source_type, request, ((object_type, dict(row)) for row in reader))


class JsonSourceAdapter(SourceAdapter):
    source_type = "json"

    def load(self, request: SourceRequest) -> list[RawEntity]:
        value = json.loads(_text(request))
        return _raw_entities(self.source_type, request, _records_from_value(value, fallback_type=_canonical_type(request.options.get("object_type"), "Document")))


class YamlSourceAdapter(SourceAdapter):
    source_type = "yaml"

    def load(self, request: SourceRequest) -> list[RawEntity]:
        value = yaml.safe_load(_text(request))
        return _raw_entities(self.source_type, request, _records_from_value(value, fallback_type=_canonical_type(request.options.get("object_type"), "Document")))


class XmlSourceAdapter(SourceAdapter):
    source_type = "xml"

    @staticmethod
    def _payload(element: ET.Element) -> dict[str, Any]:
        payload: dict[str, Any] = {f"@{key}": value for key, value in element.attrib.items()}
        for child in element:
            value: Any = XmlSourceAdapter._payload(child) if list(child) or child.attrib else (child.text or "").strip()
            if child.tag in payload:
                payload[child.tag] = payload[child.tag] if isinstance(payload[child.tag], list) else [payload[child.tag]]
                payload[child.tag].append(value)
            else:
                payload[child.tag] = value
        if not list(element) and (element.text or "").strip():
            payload.setdefault("value", (element.text or "").strip())
        return payload

    def load(self, request: SourceRequest) -> list[RawEntity]:
        root = ET.fromstring(_text(request))
        elements = list(root) or [root]
        records = ((_canonical_type(element.tag, "Document"), self._payload(element)) for element in elements)
        return _raw_entities(self.source_type, request, records)


class SqliteSourceAdapter(SourceAdapter):
    source_type = "sqlite"

    def load(self, request: SourceRequest) -> list[RawEntity]:
        temporary_path: str | None = None
        path = request.location
        if request.content is not None:
            raw = request.content if isinstance(request.content, bytes) else request.content.encode("utf-8")
            handle = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
            handle.write(raw)
            handle.close()
            temporary_path = handle.name
            path = temporary_path
        if not path:
            raise ValueError("SQLite source requires content or location.")
        try:
            connection = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                tables = [
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                    )
                ]
                requested_tables = request.options.get("tables")
                if requested_tables:
                    allowed = set(map(str, requested_tables))
                    tables = [table for table in tables if table in allowed]
                records: list[tuple[str, dict[str, Any]]] = []
                for table in tables:
                    quoted = table.replace('"', '""')
                    object_type = _canonical_type(table, "Document")
                    for row in connection.execute(f'SELECT * FROM "{quoted}"'):
                        records.append((object_type, {**dict(row), "_table": table}))
                return _raw_entities(self.source_type, request, records)
            finally:
                connection.close()
        finally:
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)


class PostgresSourceAdapter(SourceAdapter):
    source_type = "postgresql"

    def load(self, request: SourceRequest) -> list[RawEntity]:
        dsn = request.location or str(request.options.get("dsn") or "")
        query = str(request.options.get("query") or "").strip()
        table = str(request.options.get("table") or "").strip()
        if not dsn:
            raise ValueError("PostgreSQL source requires a DSN.")
        if query and not re.match(r"^select\b", query, re.IGNORECASE):
            raise ValueError("Only read-only SELECT queries are allowed.")
        if not query:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", table):
                raise ValueError("A safe table name or SELECT query is required.")
            query = f"SELECT * FROM {table}"
        with psycopg.connect(dsn, autocommit=True) as connection:
            with connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(query)
                rows = cursor.fetchmany(int(request.options.get("max_rows") or 10000))
        object_type = _canonical_type(request.options.get("object_type") or table, "Document")
        return _raw_entities(self.source_type, request, ((object_type, dict(row)) for row in rows))


class RestSourceAdapter(SourceAdapter):
    source_type = "rest"

    def load(self, request: SourceRequest) -> list[RawEntity]:
        url = request.location or ""
        if urlparse(url).scheme not in {"http", "https"}:
            raise ValueError("REST source requires an HTTP(S) URL.")
        headers = {"Accept": "application/json, application/yaml, application/xml, text/plain", **dict(request.options.get("headers") or {})}
        with urlopen(Request(url, headers=headers, method="GET"), timeout=float(request.options.get("timeout") or 10.0)) as response:
            content = response.read()
            content_type = response.headers.get_content_type()
        nested = SourceRequest(request.source_id, content=content, location=url, options=request.options)
        source_format = str(request.options.get("format") or "").lower()
        if source_format in {"yaml", "yml"} or "yaml" in content_type:
            records = YamlSourceAdapter().load(nested)
        elif source_format == "xml" or "xml" in content_type:
            records = XmlSourceAdapter().load(nested)
        elif source_format == "csv" or "csv" in content_type:
            records = CsvSourceAdapter().load(nested)
        else:
            records = JsonSourceAdapter().load(nested)
        return [RawEntity(item.source_id, self.source_type, item.ordinal, item.entity_type, item.payload, {**item.provenance, "source_type": self.source_type}) for item in records]


class SourceAdapterRegistry:
    def __init__(self, adapters: Iterable[SourceAdapter] | None = None) -> None:
        self._adapters: dict[str, SourceAdapter] = {}
        for adapter in adapters or (
            CsvSourceAdapter(), JsonSourceAdapter(), YamlSourceAdapter(), XmlSourceAdapter(),
            SqliteSourceAdapter(), PostgresSourceAdapter(), RestSourceAdapter(),
        ):
            self.register(adapter)

    def register(self, adapter: SourceAdapter) -> None:
        self._adapters[adapter.source_type] = adapter

    def get(self, source_type: str) -> SourceAdapter:
        normalized = source_type.strip().lower()
        if normalized == "yml":
            normalized = "yaml"
        try:
            return self._adapters[normalized]
        except KeyError as error:
            raise ValueError(f"Unknown source adapter: {source_type}") from error

    @property
    def supported_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


class SourceIngestionService:
    """Runs Source -> RawEntity -> normalization -> staging -> indexing."""

    def __init__(self, pipeline: KnowledgeIngestionPipeline, registry: SourceAdapterRegistry | None = None) -> None:
        self.pipeline = pipeline
        self.registry = registry or SourceAdapterRegistry()
        self.chunker = EngineeringChunker()

    def stage(self, source_type: str, request: SourceRequest) -> list[StagedEntity]:
        raw_entities = self.registry.get(source_type).load(request)
        staged = []
        for item in raw_entities:
            object_type = _canonical_type(item.entity_type, "Document")
            payload = {key: value for key, value in item.payload.items() if key not in {"object_type", "entity_type"}}
            staged.append(
                StagedEntity(
                    staging_id=f"{item.source_id}:{item.ordinal}",
                    source_id=item.source_id,
                    object_type=object_type,
                    payload=payload,
                    knowledge_level="L1_IMPORTED",
                    provenance=item.provenance,
                )
            )
        return staged

    def ingest(self, source_type: str, request: SourceRequest) -> dict[str, Any]:
        staged = self.stage(source_type, request)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in staged:
            grouped[item.object_type].append(
                {
                    "id": item.staging_id,
                    **item.payload,
                    "metadata": {
                        "knowledge_level": item.knowledge_level,
                        "source_quality": 0.55,
                        "evidence": [item.provenance],
                    },
                }
            )
        chunks: list[EngineeringChunk] = []
        for object_type, entities in grouped.items():
            chunks.extend(self.chunker.entity_chunks(entities, source_id=request.source_id, object_type=object_type))
        indexed = self.pipeline.ingest(chunks)
        return {
            "source_id": request.source_id,
            "source_type": source_type,
            "raw_count": len(staged),
            "staged": staged,
            "indexed": indexed,
        }
