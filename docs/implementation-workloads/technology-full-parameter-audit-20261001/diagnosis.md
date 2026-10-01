# Vollständige Einzelprüfung aller Technologieparameter

Freigabe: Nutzer am 01.10.2026, alle Bustypen einzeln, ohne Technikschwerpunkt.

Erste fehlerhafte Schicht: SimulationService._parameter_schema erzeugt denselben
großen Parametersatz für nahezu alle Profile. TechnologyProfile.parameter_schema
deklariert dagegen fast nur Raten. Die API überschreibt diese zentrale Definition.
Alle allgemeinen Felder werden dort required=True, obwohl viele Anforderungen,
Hardwareeigenschaften oder NIS-Szenariowerte sind und keine Busstandard-Defaults.
Historische Katalograten haben vielfach keine unabhängig geprüfte Normquelle.
Das betrifft auch lokale Geräte-/Transaktionsfelder und ihre Zuordnung zu Netz,
Controller, Zielgerät und tatsächlicher Transaktion.

Die vorherige Struktur-/Ratenprüfung ersetzt diese vollständige fachliche Prüfung
nicht. Ein bestätigter Takt ersetzt keinen Geräte- oder Kapazitätsnachweis.

Vorgehen: Alphabetische vollständige Einzelakten, jedes Feld mit Bedeutung,
Einheit, Gültigkeitsbedingungen, Quelle/Version, Default und Evidenzstatus.
Für jede Technologie zusätzlich Schichten, PHY, Zugriff, Integrität, Adressierung,
Discovery/Diagnose/Überwachung, Geräte- und Transaktionsanforderungen prüfen.
Keine Universalwerte erfinden. Fehlende tatsächliche Geräteangaben offen halten.
Normquellen und NIS-Szenariopolitik getrennt ausweisen. Erst bei vollständiger
belegter Einzelakte und bestandener Regression eine Technologie abschließen.

Alle bestehenden Korrekturen bewahren. Vollständiges Release-Gate und exakt
geprüftes Image produktiv ausliefern, dort Identität und Funktion kontrollieren.
