# Memory Budgets

Budgets are defined in `backend/engineering/performance_governance.py`.

Important limits:

- Workflow state response: 512 KB soft, 2 MB hard.
- Simulation snapshot list: 256 KB soft, 1 MB hard.
- Frontend working set: 64 MB soft, 128 MB hard.
- Graph viewport: 250 nodes soft, 500 nodes hard.
- Trace event window: 5,000 events soft, 20,000 events hard.
- Backend hot cache: 64 MB soft, 128 MB hard.

