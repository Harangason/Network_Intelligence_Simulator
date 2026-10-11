# Hardware- und Netzwerkmodell

## Kernstruktur

```text
Hardware
  └─ Port
       └─ Netzwerk-Schnittstelle
            └─ Netzwerk
```

Hardware kann ECU, Sensor, Aktor, Gateway, Steuerung, Rechner oder ein anderes
physisches beziehungsweise virtuelles Gerät sein.

Ein Port beschreibt den physischen Anschluss. Eine Netzwerk-Schnittstelle
beschreibt die logische Konfiguration auf diesem Port. Dadurch kann ein
Ethernet-Port mehrere IP-/VLAN-Schnittstellen und ein Mehrprotokoll-Port
mehrere logische Busbindungen besitzen.

## Bereits umgesetzt

- `hardware_profile.py`
- Aliasauflösung für Hardware, Nodes, Devices, ECUs, Ports und Interfaces
- unveränderte Übernahme zusätzlicher Quellfelder
- normalisierte IDs und Technologiereferenzen
- Port-/Schnittstellen-/Netzwerk-Zusammenfassung
- nicht-invasive Validierung
- Ausgabe in Manifest und Simulationsergebnis
- offene Technologieprofile

## Validierung

Erkannt werden:

- doppelte IDs
- Hardware ohne Ports
- Ports ohne Netzwerk-Schnittstellen
- Schnittstellen ohne Netzwerk
- unbekannte Netzwerkverweise
- ungenutzte Netzwerke
- Technologien ohne Profil

## Simulationswirkung

Bereits aktiv:

- Health-Zustände können Sender deaktivieren
- Technologieprofile begrenzen Payloadgrößen
- Zyklus und Jitter steuern Zeitstempel
- Technologie und Netzwerk werden je Event ausgewiesen

Geplanter Tiefenausbau:

- technologiespezifische Arbitration
- Buslast und Überlast
- Startup-Zeit und Clock Drift
- Gateway-Latenz
- elektrische Fehler und Terminierung
- technologiespezifische Wiederholungs- und Fehlerregeln
