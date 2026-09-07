# Routing Integration

Routing-Einträge behalten ihre kanonischen `ObjectRef`-Endpunkte und erhalten zusätzlich Name, logische Adresse und Namespace als nachvollziehbaren Snapshot. `AddressResolutionService` löst eine Adresse zu Node, Interfaces, Networks, Bindings und beteiligten Routen auf. Zwei Adressen lassen sich direkt zu ihren gemeinsamen Routen auflösen.

Die ausführbare Simulationskonfiguration nimmt Adressen stets aus den aktuellen HardwareNodes, nicht aus möglicherweise alten Route-Snapshots.
