# Routing Architecture

The Routing Manager is an engineering layer above the existing communication
simulator. It does not replace technology profiles, trace writers or generators.

```text
Canonical Engineering Model
          |
          v
HybridRoutingRetriever + RoutingGenerationService
          |
          v
RoutingProposal -> RoutingValidator -> Human Approval
          |
          v
Approved RoutingEntry set
          |
          v
CommunicationConfigBuilder -> existing simulator
          |
          v
SIMULATED_IN relation + routing audit observation
```

## Boundaries

- Signals and messages remain canonical references; routing never copies them.
- Interfaces and `CONNECTED_TO` relations describe available connectivity.
- `RoutingGenerationService` reads topology and creates proposals only.
- `RoutingValidator` proves static consistency and estimates latency/load.
- Repository governance is the only approval path.
- `CommunicationConfigBuilder` consumes approved routes only.
- Simulation completion records compact observations against route IDs.

PostgreSQL stores routes, proposals, conditional rules and the audit trail. An
approved route also publishes `ROUTES_TO` and `USES_ROUTE` graph relations.

## UI

`/studio/routing` exposes Table, Graph, Matrix, AI Proposals, Validation and
Conflicts views. The global Engineering Assistant is shared with every page.
