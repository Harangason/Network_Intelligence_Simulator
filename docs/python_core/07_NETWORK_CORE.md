# Network Core

## Target

Networks, interfaces, ports, topology edges and gateway boundaries belong to Python.

## Current State

Topology synchronization exists in Python, while the frontend network editor still holds substantial mapping and interpretation logic.

## Migration Path

Build Python mappers from persisted hardware/interfaces/topology to `Network` and `NetworkInterface` core objects. Use those mappers for routing, capacity and simulation snapshots.
