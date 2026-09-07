# Teststrategie

Die Verifikation umfasst: Hex-Parsing/-Formatierung und Grenzwerte; Device-Class-Defaults; reservierte und doppelte Adressen; atomare Vergabe; Policy-Strategien; Node/Interface/Network/Binding/Route-Auflösung; Invalidation; Bundle-Roundtrip; MCP-Schemas; Simulation- und Trace-Felder; Frontend-Typecheck/Build und Browser-E2E.

Referenzprojekt: `CentralGateway`, `PowertrainECU`, `BrakeECU`, `PLC_Main` sind adressierbar; `BasicTemperatureSensor` bleibt standardmäßig ohne eigene Adresse. Danach werden REST-Endpunkte, Routing, Simulation und sichtbare TX/RX-Darstellung geprüft.
