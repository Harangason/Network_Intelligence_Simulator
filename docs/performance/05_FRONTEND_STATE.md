# Frontend State

React state should contain only:

- Current filters
- Visible rows or rows needed for the active interaction
- Selected ids
- Loaded detail records for the selected item
- Compact counters and status summaries

Large snapshots and traces must be fetched lazily and discarded when no longer
needed.

