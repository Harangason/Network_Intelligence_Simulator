# Technology Modules

## Target

Each communication technology owns parameter schema, validation, frame estimate, load model, timing model and optional encoder/decoder.

## Current State

`backend/engineering/capacity/calculators.py` contains shared estimates. `backend/simulator/physic_lib/Industries/registry.py` provides an industry-oriented technology catalog.

## Migration Path

Create a technology registry contract under Python engineering services, then migrate CAN, CAN-FD, LIN, Ethernet and SOME/IP first because they are active in the wizard.
