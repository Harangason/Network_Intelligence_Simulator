# Quellenverzeichnis und projektbezogene Technikfreigabe

## Herkunft und Darstellung

Die TechnologyRegistry bleibt die einzige Quelle für Technikidentität und
Parameterherkunft. `/api/technology-sources` projiziert ihre tatsächlichen
Quellenverweise; `source_metadata.json` ergänzt bibliografische und rechtliche
Metadaten, keine zweite Technik- oder Parameterdefinition.

Eine Quelle erscheint einmal mit allen zugeordneten Bustypen. Fragmentanker,
RFC-Dateiformate und identische GitHub-Blob-/Raw-Dateien werden zusammengefasst.
Abweichende Repository-Revisionen, Dokumentversionen und URL-Abfrageparameter
bleiben getrennt. Namensgleichheit allein belegt keine Dokumentidentität.

Die Oberfläche sortiert zunächst nach Bustypkürzel, unterstützt Fuzzy-Suche
und auf-/absteigende Sortierung. Linktexte bleiben kurz. Nicht belegte
historische Abrufdaten sind **Nicht dokumentiert**, keine erfundenen Tagesdaten.
Lizenzprüfdatum, Publikationsdatum und Abrufdatum sind unterschiedliche Angaben.

## Rechtebewertung

Dokumentzugang, öffentliche Weitergabe, Code-Lizenz, Implementierung,
Patentlizenz, Markenverwendung und Produktzertifizierung sind getrennt.
NIS veröffentlicht im Verzeichnis eigene bibliografische Metadaten und Links,
keine Original-PDFs, Normtabellen, Bilder oder übernommenen Quelltexte.

Jede Quelle erhält einen Rechtsstatus:

- `UNRESOLVED`: keine ausdrückliche Erlaubnis nachgewiesen; Stoppsymbol.
- `PERMISSION_REQUIRED`: belegte Weitergabebeschränkung; Stoppsymbol.
- `CONDITIONAL`: Erlaubnis unter konkreten Bedingungen; Informationssymbol.

Eine geprüfte Herausgeberregel kann die nächste Handlung begründen, ersetzt aber
keinen Sonderhinweis der konkreten Dokumentversion. Ungeklärte Quellen werden
nicht als frei, verboten oder rechtsverbindlich geklärt ausgegeben. Die
Lizenzdialoge nennen den tatsächlichen Prüfbereich und eine Primärquelle.
Ungeprüfte Ausnahmen benötigen ausdrücklich eigene dokumentbezogene Freigaben.

Matter-Core-Dokumentlizenz und SDK-Lizenz bleiben getrennt. RFC-Wiedergabe ist
bedingt, keine pauschale Erlaubnis für geänderte Textauszüge oder Patentnutzung.
Eine NXP-/TI-Application-Note gewährt keine allgemeine Veröffentlichungslizenz.

## Vorsorgliche NIS-Ausführungssperre

Für NMEA 0183/2000 und MIPI CSI-2/DSI verlangt die registrierte NIS-Policy einen
geprüften, projektbezogenen Nachweis für den tatsächlich geplanten Umfang.
Die Policy ist eine vorsorgliche Produktentscheidung und keine Behauptung, dass
jede abstrakte Simulation nach dem Recht des Lizenzgebers lizenzpflichtig ist.
I3C Basic wird nicht durch eine pauschale MIPI-Mitgliedschaftsregel gesperrt.
Ungeklärte Dokumentveröffentlichungsrechte allein sperren keine gesamte Technik.

Die Technik bleibt auswählbar und ihre bisherigen Daten bleiben lesbar.
Ausführungssperren werden durch die HTTP-Oberfläche angezeigt und bei
Simulationseinreichung, Konfigurationsvorbereitung und Preflight serverseitig
anhand der tatsächlichen Technikidentitäten geprüft, auch bei gemischten Netzen.
Frontendflags, Warnungsbestätigung und Branchenname dürfen die Sperre nicht lösen.

## Nachweise und Prüfung

`POST /api/technology-licenses` nimmt nur eine **PENDING**-Referenz an:
Technik, Lizenzgeber, Vertragsreferenz, Nutzungsumfang, optionales Ablaufdatum.
Ein ausdrückliches Projekt ist notwendig. Einreichung ist keine Freigabe;
HTTP besitzt keinen Approval-Endpunkt und übernimmt keine Bestätigungsflags.
Keine Lizenzschlüssel, Vertragsgeheimnisse oder Dokumentuploads in dieser Ansicht.

Ein Betreiber prüft den tatsächlichen Nachweis und genehmigt oder widerruft über
`scripts/manage-technology-license.py`. Der Freigabebefehl benötigt Prüfer,
Begründung und eine tatsächlich gelesene Nachweisdatei; deren SHA-256 wird
protokolliert, ihr Inhalt wird nicht veröffentlicht. Die Prüferbestätigung ist
ein administrativer Vertrauensentscheid, keine automatische Echtheitsprüfung.

Beispiel im laufenden Container mit dort bereitgestelltem Nachweis:

```text
python scripts/manage-technology-license.py --project PROJEKT --record NACHWEIS_ID --reviewer PRUEFER --decision approve --evidence /pfad/zum/geprueften/nachweis --rationale "Geprüfter Umfang deckt diese NIS-Nutzung"
```

Nachweise liegen im persistenten Runtime-Mount unter
`technology-license-evidence`. Dateinamen verwenden den Hash der normalisierten
Projekt-ID. Betriebssystem-Dateisperre und atomare Ersetzung koordinieren API
und Betreiber-CLI. Originaldaten werden nicht überschrieben.

Freigabe gilt nur für das konkrete Projekt, die Technik, den geprüften Scope
und die aktuelle Policy-Revision. Abgelaufene, widerrufene oder veraltete
Nachweise schalten nicht frei. Lizenzfreigabe bestätigt weder Kapazität noch
vollständige Protokollimplementierung, Security, SIL/PL oder Zertifizierung.
