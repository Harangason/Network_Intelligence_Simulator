# AI Routing

## Generation

`RoutingGenerationService` resolves producer and consumers from the canonical
model, traverses `CONNECTED_TO` interface relations, builds bounded path
candidates and ranks them by protocol compatibility, hops, gateways and estimated
latency. It can suggest consumers, gateways, networks, protocols, fallback paths
and simplifications.

`HybridRoutingRetriever` combines:

- graph candidates;
- keyword and metadata matches from canonical/imported objects;
- approved route history;
- protocol rules.

Results are source-labelled, scored and truncated before they become proposal
context. The current local retrieval path is deterministic. A vector-store and
external reranker can be attached behind the same retriever contract; no vector
result is fabricated when no adapter is configured.

## Agent permissions

The Engineering Agent can read, find paths, generate proposals and validate. It
cannot approve, release or administer routing. Tools expose technical evidence,
not hidden reasoning. Relevant tool groups cover object/topology inspection,
route/proposal inspection, graph neighbors and paths, generation, optimization
suggestions and technical validation.

## Human-in-the-loop

```text
request -> retrieval -> proposal -> validation -> human review -> approval
```

Proposal acceptance means "create draft". Only explicit UI/API approval moves a
valid route into the approved table.

