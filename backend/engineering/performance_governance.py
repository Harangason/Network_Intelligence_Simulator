"""Performance governance for memory, cache and rendering boundaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


LARGE_OBJECT_THRESHOLD_BYTES = 1_000_000


@dataclass(frozen=True)
class MemoryBudget:
    name: str
    owner: str
    soft_limit_bytes: int
    hard_limit_bytes: int
    enforcement: str
    remediation: str


@dataclass(frozen=True)
class CachePolicy:
    namespace: str
    owner: str
    max_entries: int
    ttl_seconds: int
    max_value_bytes: int
    eviction_policy: str
    key_template: str


@dataclass(frozen=True)
class InventoryEntry:
    layer: str
    allowed: str
    forbidden: str
    projection_rule: str
    persistence_rule: str


MEMORY_BUDGETS: tuple[MemoryBudget, ...] = (
    MemoryBudget(
        "workflow_state_response",
        "backend.engineering.workflow",
        512_000,
        2_000_000,
        "summaries_only",
        "Return ids, status and counters; load heavy snapshots through detail endpoints.",
    ),
    MemoryBudget(
        "simulation_snapshot_list",
        "backend.engineering.workflow",
        256_000,
        1_000_000,
        "metadata_only",
        "Lists must omit result, calculated_metrics and configuration payloads.",
    ),
    MemoryBudget(
        "frontend_working_set",
        "frontend.studio",
        64_000_000,
        128_000_000,
        "bounded_state",
        "Keep only visible rows, selected details and compact summaries in React state.",
    ),
    MemoryBudget(
        "graph_viewport",
        "frontend.network_editor",
        250,
        500,
        "viewport_window",
        "Render only viewport nodes and route previews; keep full graph in backend/project store.",
    ),
    MemoryBudget(
        "trace_event_window",
        "frontend.simulation",
        5_000,
        20_000,
        "ring_buffer",
        "Stream or window trace events instead of appending full runs to component state.",
    ),
    MemoryBudget(
        "backend_hot_cache",
        "backend.runtime",
        64_000_000,
        128_000_000,
        "ttl_lru",
        "Persist historical artifacts and prune hot process memory by ttl and entry count.",
    ),
)


CACHE_POLICIES: tuple[CachePolicy, ...] = (
    CachePolicy("agent-chat", "frontend.api.agent.history", 100, 86_400, 1_502_048, "ttl_lru_file", "project_id"),
    CachePolicy("agent-feedback", "frontend.lib.agent.feedback_store", 1, 604_800, 8_000_000, "ttl_singleton_file", "history"),
    CachePolicy("simulation-jobs", "frontend.api.program_cache", 30, 7_200, 1_000_000, "ttl_lru_file", "job_id"),
    CachePolicy("local-simulator-runtime", "frontend.lib.local_simulator", 30, 3_600, 1_000_000, "ttl_lru_memory", "job_id"),
    CachePolicy("dev-opt-runtime", "frontend.api.dev_opt", 30, 3_600, 1_000_000, "ttl_lru_memory", "job_id"),
    CachePolicy("topology-sync-locks", "backend.engineering.topology_sync", 256, 0, 1, "bounded_registry", "topology_id"),
    CachePolicy("backend-job-registry", "backend.app.job_service", 100, 0, 250_000, "bounded_registry", "job_id"),
)


INVENTORY: tuple[InventoryEntry, ...] = (
    InventoryEntry(
        "Browser",
        "Visible viewport, selected detail, transient interaction state.",
        "Full project graphs, full trace histories, all simulation payloads.",
        "Virtualize tables and graph surfaces; paginate details only by user intent.",
        "No authoritative persistence in the browser.",
    ),
    InventoryEntry(
        "React State",
        "Bounded summaries, selected ids, small forms and detail records.",
        "Unbounded Maps/Sets, full historical snapshots, raw agent transcripts.",
        "Use list projections and lazy detail endpoints.",
        "State may be discarded at reload.",
    ),
    InventoryEntry(
        "Frontend Query Cache",
        "Small route, snapshot and chat projections with explicit ttl.",
        "Raw result payloads without byte and entry limits.",
        "Cache by stable project/resource/id keys.",
        "File cache is temporary and can be regenerated.",
    ),
    InventoryEntry(
        "Global Frontend Store",
        "UI preferences and current workflow markers.",
        "Project source of truth or simulation artifacts.",
        "Store identifiers, not objects.",
        "Persistent truth stays in backend/project storage.",
    ),
    InventoryEntry(
        "WebSocket Buffer",
        "Recent events and status deltas.",
        "Complete trace files or replay archives.",
        "Ring buffer with max events and resumable cursor.",
        "Long-lived streams are written as artifacts.",
    ),
    InventoryEntry(
        "Canvas/Graph Renderer",
        "Viewport nodes, edges, handles and visible labels.",
        "Every route edge for every project at once.",
        "Layout returns drawable windows and semantic groups.",
        "Graph model remains canonical backend data.",
    ),
    InventoryEntry(
        "Backend Process RAM",
        "Hot jobs, active locks, bounded summaries.",
        "Historical stores, full object inventories for every project.",
        "Service methods expose summaries by default.",
        "Database and artifact store own history.",
    ),
    InventoryEntry(
        "Python Cache",
        "Compiled calculations and active run scratch data.",
        "Cross-project result archives.",
        "Evict by ttl/count and keep payload caps.",
        "Persist only reproducible inputs and artifacts.",
    ),
    InventoryEntry(
        "Redis",
        "Optional distributed hot cache with ttl.",
        "Canonical engineering objects.",
        "Namespace every key by project and cache purpose.",
        "Database remains the source of truth.",
    ),
    InventoryEntry(
        "Database",
        "Canonical engineering model, relations, metadata, versions.",
        "Renderer-only layout scratch larger than policy.",
        "Expose indexed projections before full joins.",
        "Authoritative persistent store.",
    ),
    InventoryEntry(
        "Artifact Store",
        "Large simulation traces, exports, reports and evidence bundles.",
        "Mutable UI state.",
        "Fetch artifacts by id and byte-range/window when possible.",
        "Durable append-only evidence.",
    ),
)


PROJECTION_LIMITS: dict[str, dict[str, int]] = {
    "table_default_rows": {"soft": 50, "hard": 250},
    "matrix_visible_rows": {"soft": 50, "hard": 250},
    "matrix_visible_columns": {"soft": 20, "hard": 80},
    "graph_visible_nodes": {"soft": 250, "hard": 500},
    "trace_visible_events": {"soft": 5_000, "hard": 20_000},
    "agent_visible_messages": {"soft": 40, "hard": 60},
    "snapshot_list_bytes": {"soft": 256_000, "hard": 1_000_000},
}


def performance_governance_summary() -> dict[str, Any]:
    return {
        "principle": "Large data lives in backend persistence; browser, React state and hot caches receive bounded projections.",
        "large_object_threshold_bytes": LARGE_OBJECT_THRESHOLD_BYTES,
        "memory_budgets": [asdict(item) for item in MEMORY_BUDGETS],
        "cache_policies": [asdict(item) for item in CACHE_POLICIES],
        "inventory": [asdict(item) for item in INVENTORY],
        "projection_limits": PROJECTION_LIMITS,
    }


def assert_within_budget(name: str, payload_size_bytes: int) -> None:
    budget = next((item for item in MEMORY_BUDGETS if item.name == name), None)
    if budget is None or payload_size_bytes <= budget.hard_limit_bytes:
        return
    raise ValueError(
        f"{name} is {payload_size_bytes} bytes; hard limit is {budget.hard_limit_bytes}. "
        f"{budget.remediation}"
    )
