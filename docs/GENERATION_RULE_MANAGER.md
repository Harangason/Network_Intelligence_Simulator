# Erzeugungsregel-Manager

Verbindliche Architekturregel für Wizard, Engineering-Agent und alle neuen
Generatoren. Laufzeitimplementierung:
`backend/engineering/generation_rule_manager.py`.

## Getrennte Entscheidungen

1. Die Industrie bestimmt ausschließlich Fachvokabular, Geräteklassen,
   Funktions- und optionale Branchenvorlagen.
2. Jeder bestätigte Bustyp bestimmt unabhängig davon seinen Transportgenerator,
   seine Topologie-, Timing- und Kapazitätsprüfung über die zentrale
   Technologie-Registry.
3. Ein Bustyp beweist keine Industrie. Eine Industrie beweist keinen Bustyp.
4. Gemischte Architekturen behalten pro Bustyp getrennte Erzeugungspfade. Sie
   werden erst am kanonischen Engineering-Modell zusammengeführt.

Expliziter Projektkontext hat Vorrang vor einer Stichwortableitung aus Freitext.
Mehrdeutige Branchen oder unbekannte/nicht ausführbare Bustypen bleiben als
Finding offen. Der Manager darf in diesen Fällen keine Automotive- oder andere
Branchenvorlage als stillen Fallback verwenden. `generic_networking` und
`custom` sind nur dann Fallbacks, wenn sie ausdrücklich gewählt wurden.

## Ausführung und Nachweis

Der gemeinsame Projektentwurf speichert `generation_policy`. Requirement
Expansion liefert dieselbe Entscheidung unter
`interpretation.generation_policy`. Der Wizard erzeugt die Entscheidung erneut
aus der bestätigten Spezifikation und persistiert sie in der Proposal-Evidence.
Die Entscheidung enthält Industriequelle, erkannte Busse, Registry-Stacks,
Generatoren, getrennte Transportpfade, Findings und einen stabilen Hash.

Die Frontend-Spezifikation ruft optionale Branchenanreicherungen ausschließlich
über `applyIndustryGenerationPath` auf. Gemeinsame Signalexpansion und
protokollspezifisches Packing laufen danach unabhängig von der Branche. Neue
Branchensonderfälle werden als eigener registrierter Branchenpfad ergänzt; sie
dürfen nicht als globales Verhalten oder als Default eines anderen Profils
implementiert werden.

## Änderungsschutz

Jede Änderung an Erkennung oder Pfadauswahl benötigt mindestens:

- einen positiven Test für die betroffene Industrie/Bustechnologie,
- einen Isolationstest gegen mindestens eine andere Industrie,
- einen Mixed-Bus-Test, wenn mehr als ein Bustyp betroffen ist,
- einen Test für mehrdeutige oder fehlende Eingaben,
- bestehende Registry-/Wizard-Regressionstests.

Technologiespezifische Validierung bleibt in den Technology Bindings. Regeln
aus `SPATIAL_ARCHITECTURE_CONTRACT.md`, `COMMUNICATION_DESIGN_CONTRACT.md` und
`NETWORK_NAMING_CONTRACT.md` werden durch die Pfadauswahl nicht ersetzt.

Ein unbekannter bestätigter Bustyp erhält den Pfad `technology_discovery` und
einen Knowledge-Status aus dem Technology-Onboarding. Recherche, Pack-Aufnahme
und Core-Registrierung folgen `TECHNOLOGY_KNOWLEDGE_ONBOARDING.md`; bis dahin
bleibt der Transportpfad nicht ausführbar.
