# Semantic Intelligence Overview

This implementation adds the first controlled layer of semantic intelligence to the engineering tool. It is deliberately deterministic-first: rules and ontology provide the first evidence, local similarity provides a weak additional signal, and ML/DL/LLM adapters are present as explicit registration points rather than hidden authority.

## Implemented

- `SemanticConcept` with aliases, hierarchy, semantic type, expected units, ranges, datatypes, tags, constraints, examples, status and provenance.
- `ConceptOntology` with alias resolution, parent/child lookup, related concepts, relation validation and common ancestor lookup.
- `SemanticClassificationService` with heuristic, ontology, local similarity and confidence aggregation.
- API endpoints:
  - `GET /api/engineering/semantics/concepts`
  - `GET /api/engineering/semantics/concepts/{id}`
  - `POST /api/engineering/semantics/classify`
- Signal audit uses high-confidence semantic proposals to unblock deterministic bit optimization when an explicit `semantic_type` is missing.
- Classification results are proposals with a human-review gate. Unclear cases remain `UNKNOWN` or `AMBIGUOUS`.

## Guardrails

- No model output is a source of truth.
- LLM classification is not called in this layer and is marked `PROPOSAL_ONLY_NOT_CALLED`.
- ML and DL classifiers are modular placeholders until versioned models and datasets exist.
- Training data must come from approved engineering objects, reviewed findings or explicitly labeled synthetic scenarios.

## Next Step

Wire this service into parser and workload generation so generated signals receive explicit semantics earlier. Capacity audit already uses the service for high-confidence missing semantic types and still surfaces low-confidence cases for review.
