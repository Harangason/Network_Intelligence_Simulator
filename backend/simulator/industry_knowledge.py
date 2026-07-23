"""Industry-specific learning memory and embedded knowledge graph storage."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_INDUSTRY_ROOT = Path("physic_lib") / "Industries"

INDUSTRY_ALIASES = {
    "aerospace": "Aerospace",
    "aerospace_defense": "Aerospace",
    "automotive": "Automotive",
    "building": "BuildingAutomation",
    "building_automation": "BuildingAutomation",
    "embedded": "EmbeddedSystems",
    "embedded_systems": "EmbeddedSystems",
    "energy": "Energy",
    "generic": "Generic",
    "general": "Generic",
    "generic_networking": "Generic",
    "industrial": "IndustrialAutomation",
    "industrial_automation": "IndustrialAutomation",
    "manufacturing": "IndustrialAutomation",
    "marine": "Marine",
    "rail": "Rail",
    "robotics": "RoboticsROS",
    "robotics_ros": "RoboticsROS",
    "ros": "RoboticsROS",
    "ros2": "RoboticsROS",
}


def _token(value: Any) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip().lower())
    return re.sub(r"_+", "_", text).strip("_")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


@contextmanager
def _database(path: Path):
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
        with connection:
            yield connection
    finally:
        connection.close()


@dataclass(frozen=True)
class IndustryContext:
    """Resolved industry identity and its isolated persistence paths."""

    name: str
    root: Path = DEFAULT_INDUSTRY_ROOT

    @classmethod
    def resolve(
        cls,
        value: Any,
        *,
        root: Path = DEFAULT_INDUSTRY_ROOT,
    ) -> "IndustryContext":
        token = _token(value) or "generic"
        name = INDUSTRY_ALIASES.get(token)
        if name is None:
            existing = {
                _token(path.name): path.name
                for path in Path(root).iterdir()
                if path.is_dir()
            } if Path(root).is_dir() else {}
            name = existing.get(token) or "".join(part.capitalize() for part in token.split("_")) or "Generic"
        return cls(name=name, root=Path(root))

    @classmethod
    def from_request(
        cls,
        request_data: dict[str, Any] | None,
        *,
        fallback: Any = "Generic",
        root: Path = DEFAULT_INDUSTRY_ROOT,
    ) -> "IndustryContext":
        request = request_data if isinstance(request_data, dict) else {}
        scenario = request.get("scenario") if isinstance(request.get("scenario"), dict) else {}
        filters = request.get("filter_system") if isinstance(request.get("filter_system"), dict) else {}
        value = (
            scenario.get("industry")
            or scenario.get("domain")
            or request.get("industry")
            or request.get("domain")
            or filters.get("industry")
            or filters.get("domain")
            or fallback
        )
        return cls.resolve(value, root=root)

    @property
    def key(self) -> str:
        return _token(self.name)

    @property
    def directory(self) -> Path:
        return self.root / self.name

    @property
    def memory_path(self) -> Path:
        return self.directory / "Learning" / "simulation_memory.db"

    @property
    def graph_path(self) -> Path:
        return self.directory / "Knowledge" / "knowledge_graph.db"


class IndustryMemoryStore:
    """SQLite run memory isolated to exactly one industry directory."""

    def __init__(self, context: IndustryContext) -> None:
        self.context = context
        self.path = context.memory_path

    def ensure(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path = self.context.directory / "learning" / "simulation_memory.db"
        if not self.path.exists() and legacy_path.exists():
            shutil.copy2(legacy_path, self.path)
        with _database(self.path) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS simulation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_utc TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    project_profile TEXT NOT NULL,
                    maneuver_profile TEXT NOT NULL,
                    package_mode TEXT NOT NULL,
                    signal_value_strategy TEXT NOT NULL,
                    generation_source_type TEXT,
                    request_path TEXT,
                    trace_dir TEXT,
                    formats TEXT,
                    duration_s REAL,
                    can_frames INTEGER,
                    ethernet_frames INTEGER,
                    warnings_count INTEGER,
                    plausibility_score INTEGER,
                    manifest_json TEXT,
                    interface_json TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_simulation_runs_lookup
                ON simulation_runs(project_profile, maneuver_profile, package_mode, signal_value_strategy)
                """
            )
        return self.path

    def recent(self, limit: int = 200) -> list[dict[str, Any]]:
        self.ensure()
        with _database(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, created_utc, prompt, project_profile, maneuver_profile, package_mode,
                       signal_value_strategy, generation_source_type, request_path, trace_dir,
                       formats, duration_s, can_frames, ethernet_frames, warnings_count,
                       plausibility_score
                FROM simulation_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def insert(self, values: dict[str, Any]) -> int:
        self.ensure()
        columns = (
            "created_utc",
            "prompt",
            "project_profile",
            "maneuver_profile",
            "package_mode",
            "signal_value_strategy",
            "generation_source_type",
            "request_path",
            "trace_dir",
            "formats",
            "duration_s",
            "can_frames",
            "ethernet_frames",
            "warnings_count",
            "plausibility_score",
            "manifest_json",
            "interface_json",
        )
        with _database(self.path) as connection:
            cursor = connection.execute(
                f"INSERT INTO simulation_runs ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                tuple(values.get(column) for column in columns),
            )
            return int(cursor.lastrowid)


class KnowledgeGraphStore:
    """Embedded property graph persisted in an industry-local SQLite database."""

    def __init__(self, context: IndustryContext) -> None:
        self.context = context
        self.path = context.graph_path

    def ensure(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _database(self.path) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    node_key TEXT NOT NULL,
                    properties_json TEXT NOT NULL,
                    created_utc TEXT NOT NULL,
                    updated_utc TEXT NOT NULL,
                    UNIQUE(kind, node_key)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
                    relation TEXT NOT NULL,
                    target_id TEXT NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
                    properties_json TEXT NOT NULL,
                    created_utc TEXT NOT NULL,
                    updated_utc TEXT NOT NULL,
                    UNIQUE(source_id, relation, target_id)
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_graph_nodes_kind ON graph_nodes(kind)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_relation ON graph_edges(relation)")
        return self.path

    @staticmethod
    def node_id(kind: str, key: Any) -> str:
        return f"{_token(kind)}:{_token(key) or 'unknown'}"

    def upsert_node(self, kind: str, key: Any, properties: dict[str, Any] | None = None) -> str:
        self.ensure()
        node_id = self.node_id(kind, key)
        now = _utc_now()
        with _database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO graph_nodes (id, kind, node_key, properties_json, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    properties_json=excluded.properties_json,
                    updated_utc=excluded.updated_utc
                """,
                (node_id, kind, str(key), _json(properties or {}), now, now),
            )
        return node_id

    def upsert_edge(
        self,
        source_id: str,
        relation: str,
        target_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        self.ensure()
        now = _utc_now()
        with _database(self.path) as connection:
            connection.execute(
                """
                INSERT INTO graph_edges
                    (source_id, relation, target_id, properties_json, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, relation, target_id) DO UPDATE SET
                    properties_json=excluded.properties_json,
                    updated_utc=excluded.updated_utc
                """,
                (source_id, relation.upper(), target_id, _json(properties or {}), now, now),
            )

    def neighbors(
        self,
        node_id: str,
        *,
        relation: str | None = None,
        direction: str = "out",
    ) -> list[dict[str, Any]]:
        self.ensure()
        source_column, neighbor_column = (
            ("source_id", "target_id") if direction == "out" else ("target_id", "source_id")
        )
        parameters: list[Any] = [node_id]
        relation_clause = ""
        if relation:
            relation_clause = " AND e.relation = ?"
            parameters.append(relation.upper())
        with _database(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT e.relation, e.properties_json AS edge_properties,
                       n.id, n.kind, n.node_key, n.properties_json
                FROM graph_edges e
                JOIN graph_nodes n ON n.id = e.{neighbor_column}
                WHERE e.{source_column} = ?{relation_clause}
                ORDER BY e.relation, n.kind, n.node_key
                """,
                parameters,
            ).fetchall()
        return [
            {
                **dict(row),
                "edge_properties": json.loads(row["edge_properties"]),
                "properties": json.loads(row["properties_json"]),
            }
            for row in rows
        ]

    def record_simulation(
        self,
        memory_id: int,
        request_data: dict[str, Any],
        *,
        manifest: dict[str, Any] | None = None,
        interface: dict[str, Any] | None = None,
    ) -> str:
        scenario = request_data.get("scenario") if isinstance(request_data.get("scenario"), dict) else {}
        run_id = self.upsert_node(
            "SimulationRun",
            memory_id,
            {
                "memory_id": memory_id,
                "description": scenario.get("description"),
                "output_dir": request_data.get("output_dir"),
                "duration_s": request_data.get("duration_s"),
                "created_utc": _utc_now(),
            },
        )
        industry_id = self.upsert_node("Industry", self.context.name, {"name": self.context.name})
        self.upsert_edge(industry_id, "HAS_RUN", run_id)

        for kind, relation, value in (
            ("ProjectProfile", "USES_PROFILE", scenario.get("project_profile")),
            ("ManeuverProfile", "USES_MANEUVER", scenario.get("maneuver_profile")),
            ("PackageMode", "USES_PACKAGE", request_data.get("package_mode") or scenario.get("package_mode")),
        ):
            if value:
                self.upsert_edge(run_id, relation, self.upsert_node(kind, value))

        self._record_topology(run_id, request_data)
        self._record_findings(run_id, manifest or {})
        if interface:
            interface_id = self.upsert_node("SimulationInterface", memory_id, interface)
            self.upsert_edge(run_id, "HAS_INTERFACE_SUMMARY", interface_id)
        return run_id

    def _record_topology(self, run_id: str, request_data: dict[str, Any]) -> None:
        hardware = request_data.get("hardware") if isinstance(request_data.get("hardware"), list) else []
        networks = request_data.get("networks") if isinstance(request_data.get("networks"), list) else []
        participants = request_data.get("participants") if isinstance(request_data.get("participants"), list) else []

        for network in networks:
            if not isinstance(network, dict):
                continue
            network_key = network.get("id") or network.get("name")
            if not network_key:
                continue
            network_id = self.upsert_node("Network", network_key, network)
            self.upsert_edge(run_id, "USES_NETWORK", network_id)
            technology = network.get("technology") or network.get("type") or network.get("protocol")
            if technology:
                technology_id = self.upsert_node("Technology", technology)
                self.upsert_edge(network_id, "USES_TECHNOLOGY", technology_id)

        for item in [*hardware, *participants]:
            if not isinstance(item, dict):
                continue
            hardware_key = item.get("id") or item.get("name")
            if not hardware_key:
                continue
            hardware_id = self.upsert_node("Hardware", hardware_key, item)
            self.upsert_edge(run_id, "INVOLVES", hardware_id)
            for service_name in item.get("provided_services") or []:
                service_id = self.upsert_node("Service", service_name)
                self.upsert_edge(hardware_id, "PROVIDES", service_id)
            for service_name in item.get("consumed_services") or []:
                service_id = self.upsert_node("Service", service_name)
                self.upsert_edge(hardware_id, "CONSUMES", service_id)
            for port in item.get("ports") or []:
                if not isinstance(port, dict):
                    continue
                port_key = port.get("id") or port.get("name")
                if not port_key:
                    continue
                port_id = self.upsert_node("Port", f"{hardware_key}:{port_key}", port)
                self.upsert_edge(hardware_id, "HAS_PORT", port_id)
                interfaces = port.get("network_interfaces") or port.get("interfaces") or []
                for interface_item in interfaces:
                    if not isinstance(interface_item, dict):
                        continue
                    interface_key = interface_item.get("id") or interface_item.get("name")
                    if not interface_key:
                        continue
                    interface_id = self.upsert_node("NetworkInterface", interface_key, interface_item)
                    self.upsert_edge(port_id, "EXPOSES_INTERFACE", interface_id)
                    network = interface_item.get("network") or interface_item.get("network_id")
                    if network:
                        self.upsert_edge(interface_id, "CONNECTED_TO", self.upsert_node("Network", network))
                    technology = interface_item.get("technology") or interface_item.get("protocol")
                    if technology:
                        self.upsert_edge(
                            interface_id,
                            "USES_TECHNOLOGY",
                            self.upsert_node("Technology", technology),
                        )

        communications = (
            request_data.get("communications")
            if isinstance(request_data.get("communications"), list)
            else []
        )
        for index, communication in enumerate(communications):
            if not isinstance(communication, dict):
                continue
            route_key = communication.get("id") or communication.get("name") or f"route_{index + 1}"
            route_id = self.upsert_node("CommunicationRoute", route_key, communication)
            self.upsert_edge(run_id, "USES_ROUTE", route_id)
            sender = communication.get("sender_interface") or communication.get("sender")
            if sender:
                self.upsert_edge(
                    self.upsert_node("NetworkInterface", sender),
                    "SENDS_VIA",
                    route_id,
                )
            receivers = communication.get("receivers") or communication.get("receiver_interfaces") or []
            if not isinstance(receivers, list):
                receivers = [receivers]
            for receiver in receivers:
                if receiver:
                    self.upsert_edge(
                        route_id,
                        "DELIVERS_TO",
                        self.upsert_node("NetworkInterface", receiver),
                    )

    def _record_findings(self, run_id: str, manifest: dict[str, Any]) -> None:
        validation = manifest.get("hardware_validation") if isinstance(manifest.get("hardware_validation"), dict) else {}
        findings: Iterable[Any] = validation.get("findings") or []
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                continue
            finding_id = self.upsert_node(
                "Finding",
                f"{run_id}:{index}:{finding.get('code') or 'finding'}",
                finding,
            )
            self.upsert_edge(run_id, "PRODUCED_FINDING", finding_id)


class IndustryKnowledgeService:
    """Coordinates industry-local run memory and knowledge graph updates."""

    def __init__(self, context: IndustryContext) -> None:
        self.context = context
        self.memory = IndustryMemoryStore(context)
        self.graph = KnowledgeGraphStore(context)

    def ensure(self) -> tuple[Path, Path]:
        return self.memory.ensure(), self.graph.ensure()
