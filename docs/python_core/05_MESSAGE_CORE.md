# Message Core

## Target

Messages are transport payload containers. Packing, payload occupancy, DLC validation and message lifecycle belong to Python.

## Current State

Message metadata is persisted through engineering repositories. Payload and signal occupancy checks exist in Python signal audit and are partly duplicated in TypeScript network inspection.

## Migration Path

Create a Python message packing service that consumes `Message`, `Signal` and `Encoding` core objects, then expose message inspection through the API.
