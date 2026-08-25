# Routing Model

## RoutingEntry

`RoutingEntry` is a versioned aggregate. JSONB subdocuments preserve protocol-
neutral details without creating parallel signal or interface definitions.

| Area | Main fields |
|---|---|
| Identity | `id`, `route_code`, `revision`, `supersedes_id`, `name` |
| Source | node, port, interface, network, protocol |
| Payload | interface definition, message, selected signal IDs, topic, data object |
| Destinations | one or more nodes, interfaces, networks and protocols |
| Path | hops, gateways, transformations, priority |
| Timing | cycle, timeout, maximum latency, jitter |
| Policy | routing type, redundancy mode, fallback route, conditions |
| Governance | origin, confidence, review, approval, actors, timestamps |

Supported route types include unicast, multicast, broadcast, publish/subscribe,
request/response, cyclic, event-based, conditional, redundant and gateway-routed.
Protocols include CAN families, LIN, FlexRay, Ethernet, SOME/IP, TCP/UDP, DDS,
ROS 2, OPC UA, EtherCAT, PROFINET, Modbus, ARINC, MIL-STD-1553 and custom.

Approved revisions are immutable. Editing one creates a pending draft revision
with the same `route_code`; validation is reset.

## RoutingProposal

AI output is stored separately with prompt, target objects, generated routes,
retrieved context, evidence, confidence, validation results and model metadata.
Accepting a proposal creates pending drafts, never approved routes.

## RoutingRule

A rule stores `condition`, `action`, `priority`, status and version. It supports
conditional and fallback routing without embedding executable code. Approved or
released rules are immutable and cannot be deleted.

