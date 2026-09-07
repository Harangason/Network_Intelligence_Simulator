# Agent- und MCP-Integration

Registrierte Werkzeuge: `get_logical_node_address`, `resolve_logical_node_address`, `find_free_logical_node_address`, `validate_logical_node_address`, `allocate_logical_node_address` und `resolve_route_by_address`. Sie rufen ausschließlich `LogicalNodeAddressAllocator` beziehungsweise `AddressResolutionService` auf.

Lesen und Validieren bleiben mutierungsfrei. Die Vergabe benötigt die Governance-Berechtigung `APPLY_APPROVED_PROPOSAL`; dadurch existiert kein zweiter Agenten-Allocator.
