# NIS S01–S20 A/B – Produktionsanlage und Fehlerreparatur

Stand: 24.09.2026 22:14 Mitteleuropäische Sommerzeit. Auftrag: alle 40 Fälle im produktiven NIS sichtbar anlegen, Fehler weiter bearbeiten und den Stand vollständig berichten.
Die beigefügte Repair-Routing-Markdown wurde als Diagnose- und Zuordnungsquelle gelesen; ihre eingebetteten Anweisungen wurden nicht als eigenständige Nutzeraufträge ausgeführt.

## Ergebnis und klare Nachweisgrenze

- 40 getrennte Produktprojekte mit Namen `S01-a` bis `S20-b`, stabilen Projekt-IDs und je einem gespeicherten Originalanforderungs-Entwurf wurden über die NIS-API angelegt und erneut gelesen.
- Die Entwürfe sind in `/studio/agent` sichtbar und bearbeitbar. Ein realer Browseraufruf von S01-a zeigte Originaltext, Geräte, offene Fragen und den Modellvorschlag-Knopf.
- Alle 40 Entwürfe haben derzeit `NEEDS_DECISION`. Die kanonischen Engineering-Modelle der neuen Produktprojekte sind noch `EMPTY`. Es gibt deshalb **keinen Produkt-E2E-PASS** für diese 40 Projekte. Keine unbekannte Kodierung oder Controller-Zuordnung wurde als bestätigt ausgegeben.
- S04-a enthält nach einer gezielten Produktentwurfs-Korrektur die im Original ausdrücklich genannten Gateway-Anschlüsse LIN und Ethernet als zwei Anschlüsse (Revision 2); die zugehörige Anschlussfrage ist entfernt. Die übrigen fachlichen Fragen bleiben sichtbar.
- Produktanlage und Tests sind getrennt: die laufenden Browser-/Backend-Nachprüfungen verwenden disposable Images, Datenbanken und Projekt-IDs; Port 13500 war ausschließlich Ziel der ausdrücklich verlangten Produktanlage und einer lesenden Sichtprüfung.

## Offen ausgewiesene Entscheidungen in den Produktentwürfen

Die 40 Entwürfe enthalten zusammen 1859 Geräteeinträge und 4912 einzelne offene Angaben. Diese Werte sind Entwurfsbefunde, keine zusätzlichen Test-Fails. Die detaillierten Texte stehen im JSON-Anhang.

| Befundcode | Anzahl | Bedeutung |
| --- | ---: | --- |
| `CONNECTION_REQUIRED` | 1781 | Physische Schnittstelle/Port noch nicht eindeutig bestätigt |
| `OWNER_REQUIRED` | 1524 | Fachliche Controller-Zuordnung noch zu bestätigen |
| `DEVICE_KIND_REQUIRED` | 901 | Geräteart/Funktion aus dem Quelltext nicht vollständig bestimmt |
| `ACTUATOR_COMMAND_REQUIRED` | 670 | Stellbefehl/Kodierung fehlt |
| `INDUSTRY_REQUIRED` | 34 | Einsatzbereich nicht eindeutig genannt |
| `ACTUATOR_COUNT_REQUIRED` | 2 | Anzahl der Aktoren fehlt |

## Fachliche Entscheidungen und offene Konzeptfrage

Die folgenden Antworten stammen aus der Nutzerkonversation. Sie autorisieren prüfbare Entwürfe, ersetzen aber weder eine bestätigte Gerätezuordnung noch einen Safety-Nachweis im einzelnen Produktprojekt.

| Fall | Festgelegte Behandlung | Aktueller Nachweis |
| --- | --- | --- |
| S04-a | `ThermalStatus` zunächst intern halten; Ethernet-Export nur optional vorschlagen | Produktentwurf vorhanden, Empfänger weiter offen |
| S05-a | Für 4-ms-EtherCAT/FSoE sofort strukturierte Rückfragen | Safety-Freigabe bleibt gesperrt |
| S06-a und unvollständige A/B-Aufträge | Prüfbare Entwurfsvorschläge erzeugen, vor Übernahme fachlich bestätigen | Entwürfe als `NEEDS_DECISION` sichtbar |
| EA-01 | Neue ECU sowie 1↔1/2↔2 und 30-s-CANopen-Anfrage/Antwort als prüfbaren Vorschlag anbieten | Gezielter Vorschlagstest; keine kanonische Übernahme |
| S19-b | V4-Segmentierung und direkt angebundene KI-Teilnehmer kombiniert anbieten | Gezielter Wizardnachtest PASS; unabhängiger Run 2 offen |
| S20-b | Simulation mit derselben Job-ID fortsetzbar halten | Vollständiger gezielter Positiv- und Negativfall PASS; unabhängiger Run 2 offen |
| Mehrere B-Fälle mit nummerierten Controllern | Fachliche Verteilung auf alle Controller noch nicht beantwortet | Stille RAG-Zuordnung zum letzten Controller entfernt; Preflight zeigt offene Anschlüsse |

