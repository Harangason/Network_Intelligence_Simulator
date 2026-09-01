# Model Registry

The model registry is planned for versioned classifiers and rerankers.

Registry fields should include model id, model type, version, task, training dataset, metrics, creation time, status and artifact location.

Allowed statuses are `TRAINING`, `EVALUATION`, `CANDIDATE`, `APPROVED`, `PRODUCTION` and `DEPRECATED`.
