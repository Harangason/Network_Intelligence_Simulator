# Agent Tool Architecture

## Current Tools

The chat agent can list canonical objects and relations and can create separate
object or relation proposals. It cannot approve objects. Tool loops are bounded.

## Tool Registry

Tools are grouped as `READ`, `PROPOSE`, `SIMULATE`, `REVIEW`, `APPROVE`, and
`ADMIN`. The default agent receives only `READ`, `PROPOSE`, and `SIMULATE`.
Approval tools require an explicit user command plus authorization enforced by
the service, not merely by the prompt.

Validation tools cover duplicate and conflict detection, payload, bus load,
cycle time, range, and transport compatibility. Read tools will expose canonical
objects, topology, requirements, imported sources, graph paths, and simulation
observations through typed service APIs.

`retrieve_engineering_knowledge` is a read-only hybrid retrieval tool. It returns
bounded context and evidence, never raw unbounded database dumps. Routing and
Capacity tools can create proposals or What-if analyses but cannot approve them.

All tool calls that can alter durable state require audit records with actor,
agent, model, tool, object, operation, before/after state, evidence, and approval.
