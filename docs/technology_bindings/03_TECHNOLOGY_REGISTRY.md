# TechnologyRegistry

`TechnologyRegistry` owns profiles and independent component registries for bindings, generators, validators, encoders, decoders, timing models, and load calculators.

Public operations: `register_binding`, `register_generator`, `register_validator`, `register_encoder`, `register_decoder`, `register_load_calculator`, `register_timing_model`, `get_capabilities`, `resolve_binding`, `resolve_generator`, and `resolve_stack`.

Validierte generierte Technology Packs werden über
`register_generated_profile` aufgenommen. Dieser Pfad darf eingebaute Profile
nicht ersetzen und bewahrt Pack-Herkunft, Revision und Knowledge-Status. Details:
`../TECHNOLOGY_KNOWLEDGE_ONBOARDING.md`.
