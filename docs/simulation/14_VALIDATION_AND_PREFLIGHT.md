# Validation And Preflight

Bestehende Simulation- und Routing-Validierungen bleiben aktiv.

Der Signal-Preflight laeuft serverseitig in `validate_signal_emulation_model`, bevor eine projektbasierte Simulation gestartet wird. Das Ergebnis wird als `signal_emulation_validation` in die angereicherte Konfiguration und in den Model Trace geschrieben.

Blockierende Fehler:

- ungueltige Formula blockieren
- Dependency-Zyklen blockieren
- fehlende Message-/Signal-Mappings blockieren
- Signal-Encoding ausserhalb der Payload blockieren
- unbekannte Behavior-Modelle blockieren

Warnungen:

- fehlendes Behavior-Modell nutzt generische Fallback-Emulation
- `GENERIC_ESTIMATE` bleibt als Modellguete sichtbar
