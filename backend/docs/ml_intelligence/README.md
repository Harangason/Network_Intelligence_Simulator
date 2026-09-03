# Random Forest / Gradient Boosting ML Layer

Status: implemented as an advisory, review-gated ML layer.

## Purpose

The simulator now separates deterministic engineering logic from ML and LLM work:

- Python core: deterministic calculation, validation, routing and message packing.
- ML: classification, ranking and quality scoring.
- Qwen / LLM: interpretation, explanation and proposals.

ML never overwrites deterministic results directly. Packing, routing and architecture changes remain proposals until a user or workflow gate approves them.

## Implemented Tasks

- `SIGNAL_SEMANTIC_CLASSIFICATION`
- `STATUS_MODEL_CLASSIFICATION`
- `PHYSICAL_MODEL_SELECTION`
- `TRACE_FAULT_CLASSIFICATION`
- `ROUTE_CANDIDATE_RANKING`
- `MESSAGE_PACKING_QUALITY`
- `ARCHITECTURE_GAP_QUALITY`

## Models

Two candidates are trained for classifier tasks:

- `RANDOM_FOREST` baseline
- `GRADIENT_BOOSTING` candidate

If `scikit-learn` is not installed, both trainers use the built-in deterministic token ensemble fallback and preserve the same model registry metadata. This keeps the simulator runnable offline and leaves a clean replacement point for native sklearn models.

## Dataset Pipeline

`MLDatasetBuilder` implements:

- collect
- sanitize
- deduplicate
- feature extraction
- class-balanced ordering
- stratified train / validation / test split
- dataset version export

All model artifacts record `feature_schema_version` and are rejected at inference time when the runtime schema does not match.

## API

The Engineering API exposes:

- `POST /api/engineering/ml/models/train`
- `POST /api/engineering/ml/classify/signal`
- `POST /api/engineering/ml/classify/status`
- `POST /api/engineering/ml/classify/physical`
- `POST /api/engineering/ml/classify/fault`
- `POST /api/engineering/ml/rank/routes`
- `POST /api/engineering/ml/score/packing`
- `POST /api/engineering/ml/score/architecture`
- `POST /api/engineering/ml/explain/qwen`

Confidence policy:

- `HIGH_CONFIDENCE`: confidence >= 0.90
- `MEDIUM_CONFIDENCE`: 0.70 <= confidence < 0.90
- `REVIEW_REQUIRED`: confidence < 0.70

## Registry

Artifacts are stored under `backend/runtime/ml_registry` by default. Registry entries include model type, task, dataset version, feature schema version, metrics, status and artifact location.
