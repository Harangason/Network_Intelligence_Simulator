# Agent History

Agent history is a working context, not a permanent source of truth.

Current limits:

- Maximum messages per project: 60
- Maximum cached bytes per project: 1.5 MB plus envelope
- Maximum projects in cache: 100
- TTL: 24 hours

User-approved model changes must be persisted in the canonical engineering
model, not only in chat memory.

