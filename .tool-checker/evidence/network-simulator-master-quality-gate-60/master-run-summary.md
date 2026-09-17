# Tool Checker Master-Quality-Gate 60 - Zwischenstand

Datum: 2026-09-17
Quelle: `NETWORK_SIMULATOR_MASTER_TEST_REPAIR_QUALITY_GATE_60_SCENARIOS.md`
Source hash: `e2409f24d4ae510d5289b283efd75d92b0bddc758c3fc7117e08fd5d883c7eab`

## Inventar

- 60/60 Testvertraege aufgenommen: S01-A bis S20-B, S21 bis S40.
- `verify-source`: PASS, keine Hash- oder Quellenprobleme.
- `dry-run all`: erfolgreich; Ausgabe umfasst alle 60 Vertraege.
- Vollstaendiger Masterlauf: NICHT ABGESCHLOSSEN.

## Bestaetigter Defekt und Reparatur

Der reale S01-A-Canary erkannte in einem gezaehlten Sensorblock nur zwei von drei
benannten Sensoren. `PT100 ueber SPI-ADC` ging verloren und wurde als generischer
`Sensor3` ersetzt. Dadurch blieb die Uebernahme deaktiviert. Der erste Browser-
Nachtest fand danach eine zweite Doppelzaehlung: `2 PWM-Ventile` wurden bei bereits
bestaetigtem Aktor-Sollwert auf vier generische Ventile erweitert.

Reparatur:

- Gezaehlte Sensor-/Aktor-Bloecke bewahren nun die konkreten Geraetenamen.
- `2 PWM-Ventile` wird als `Ventilaktor1` und `Ventilaktor2` expandiert.
- PWM-/Proportionalventile verwenden ihre lokale Anzahl auch bei bestaetigtem Sollwert.
- Regressionstest fuer PT100, Druck, Drehzahl, zwei Ventile, DC-Motor und Relais.
- Regressionstest deckt den rohen Auftrag und die reale Wizard-Huelle ab.

## Verifikation und Deployment

- Frontend: 399/399 Tests PASS.
- Backend: 1857 PASS, 2 SKIP.
- Browser E2E: 68/68 PASS, inklusive S01-A bis S20-B Scope-Inventar und realem Wizard.
- Typecheck, Produktionsbuild, Small-HTTP und Large-HTTP: PASS.
- Finales Release-Gate-Receipt: PASS.
- Getestetes Image: `sha256:1f8e9a523f7de50784b6069bf8e41563b5de96ca84746dba9b3dff3f32851b56`.
- Build: `ab227ba0c712`.
- Exakt dieses Image wurde deployed; `/api/health` meldet `status=ok` und denselben Build.

Finaler realer Hauptwizard-Canary auf Build `ab227ba0c712`:

- Projekt `20260917120720195-0835a0c0` ueber `Neues Projekt` angelegt.
- Geraeteumfang: Sensoren 3/3, Aktoren 4/4.
- Erkannte Namen: PT100, Druck, Drehzahl, Ventilaktor1/2, DC-Motor, Relaisausgang.
- Uebergabe startete den Agenten und erreichte das Modell-Review mit 72 gueltigen Aenderungen.
- Geskriptete Testfreigabe uebernahm 8 Geraete und setzte den Workflow fort.
- Der Lauf erreichte das Routing-Review mit 11/11 gueltigen Routen; kein Abbruch beobachtet.

## KI-Laufzeit

Der erste Health-Check meldete die lokale KI als nicht erreichbar. Ursache war ein
nicht lauschender Ollama-Dienst. Der Dienst wurde gestartet und erneut geprueft:

- Ollama ist auf Port 11434 erreichbar.
- Modell `qwen3.8:27b` ist installiert und wird von NIS erkannt.

Der Laufzeitblocker ist damit behoben. Der Mastervertrag ist trotzdem noch nicht
objektiv 60/60 nachgewiesen: Die gruenen Release-Gate-Tests ersetzen weder 40 ueber
den Hauptwizard erzeugte Projekte noch die geforderten positiven und negativen
Simulationen samt Trace-, Finding- und Reload-Evidence.

## Ergebnis

Release-Kandidat: PASS.

Master-Quality-Gate 60: INCOMPLETE/BLOCKED, kein finaler PASS.
