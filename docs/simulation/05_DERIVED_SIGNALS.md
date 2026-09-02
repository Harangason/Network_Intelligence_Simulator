# Derived Signals

Derived Signals werden ueber vorhandene Dependencies und `FORMULA` oder `STATE_DEPENDENT` berechnet.

Die Input-Werte kommen aus bereits berechneten Signalen des aktuellen Events. Damit werden abhaengige Signale nicht unabhaengig randomisiert.

Noch offen fuer einen spaeteren Ausbau:

- expliziter Dependency Graph
- Cycle Detection vor der Simulation
- Unit-Kompatibilitaetspruefung

