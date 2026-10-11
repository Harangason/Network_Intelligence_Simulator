# Data Ingestion

## Target Flow

```text
Source -> Parser -> RawEntity -> Normalizer -> Canonical Mapper
       -> Entity Resolver -> Duplicate Detector -> Staging
       -> Knowledge Graph -> Embedding Pipeline -> Review
```

The active Engineering Import Wizard supports DBC, CSV, and XLSX. The
provider-neutral `SourceAdapterRegistry` additionally supports CSV, JSON, YAML,
XML, SQLite, PostgreSQL, and REST sources. PostgreSQL accepts read-only `SELECT`
queries; REST uses GET and delegates parsing by content type. ARXML, FIBEX, LDF,
OPC UA, AutomationML, ROS/ROS2, OpenAPI, and JSON Schema remain adapter
extensions.

The local import path has no configured file-size or row-count limit. Parsing
time and memory consumption therefore scale with the supplied source file.

Every staged entity must preserve source ID, location, source object, version,
import timestamp, and a raw payload reference. `POSSIBLE_MATCH` is review-only
and may never auto-merge.

## Current State

`POST /api/engineering/imports/preview` parses an uploaded file without changing
the canonical model. It returns detected column mappings, warnings, and counts
for the complete `HardwareNode -> Function -> Interface -> Message -> Signal`
hierarchy. `POST /api/engineering/imports/commit` persists the confirmed plan
with `source=import` and full import provenance.

The SHA-256 import ID and stable per-object import keys make commits idempotent:
re-importing identical content reuses the existing objects and graph edges.
Imported objects remain pending and unreviewed; import never bypasses governance.

`EngineeringChunker` separates documents by section and imported models by
HardwareNode, Function, Interface, Message and Signal. `KnowledgeIngestionPipeline`
indexes those chunks without changing the canonical source records. Imported
domains are preserved; absent domains default to `generic`, never to a hard-coded
industry.

`SourceIngestionService` materializes `RawEntity` and `StagedEntity` records
before indexing. It does not mutate the canonical model. The canonical commit
remains an explicit, reviewed action through the Engineering Import Wizard or a
future source-specific review UI.
