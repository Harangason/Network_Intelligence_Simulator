# Address Model

`LogicalNodeAddress` enthält `value`, `formatted_value`, `namespace`, `assignment_mode`, `status` und `provenance`. Persistiert werden diese Angaben am HardwareNode. Modi: `AUTO`, `MANUAL`, `IMPORTED`, `RESERVED`. Status: `UNASSIGNED`, `PROPOSED`, `ASSIGNED`, `CONFLICT`, `RESERVED`, `OUTDATED`, `INVALID`.

Die Eindeutigkeit wird in PostgreSQL per partiellem Unique Index über `(project_id, address_namespace, logical_node_address)` und zusätzlich im Python-Service geprüft. Eine Adresse ist weder CAN-Identifier noch IP-Adresse.
