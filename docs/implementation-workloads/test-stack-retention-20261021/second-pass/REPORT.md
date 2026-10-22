# Prüfung der verbliebenen NIS-Images, 21.10.2026

Die 73 Images des ersten Abschlusses waren eine vorläufige Schutzmenge, kein Nachweis, dass 73 Images gebraucht werden. Die erste Inventur hatte Receipts in älteren Git-Worktrees und Dokumentationsordnern nicht mit erfasst. Die erweiterte Prüfung liest 494 ursprüngliche Receipt-Dateien aus dem kanonischen Projekt, seinen Dokumentationsordnern und allen drei registrierten historischen Worktrees; dabei traten keine Lesefehler auf.

Zusätzlich wurden **25 ungenutzte PREPARED-/FAIL-Kandidaten** vollständig archiviert, verifiziert und einzeln mit `docker image rm --no-prune` entfernt. Der frische Endbestand umfasst **49 NIS-Images**. Während dieser Prüfung hinzugekommene Images aus einem anderen aktiven Arbeitsablauf: **1**. Diese gehören nicht zum alten Bereinigungsumfang und bleiben erhalten.

| Gruppe im ursprünglichen Bestand | Anzahl | Bewertung |
| --- | ---: | --- |
| Laufende Produktion | 1 | Unverändert erhalten |
| Festgelegtes vollständiges PASS-Rollback | 1 | Unverändert erhalten |
| Weitere eindeutig ungenutzte Entwicklungs-/Fehlkandidaten | 25 | Geprüft archiviert und entfernt |
| Weitere historische Images mit vollständigem PASS | 40 | Kein aktueller Containerverweis; Aufbewahrungsnachweis noch offen |
| Alte nicht abschließend zugeordnete Stände | 6 | Fünf ohne eindeutigen Releasebeleg, eines mit historischem RUNNING-Receipt |

Für den laufenden Betrieb sind aus dem alten Bestand nur Produktion `3792d2e086e4` und das festgelegte Rückfallimage `09d1f624dfdd` ausdrücklich erforderlich. Die 40 anderen erfolgreichen Historien werden nicht als 40 benötigte Rollbacks ausgegeben. 35 sind älter als sieben Tage, fünf liegen noch innerhalb der Mindestaufbewahrung. Für keines dieser 40 Images liegt bislang der vom bestehenden `scripts/release_storage.py` verlangte vollständige Nachweis `SUPERSEDED_DELIVERED` mit `FULL_CANDIDATE_FEATURES` gegenüber der laufenden Produktion vor. Die unveränderte Policy wurde nach der Bereinigung mit dem vollständigen aktuellen Bestand einschließlich des parallel hinzugekommenen Kandidaten und vollständiger Container-/Receipt-Inventur ausgeführt (`post-cleanup-policy-result.json`): kein globaler Inventurblocker, aber **0 nach der normalen Policy zur Entfernung freigegebene Historien**. Ein Git-Vorgänger, ein früherer PASS oder ein fehlender Containerverweis ersetzt diesen Funktionsnachweis nicht. Die zusätzlichen Nicht-PASS-Kandidaten werden im ausdrücklich beauftragten Ausmusterungsumfang archiviert entfernt; ihre Receipts werden nicht umgeschrieben.

Produktion, Produktdatenbank und festgelegtes Rollback wurden danach erneut geprüft. Produktionscontainer/-image, Datenbankcontainer/-mounts und Rollback-ID bleiben unverändert; die vorhandene vollständige Rollback-PASS-Quittung ist weiterhin gültig. Readiness und Build-Info liefern HTTP 200. Diese Bereinigung hat keinen Anwendungsbuild, kein Deployment und keinen Produktionsneustart gestartet. Der parallel beobachtete neue Kandidatenbuild stammt aus dem anderen laufenden Arbeitsauftrag.

Das gemeinsame zusätzliche Archiv von 24 Images samt SHA-256 und allen 260 geprüften Index-/Konfigurations-/Layerbestandteilen ist in `additional-image-archive-audit.json` gebunden. Für den zusätzlich entfernten alten Diagnosekandidaten wurde sein bereits vorhandenes unveränderliches Archiv frisch nachgeprüft; Nachweise stehen in `old-diagnostic-archive-reverified.json` und `old-diagnostic-removal.json`. Originalreceipts und Einzeloperationen stehen in `preserved-receipts/` und `additional-removal-result.json`. Es wurde weder Force noch Prune verwendet und kein Container eines fremden Arbeitsablaufs entfernt. Der versuchte gesonderte Nur-Lese-Quellinventur-Helfer wurde nach Docker-Verzögerungen beendet; daraus wird kein vollständiger Funktionsvergleich für die PASS-Historien behauptet.

## Einzelbewertung aller ursprünglich 73 Images

