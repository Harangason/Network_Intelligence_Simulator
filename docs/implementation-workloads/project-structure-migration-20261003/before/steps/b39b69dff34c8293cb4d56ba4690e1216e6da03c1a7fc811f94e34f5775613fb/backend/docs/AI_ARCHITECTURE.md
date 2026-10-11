# AI Architecture

## Safety Boundary

```text
User -> Agent -> read/retrieval tools -> AIProposal -> validation
     -> human review -> Approval Service -> Engineering Model
```

The forbidden path is LLM to direct Engineering Model mutation. The current
agent therefore stores object and relation suggestions in
`engineering_ai_proposals`; generic CRUD rejects direct AI writes.

## Model Gateway

`backend.knowledge.AIModelGateway` exposes `generate`, `embed`, `rerank`, and `classify`.
Business services may not call a provider directly. Provider adapters and model
routing remain replaceable so embeddings, reranking, extraction, classification,
and generation can use appropriately sized models. `LocalAIProvider` is the
offline reference provider; hosted providers can implement the same `AIProvider`
contract.

## Explainability

Stored proposals contain the prompt, model identity, retrieved context,
evidence, confidence, proposed objects, and validation results. Explanations are
short engineering summaries; internal chain-of-thought is neither stored nor shown.
