# Simulation Core

## Target

Simulation scenarios, signal behavior, function behavior, runtime state, faults, metrics and trace output belong to Python.

## Current State

Python simulation services exist under `backend/app` and `backend/engineering/simulation.py`. Frontend still contains simulation wizard behavior and local fallback logic.

## Migration Path

Keep frontend simulation controls as input forms. Move scenario interpretation and deterministic behavior generation behind Python APIs.