| Image-Tag | Erstellt (UTC) | Releasebelege | Bewertung |
| --- | --- | --- | --- |
| `networkis:candidate-6d6fe881f4bd` | 2026-10-20 | PREPARED | Altes geprüftermaßen archiviertes Diagnoseimage nach Bereitschaft des neuen Kandidaten entfernt |
| `networkis:candidate-952edd277e95` | 2026-10-17 | PASS | Für laufende Produktion benötigt |
| `networkis:candidate-c79fead2a497` | 2026-10-17 | PASS, PREPARED | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-ba70268dda42` | 2026-10-16 | PASS, PREPARED | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-c557b3914eac` | 2026-10-16 | PASS | Festgelegtes geprüftes Rollback; benötigt |
| `networkis:candidate-a1c086d28f4b` | 2026-10-16 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-448b47f5d20f` | 2026-10-15 | FAIL, PASS, PREPARED | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-d7ad51da43e8` | 2026-10-14 | FAIL, PASS, PREPARED | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-3bf595a4e58f` | 2026-10-13 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-96954d84b738` | 2026-10-13 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-7a285cebd21b` | 2026-10-13 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-18a5313b3633` | 2026-10-13 | FAIL, PASS, PREPARED | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-44fdae5dc2e1` | 2026-10-12 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-baff4e76f405` | 2026-10-12 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-4bfc55bac818` | 2026-10-12 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-bb493012fb1c` | 2026-10-11 | FAIL, PASS, RUNNING | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-e0cc8540367f` | 2026-10-11 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-e7cc98f3e6fb` | 2026-10-10 | FAIL, PASS, PREPARED | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-264282c9a63a` | 2026-10-10 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-897531633817` | 2026-10-08 | PASS, RUNNING | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-b106f2e968ff` | 2026-10-08 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-efa53ff9fe54` | 2026-10-08 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-bd97b35d951d` | 2026-10-07 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-7de84eb3b678` | 2026-10-07 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-188e8a0234a0` | 2026-10-07 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-27a216bd0002` | 2026-10-07 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-e6ef799ce239` | 2026-10-07 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-cec9d47d49b0` | 2026-10-07 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-b38d800af059` | 2026-10-07 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-252b0f82237a` | 2026-10-07 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-2cc9af52a4a2` | 2026-10-07 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-ee8b5acd70fb` | 2026-10-07 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-6147d73f5a60` | 2026-10-07 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-a2cc56f015d0` | 2026-10-06 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-cd8def2648ee` | 2026-10-06 | RUNNING | Altes RUNNING-Receipt ohne abschließenden Releasebeleg; geschützt |
| `networkis:candidate-613effc89d23` | 2026-10-06 | PASS, PREPARED | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-ee5696e4ffd6` | 2026-10-06 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-f9f5f57ec850` | 2026-10-06 | PASS, PREPARED | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-5600944b7926` | 2026-10-05 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-f1c70fa45bdd` | 2026-10-05 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-fcff78e977a4` | 2026-10-05 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-a7c4241b2ee1` | 2026-10-05 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-587034d2a5ed` | 2026-10-05 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-2613546e95f0` | 2026-10-05 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-2f595348dcbb` | 2026-10-05 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-35c50a21fab1` | 2026-10-03 | FAIL, PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-db6b43fecc86` | 2026-10-03 | FAIL | Archiviert und exakt entfernt |
| `networkis:candidate-4bb663672cb2` | 2026-10-01 | FAIL, PASS, PREPARED | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-9b7d7b543a9a` | 2026-09-30 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-295ec575b38a` | 2026-09-30 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-5768cd695858` | 2026-09-30 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-50d6e6d6879d` | 2026-09-30 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-d88bb2fea9aa` | 2026-09-30 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-e440fa4ebfdc` | 2026-09-30 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-472bab57f9fc` | 2026-09-30 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-ff63f6cd6609` | 2026-09-30 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-e08c72876ed3` | 2026-09-30 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-eb88afa8ff2b` | 2026-09-30 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-79ccac258b5c` | 2026-09-30 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-4b196ede0006` | 2026-09-30 | PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-e0657ff2269e` | 2026-09-30 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-4fa2ee7f0d82` | 2026-09-30 | FAIL, PREPARED | Archiviert und exakt entfernt |
| `networkis:candidate-02f73c791176` | 2026-09-30 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-4cd07c194bc7` | 2026-09-30 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-3d66aa63ef59` | 2026-09-29 | PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:production-20260929` | 2026-09-29 | ungeklärt | Releaseherkunft trotz erweiterter Suche ungeklärt; geschützt |
| `networkis:candidate-fe5d080681c8` | 2026-09-29 | ungeklärt | Releaseherkunft trotz erweiterter Suche ungeklärt; geschützt |
| `networkis:candidate-cd9d10760fb8` | 2026-09-28 | FAIL, PASS | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-edc1cf88ca84` | 2026-09-28 | PASS, PREPARED | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-a91ed2172e10` | 2026-09-28 | PASS, PREPARED | Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt |
| `networkis:candidate-9d30399e1ea1` | 2026-09-27 | ungeklärt | Releaseherkunft trotz erweiterter Suche ungeklärt; geschützt |
| `networkis:candidate-b882e963c160` | 2026-09-27 | ungeklärt | Releaseherkunft trotz erweiterter Suche ungeklärt; geschützt |
| `networkis:candidate-03f8e6157514` | 2026-09-27 | ungeklärt | Releaseherkunft trotz erweiterter Suche ungeklärt; geschützt |

## Während der Prüfung hinzugekommene, geschützte Arbeitsstände

- `networkis:candidate-6d41919070e2` / `sha256:189ca2794ddf3f6b6ae320f830f2dd9de8096c9707725e71cf2dabaa4fcfb639`; im anderen Arbeitsablauf erzeugt, nicht bereinigt.

Die unveränderlichen vollständigen IDs, Quellidentitäten, Originalbelegpfade, Beleg-Hashes und genauen Policygründe je Image stehen in `image-roles-and-retention.json`.
