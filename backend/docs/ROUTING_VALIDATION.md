# Routing Validation

`RoutingValidator` resolves canonical references and returns structured errors,
warnings, evidence and metrics. Approval rejects every route whose latest
validation is not valid.

Checks include:

- source, destination, interface, message, signal and gateway existence;
- interface ownership and signal/message membership;
- source/destination protocol compatibility and explicit transformations;
- broken hops, unreachable consumers, gateway placement and routing loops;
- payload capacity, cycle, latency, jitter and estimated route load;
- duplicate routes and table-level conflicts;
- multicast/unicast cardinality;
- conditional rules and fallback/redundancy consistency.

The load estimate uses selected signal lengths or message DLC, cycle time and a
protocol capacity profile. It is an engineering pre-check, not a replacement for
runtime simulation. Simulation observations are linked back to the route through
`SIMULATED_IN` and audit events.

Validation never changes approval. Editing path-affecting fields clears previous
validation, returning the route to draft review.