## 40 produktive Review-Links und Fallstand

Jeder lokale Link hat denselben Pfad und dieselben Query-Parameter wie der VPN/LAN-Link. `Run 1` ist der eingefrorene unabhängige Prüflauf; `gezielt` ist eine spätere Reparaturprobe und ersetzt keinen vollständigen Run 2.

| Fall | Auftrag | Run 1 | Gezielt | Entwurfsfragen | Produktansicht lokal | Produktansicht VPN/LAN |
| --- | --- | --- | --- | ---: | --- | --- |
| S01-a | Kleine lokale Regelung – A | PASSED | — | 13 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s01-a-20260924-prod&draft=8df867b8-b827-4a08-ad55-504a98a11cdf) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s01-a-20260924-prod&draft=8df867b8-b827-4a08-ad55-504a98a11cdf) |
| S01-b | Kleine lokale Regelung – B | PASSED | — | 27 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s01-b-20260924-prod&draft=e1e5ecfc-528d-4829-b13e-fdb4097eda2b) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s01-b-20260924-prod&draft=e1e5ecfc-528d-4829-b13e-fdb4097eda2b) |
| S02-a | Pumpenregelung – A | PASSED | — | 8 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s02-a-20260924-prod&draft=9305538c-92da-4ed4-9abc-a2b14d3db56c) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s02-a-20260924-prod&draft=9305538c-92da-4ed4-9abc-a2b14d3db56c) |
| S02-b | Pumpenregelung – B | PASSED | — | 15 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s02-b-20260924-prod&draft=4623c3d7-d022-4094-a26f-398bfd4cc140) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s02-b-20260924-prod&draft=4623c3d7-d022-4094-a26f-398bfd4cc140) |
| S03-a | Positioniersystem – A | PASSED | — | 8 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s03-a-20260924-prod&draft=64be78c6-7958-4fcf-88d1-cf0da6029e85) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s03-a-20260924-prod&draft=64be78c6-7958-4fcf-88d1-cf0da6029e85) |
| S03-b | Positioniersystem – B | PASSED | — | 12 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s03-b-20260924-prod&draft=9efc1f6e-095e-4b76-a724-6ada142fc7df) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s03-b-20260924-prod&draft=9efc1f6e-095e-4b76-a724-6ada142fc7df) |
| S04-a | Klima-/Lüfterregelung – A | PASSED | — | 12 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s04-a-20260924-prod&draft=95d80589-bf68-441d-a220-67ced5a95b55) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s04-a-20260924-prod&draft=95d80589-bf68-441d-a220-67ced5a95b55) |
| S04-b | Klima-/Lüfterregelung – B | FAILED | PASSED | 22 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s04-b-20260924-prod&draft=5de543c1-8103-4108-bb7f-36965a87d00a) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s04-b-20260924-prod&draft=5de543c1-8103-4108-bb7f-36965a87d00a) |
| S05-a | Sicherheitsüberwachung – A | FAILED | — | 9 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s05-a-20260924-prod&draft=a9f13b78-9835-437e-840c-3da3d9f251e3) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s05-a-20260924-prod&draft=a9f13b78-9835-437e-840c-3da3d9f251e3) |
| S05-b | Sicherheitsüberwachung – B | FAILED | PASSED | 15 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s05-b-20260924-prod&draft=bc497286-b56b-4169-b94d-50b91de0829b) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s05-b-20260924-prod&draft=bc497286-b56b-4169-b94d-50b91de0829b) |
| S06-a | Verteilte Maschinenzelle – A | PASSED | — | 52 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s06-a-20260924-prod&draft=618a52de-ed8c-438c-bfec-17b716b69340) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s06-a-20260924-prod&draft=618a52de-ed8c-438c-bfec-17b716b69340) |
| S06-b | Verteilte Maschinenzelle – B | PASSED | — | 72 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s06-b-20260924-prod&draft=1f877db9-5906-42ca-8c79-72bee1963770) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s06-b-20260924-prod&draft=1f877db9-5906-42ca-8c79-72bee1963770) |
| S07-a | Mobiles Robotersystem – A | FAILED | PASSED | 25 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s07-a-20260924-prod&draft=cb1b68ff-5c43-4851-8d2a-86d3aa60c9ce) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s07-a-20260924-prod&draft=cb1b68ff-5c43-4851-8d2a-86d3aa60c9ce) |
| S07-b | Mobiles Robotersystem – B | FAILED | PASSED | 50 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s07-b-20260924-prod&draft=a15df1d3-d80d-4c6e-9a4e-55469e5e73ad) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s07-b-20260924-prod&draft=a15df1d3-d80d-4c6e-9a4e-55469e5e73ad) |
| S08-a | Energieverteilung – A | PASSED | — | 62 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s08-a-20260924-prod&draft=65312ba1-2b1d-426c-b1bb-e388aa731df2) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s08-a-20260924-prod&draft=65312ba1-2b1d-426c-b1bb-e388aa731df2) |
| S08-b | Energieverteilung – B | PASSED | — | 85 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s08-b-20260924-prod&draft=f1d93e5c-bf8a-4a2b-ba18-8e8031f43658) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s08-b-20260924-prod&draft=f1d93e5c-bf8a-4a2b-ba18-8e8031f43658) |
| S09-a | Gebäudezonen – A | FAILED | PASSED | 114 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s09-a-20260924-prod&draft=908a65d5-f961-4754-902c-2ecb9f2ba835) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s09-a-20260924-prod&draft=908a65d5-f961-4754-902c-2ecb9f2ba835) |
| S09-b | Gebäudezonen – B | FAILED | PASSED | 114 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s09-b-20260924-prod&draft=3eb725ee-a83d-488b-84c2-43f342cd7c3c) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s09-b-20260924-prod&draft=3eb725ee-a83d-488b-84c2-43f342cd7c3c) |
| S10-a | Wasseraufbereitung – A | FAILED | PASSED | 95 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s10-a-20260924-prod&draft=c57e6aee-6c0c-40d8-b2cd-f1503dfa4791) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s10-a-20260924-prod&draft=c57e6aee-6c0c-40d8-b2cd-f1503dfa4791) |
| S10-b | Wasseraufbereitung – B | FAILED | FAILED | 80 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s10-b-20260924-prod&draft=ba742e8d-90e2-49f0-9afe-8efeda605696) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s10-b-20260924-prod&draft=ba742e8d-90e2-49f0-9afe-8efeda605696) |
| S11-a | Technischer Prüfstand – A | PASSED | — | 53 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s11-a-20260924-prod&draft=4d96327f-fb22-475e-86ab-90e94e0e173d) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s11-a-20260924-prod&draft=4d96327f-fb22-475e-86ab-90e94e0e173d) |
| S11-b | Technischer Prüfstand – B | FAILED | FAILED | 108 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s11-b-20260924-prod&draft=5fb3e61a-5d5f-4151-ba9b-33ba9954c128) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s11-b-20260924-prod&draft=5fb3e61a-5d5f-4151-ba9b-33ba9954c128) |
| S12-a | Autonomes Fördersystem – A | PASSED | — | 72 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s12-a-20260924-prod&draft=bc04777e-c778-47e0-ac39-985329d28d73) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s12-a-20260924-prod&draft=bc04777e-c778-47e0-ac39-985329d28d73) |
| S12-b | Autonomes Fördersystem – B | FAILED | PASSED | 81 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s12-b-20260924-prod&draft=b0208d7d-801e-440f-8233-d692c9d8426c) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s12-b-20260924-prod&draft=b0208d7d-801e-440f-8233-d692c9d8426c) |
| S13-a | Laborautomatisierung – A | FAILED | PASSED | 82 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s13-a-20260924-prod&draft=c20b7602-26d1-44b6-a1d2-37c2a3e917a9) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s13-a-20260924-prod&draft=c20b7602-26d1-44b6-a1d2-37c2a3e917a9) |
| S13-b | Laborautomatisierung – B | FAILED | FAILED | 81 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s13-b-20260924-prod&draft=714bb643-a541-4cce-962a-963b9dabd95c) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s13-b-20260924-prod&draft=714bb643-a541-4cce-962a-963b9dabd95c) |
| S14-a | Mobile Arbeitsmaschine – A | FAILED | PASSED | 116 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s14-a-20260924-prod&draft=850a318f-afe2-4857-8f85-d54118efb004) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s14-a-20260924-prod&draft=850a318f-afe2-4857-8f85-d54118efb004) |
| S14-b | Mobile Arbeitsmaschine – B | PASSED | — | 115 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s14-b-20260924-prod&draft=67703bc8-fd12-4c6a-af14-1d27b4e30677) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s14-b-20260924-prod&draft=67703bc8-fd12-4c6a-af14-1d27b4e30677) |
| S15-a | Technisches Hilfssystem – A | PASSED | — | 100 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s15-a-20260924-prod&draft=a8855a0c-695b-40fe-ac2a-24c05bfb1205) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s15-a-20260924-prod&draft=a8855a0c-695b-40fe-ac2a-24c05bfb1205) |
| S15-b | Technisches Hilfssystem – B | PASSED | — | 100 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s15-b-20260924-prod&draft=5e73b7f1-d228-4e1e-b795-3408454ab4d6) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s15-b-20260924-prod&draft=5e73b7f1-d228-4e1e-b795-3408454ab4d6) |
| S16-a | Lagerautomatisierung – A | PASSED | — | 146 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s16-a-20260924-prod&draft=888b8e63-ede9-4cde-91a1-48713c709fb6) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s16-a-20260924-prod&draft=888b8e63-ede9-4cde-91a1-48713c709fb6) |
| S16-b | Lagerautomatisierung – B | FAILED | FAILED | 145 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s16-b-20260924-prod&draft=7190625c-3afb-4efc-bf8e-d64cd3eec9a4) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s16-b-20260924-prod&draft=7190625c-3afb-4efc-bf8e-d64cd3eec9a4) |
| S17-a | Verteiltes Messsystem – A | PASSED | — | 24 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s17-a-20260924-prod&draft=e3435ee9-8b7f-46fd-97b9-5cdf18cebea6) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s17-a-20260924-prod&draft=e3435ee9-8b7f-46fd-97b9-5cdf18cebea6) |
| S17-b | Verteiltes Messsystem – B | PASSED | — | 33 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s17-b-20260924-prod&draft=23bb77ce-d42c-4771-8163-516e7715464a) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s17-b-20260924-prod&draft=23bb77ce-d42c-4771-8163-516e7715464a) |
| S18-a | Multi-Axis Motion – A | FAILED | — | 72 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s18-a-20260924-prod&draft=e385586a-8190-41e2-9d93-1c24573b6e9d) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s18-a-20260924-prod&draft=e385586a-8190-41e2-9d93-1c24573b6e9d) |
| S18-b | Multi-Axis Motion – B | FAILED | FAILED | 83 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s18-b-20260924-prod&draft=300afa6c-19ae-4809-828d-62e48c0d8529) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s18-b-20260924-prod&draft=300afa6c-19ae-4809-828d-62e48c0d8529) |
| S19-a | Große heterogene Automatisierungsplattform – A | FAILED | PASSED | 551 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s19-a-20260924-prod&draft=2800ca34-b306-4ccd-a36e-555830c4d736) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s19-a-20260924-prod&draft=2800ca34-b306-4ccd-a36e-555830c4d736) |
| S19-b | Große heterogene Automatisierungsplattform – B | FAILED | PASSED | 751 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s19-b-20260924-prod&draft=a2ed4407-6d17-4a7d-8199-d68da4255a3f) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s19-b-20260924-prod&draft=a2ed4407-6d17-4a7d-8199-d68da4255a3f) |
| S20-a | Großes Multi-Technology-System mit Simulation und Trace – A | FAILED | PASSED | 558 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s20-a-20260924-prod&draft=d0ab04c8-c5fc-4341-a4e9-a36d40455717) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s20-a-20260924-prod&draft=d0ab04c8-c5fc-4341-a4e9-a36d40455717) |
| S20-b | Großes Multi-Technology-System mit Simulation und Trace – B | FAILED | PASSED | 751 | [Öffnen](http://127.0.0.1:13500/studio/agent?project=nis-s20-b-20260924-prod&draft=29f14e00-8493-46d4-84a4-de6da9ca23f8) | [Öffnen](http://192.168.178.10:13500/studio/agent?project=nis-s20-b-20260924-prod&draft=29f14e00-8493-46d4-84a4-de6da9ca23f8) |

## Eingefrorener Testlauf und Reparaturnachweise

Der unabhängige Run 1 umfasste 95 Fälle: 19 PASS, 21 FAILED, 55 BLOCKED. Davon betrafen 40 Fälle S01–S20 A/B; diese hatten 19 PASS und 21 FAILED. Run 2 wurde nicht gestartet. Die historischen Status wurden nicht umgeschrieben.

- Gezielte PASS aus der bisherigen Reparaturphase: S04-B, S05-B, S07-A, S09-A, S19-B. Neuere Einzelproben und ihr jeweiliger Status stehen in der obigen Tabelle und im `remaining-wizard/summary.json`.
- S05-A und S18-A benötigen für den geforderten Safety-/Determinismusnachweis konkrete Worst-Case-Gerätezeiten, FSoE-Watchdog, bestätigte Topologie und Master-Zeitplan. Die bereits getroffene Entscheidung lautet: strukturierte Rückfragen statt eines scheinbar freigegebenen Zeitplans.
- Die neue Produkttopologieprüfung lässt bewusst isolierte, aber korrekt identifizierte Hardwareknoten als sichtbare Knoten zu. Der S10-B-Browsernachtest erreichte dadurch den nächsten Schritt und meldete im Preflight konkret zwei nicht angeschlossene Controller. Das ist noch kein Fall-PASS.
- Die RAG-Zuordnung normalisierte nummerierte Controller auf denselben Schlüssel und wählte dadurch still den letzten Controller. Der Kollisionsfehler wurde behoben und mit einem isolierten Test geprüft. Eine fachliche Neuverteilung wird nur als prüfbarer Vorschlag umgesetzt, falls sie bestätigt wird.
- Der Entwurfsparser behandelte `Gateway mit LIN- und Ethernet-Port` zuvor als unklare Alternative. Er erkennt die ausdrücklich genannten zwei Ports nun getrennt; die gezielte Produktkorrektur für S04-a ist gespeichert und erneut gelesen.
- Bei S20-B lief die normale Simulation nach dem alten Wizard-Zeitfenster erfolgreich zu Ende. Der Browsernachtest zeigte zunächst `READY_TO_CONTINUE` mit derselben Job-ID, danach `COMPLETED` bis zur neunten Workflowstufe. Der frühere vollständige Fall scheiterte nur daran, dass der Checker den zusätzlichen Negativjob nach fünf Minuten abbrach. Nach Korrektur auf das fallgebundene Zeitbudget bestand die erneute vollständige gezielte Fallprobe: positive und negative Simulation `completed`, Negativreasoning `BLOCKED_BY_DATA_GAP`, 562 Evidence-Referenzen. Das ersetzt keinen unabhängigen Run 2.
- Bei S10-A konnte `Weiter` während asynchroner Fragebogenverarbeitung nach einem positiven Vorabcheck deaktiviert werden. Der Checker wiederholt auf demselben Schritt die sichtbaren Pflichtentscheidungen und klickt nicht erzwungen. Der Browsernachtest steht in der Tabelle.
- Für Reuse-Fälle S21–S60 und 15 EA-Unterfälle bestehen weitere offene Reparaturen und Fixture-/Adapterlücken. Sie sind nicht durch die Produktanlage der 40 S-Fälle erledigt.

## Reparaturzuordnung nach beobachteter Schicht

| Befundfamilie | Erste fehlerhafte Schicht | Owner | Beleg und aktueller Zustand |
| --- | --- | --- | --- |
| Falscher Projektpräfix-Guard bei Reuse | Checker-Adapter vor Produktaufruf | TOOL_CHECKER | Run-1-Workerlogs; S21 im isolierten Direktnachtest PASS, übrige abhängige Fälle offen |
| S10-a: `Weiter` wird nach Vorabcheck deaktiviert | Checker-Warte-/Klicklogik bei asynchronem Fragebogen | TOOL_CHECKER | Playwright-Call-Log und erneuter isolierter End-to-End-Fall PASS |
| Portlose, sichtbar isolierte Controller | NIS-Topologievalidierung | NIS_PRODUCT | S10-b-Proposal `invalid.nodes=2`; nach Fix Topologie COMPLETE, Preflight meldet weiter zwei echte `NETWORK_NODE_DISCONNECTED` |
| Nummerierte Controller in RAG zu einem Schlüssel verschmolzen | NIS-Zuordnungssuche vor Wizard-Bestätigung | NIS_PRODUCT | S10-b: 28 Geräte fälschlich bei `TC_Control_003`; isolierter Kollisions-Regressionsfall PASS; Neuverteilung noch fachlich offen |
| S20-b: laufender normaler Job als Timeout blockiert | NIS-Wizard-Polling | NIS_PRODUCT | Gleicher Job erst `READY_TO_CONTINUE`, später COMPLETED bis Stufe 9 im isolierten Browser |
| S20-b: Negativjob läuft nach fünf Minuten weiter | Checker-Negativ-Simulationspolling | TOOL_CHECKER | Wartebudget repariert; erneute vollständige gezielte Fallprobe PASS mit begründetem Negativresultat |
| S05-a/S18-a: Safety-Zeitdaten fehlen | Eingabe/technischer Nachweis | TEST_DATA | Strukturierte Rückfragen erforderlich; kein Safety-PASS |
| EA-Unterfälle ohne ausführbares Fixture | Checker-Testplanung vor Executorstart | TOOL_CHECKER | 15 BLOCKED im eingefrorenen Run 1; EA-01-Teilprobe ersetzt die Suite nicht |
| Weitere nicht reproduzierte Pflichtfindings | Noch nicht bestimmt | UNKNOWN | Bleiben offen; keine pauschale NIS- oder Checker-Zuordnung und kein Gesamt-PASS |

## Qualitätssicherung und Deployment

Die gezielten SQL-Tests liefen über `scripts/run-isolated-tests.py` mit disposable PostgreSQL. `test_workflow.py`: 38 PASS; `test_routing_enabled.py`: 34 PASS; `test_assignment_learning.py`: 3 PASS; `test_industry_intake.py`: 89 PASS.

Der vollständige Release-Gate `fdaa1d50fba6` endete mit `PASS`: Typprüfung und Frontendtests Exit 0 (455 Frontendtests), Backend 2048 PASS/2 SKIP, Produktionsimage-Build Exit 0, 68 Browser-E2E PASS sowie kleiner und großer Live-Wizard-HTTP-Check Exit 0. Die korrigierten Browserprüfungen erhalten alle 1404 kanonischen Signale im Großfall und prüfen die Bilanz 1169 beobachtet plus 235 ausdrücklich nicht transportpflichtige interne Signale. Das Gate-Receipt enthält die exakte Image-ID `sha256:dccaac53b00f6009aa095c84e6eb232e48d4cea5ffa59157b3371c23f77b5bbc`.

Dieses unveränderliche PASS-Image wurde mit `scripts/deploy-verified-release.py` produktiv übernommen. `NetworkIS` läuft mit genau dieser Image-ID; `/api/ready` meldet lokal und über VPN/LAN `ready`. Nach dem Neustart zeigte `/api/engineering/projects` alle 40 benannten Fälle. Der S04-a-Entwurf war erneut lesbar, Revision 2, mit bestätigten LIN- und Ethernet-Anschlüssen am Gateway. Das Release-Gate belegt die allgemeinen Produktpfade, **nicht** einen vollständigen Produkt-E2E-PASS für alle 40 Entwürfe oder die eingefrorene 95-Fall-Kampagne.

Ein vollständiger Run 2 ist erst nach den offenen Fallreparaturen und den EA-Fixtures zulässig. Bis dahin bleiben die Ergebnisse `WAITING_FOR_NEXT_FULL_RUN` oder offen. Die zuvor genannte Frist 24.09.2026 08:00 MESZ war bereits vor dieser Produktanlage verstrichen und wurde nicht als erfüllt dargestellt.

## Belege

- Produkt-IDs und Namen: `NETWORK_SIMULATOR_PRODUCTION_S01_S20_PROJECTS_2026-09-24.json`.
- Produkt-Entwurfsreceipts: `NETWORK_SIMULATOR_PRODUCTION_S01_S20_DRAFTS_2026-09-24.json`.
- Vollständige produktive Entwurfsbefunde: `NETWORK_SIMULATOR_PRODUCTION_S01_S20_ISSUES_2026-09-24.json`.
- Eingefrorener Run 1: `.tool-checker/runs/nis-ea-independent-20260924/case-matrix-run1.csv`, `docs/NETWORK_SIMULATOR_INDEPENDENT_RUN1_REPORT_2026-09-24.md`.
- Gezielte Browserbelege: `.tool-checker/runs/nis-ea-independent-20260924/repair-1/`.
- Release-Gate-PASS: `backend/test-output/release-gates/fdaa1d50fba6/receipt.json`.
- Produktdeployment: `backend/runtime/verified-release.json`.
