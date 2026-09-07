# Findings und Validation

Preflight und Intelligence verwenden den Allocator für `DIAGNOSTIC_ADDRESS_MISSING`, `DIAGNOSTIC_ADDRESS_CONFLICT`, `DIAGNOSTIC_ADDRESS_INVALID`, `DIAGNOSTIC_ADDRESS_RESERVED`, `DIAGNOSTIC_ADDRESS_OUTDATED`, `ADDRESS_BINDING_MISSING` und `ADDRESS_ROUTE_UNRESOLVED`.

Manuelle Änderungen werden gegen Bereich, Reservierungen und Eindeutigkeit validiert. Vor der Änderung liefert die Impact-Analyse betroffene Routen, Bindings, Simulationen und Traces. PATCH verlangt danach eine ausdrückliche Bestätigung.
