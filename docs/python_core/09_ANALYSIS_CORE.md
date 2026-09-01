# Analysis Core

## Target

Capacity, bus load, timing, latency, jitter, queueing, bottleneck and root-cause analysis belong to Python.

## Current State

Capacity and timing are already Python-first in `backend/engineering/capacity`. The service is large and mixes calculation, grouping, persistence and report DTO shaping.

## Migration Path

Split pure calculations from persistence and API presentation. Use technology modules for protocol-specific load and timing behavior.
