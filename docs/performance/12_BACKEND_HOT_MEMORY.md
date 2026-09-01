# Backend Hot Memory

Backend process memory may contain active jobs, current calculations and compact
status summaries.

It must not become the archive for:

- Historical simulation results
- Full trace files
- Project-wide analysis payloads
- Every generated proposal in full detail

Those belong in the database or artifact store.

