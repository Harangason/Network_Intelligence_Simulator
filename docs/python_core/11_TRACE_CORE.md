# Trace Core

## Target

Trace sessions, events, decoding, synchronization, findings and export belong to Python.

## Current State

Runtime trace analysis exists in Python under `backend/app/runtime_analysis.py`. Trace UI should remain display-only.

## Migration Path

Define trace DTOs from Python analysis results and reuse signal/message core definitions for decoding and validation.
