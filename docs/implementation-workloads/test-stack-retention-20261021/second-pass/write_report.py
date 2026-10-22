"""Readable per-image audit, with actual need kept separate from protection."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
roles = json.loads((OUT / 'image-roles-and-retention.json').read_text())['roles']
plan = json.loads((OUT / 'additional-cleanup-plan.json').read_text())
result = json.loads((OUT / 'additional-removal-result.json').read_text())
after = json.loads((OUT / 'inventory-after-extra.json').read_text())
extra = json.loads((OUT / 'old-diagnostic-removal.json').read_text())
health = json.loads((OUT / 'production-and-rollback-after.json').read_text())
assert result['status'] == 'COMPLETED' and health['status'] == 'PASSED'
targets = {row['id'] for row in plan['images']} | {extra['image']}
initial_ids = {row['image'] for row in roles}
new = [row for row in after['images'] if row['id'] not in initial_ids]
texts = {
    'PRODUCTION': 'Für laufende Produktion benötigt',
    'REQUIRED_VERIFIED_ROLLBACK': 'Festgelegtes geprüftes Rollback; benötigt',
    'ADDITIONAL_UNUSED_NON_PASS_RETIREMENT': 'Archiviert und exakt entfernt',
    'HISTORICAL_PASS_NO_RUNTIME_REFERENCE_DELIVERY_AUDIT_MISSING': 'Historischer PASS; kein Laufzeitbedarf belegt, vollständiger Funktions-Übernahmenachweis fehlt',
    'LATEST_OLD_DIAGNOSTIC_ALREADY_ARCHIVED_STACK_RETIRED': 'Altes geprüftermaßen archiviertes Diagnoseimage nach Bereitschaft des neuen Kandidaten entfernt',
    'HISTORICAL_INCOMPLETE_RECEIPT_NOT_PROVEN_TERMINAL': 'Altes RUNNING-Receipt ohne abschließenden Releasebeleg; geschützt',
    'RELEASE_STATUS_NOT_RESOLVED': 'Releaseherkunft trotz erweiterter Suche ungeklärt; geschützt',
}
lines = ['# Prüfung der verbliebenen NIS-Images, 21.10.2026', '',
    'Die 73 Images des ersten Abschlusses waren eine vorläufige Schutzmenge, kein Nachweis, dass 73 Images gebraucht werden. '
    'Die erste Inventur hatte Receipts in älteren Git-Worktrees und Dokumentationsordnern nicht mit erfasst. '
    'Die erweiterte Prüfung liest 494 ursprüngliche Receipt-Dateien aus dem kanonischen Projekt, seinen Dokumentationsordnern und allen drei registrierten historischen Worktrees; dabei traten keine Lesefehler auf.', '',
    f'Zusätzlich wurden **{len(targets)} ungenutzte PREPARED-/FAIL-Kandidaten** vollständig archiviert, verifiziert und einzeln mit `docker image rm --no-prune` entfernt. '
    f'Der frische Endbestand umfasst **{len(after["images"])} NIS-Images**. '
    f'Während dieser Prüfung hinzugekommene Images aus einem anderen aktiven Arbeitsablauf: **{len(new)}**. Diese gehören nicht zum alten Bereinigungsumfang und bleiben erhalten.', '',
    '| Gruppe im ursprünglichen Bestand | Anzahl | Bewertung |',
    '| --- | ---: | --- |',
    '| Laufende Produktion | 1 | Unverändert erhalten |',
    '| Festgelegtes vollständiges PASS-Rollback | 1 | Unverändert erhalten |',
    f'| Weitere eindeutig ungenutzte Entwicklungs-/Fehlkandidaten | {len(targets)} | Geprüft archiviert und entfernt |',
    '| Weitere historische Images mit vollständigem PASS | 40 | Kein aktueller Containerverweis; Aufbewahrungsnachweis noch offen |',
    '| Alte nicht abschließend zugeordnete Stände | 6 | Fünf ohne eindeutigen Releasebeleg, eines mit historischem RUNNING-Receipt |', '',
    'Für den laufenden Betrieb sind aus dem alten Bestand nur Produktion `3792d2e086e4` und das festgelegte Rückfallimage `09d1f624dfdd` ausdrücklich erforderlich. '
    'Die 40 anderen erfolgreichen Historien werden nicht als 40 benötigte Rollbacks ausgegeben. 35 sind älter als sieben Tage, fünf liegen noch innerhalb der Mindestaufbewahrung. '
    'Für keines dieser 40 Images liegt bislang der vom bestehenden `scripts/release_storage.py` verlangte vollständige Nachweis `SUPERSEDED_DELIVERED` mit `FULL_CANDIDATE_FEATURES` gegenüber der laufenden Produktion vor. '
    'Die unveränderte Policy wurde nach der Bereinigung mit dem vollständigen aktuellen Bestand einschließlich des parallel hinzugekommenen Kandidaten und vollständiger Container-/Receipt-Inventur ausgeführt (`post-cleanup-policy-result.json`): kein globaler Inventurblocker, aber **0 nach der normalen Policy zur Entfernung freigegebene Historien**. '
    'Ein Git-Vorgänger, ein früherer PASS oder ein fehlender Containerverweis ersetzt diesen Funktionsnachweis nicht. Die zusätzlichen Nicht-PASS-Kandidaten werden im ausdrücklich beauftragten Ausmusterungsumfang archiviert entfernt; ihre Receipts werden nicht umgeschrieben.', '',
    'Produktion, Produktdatenbank und festgelegtes Rollback wurden danach erneut geprüft. Produktionscontainer/-image, Datenbankcontainer/-mounts und Rollback-ID bleiben unverändert; die vorhandene vollständige Rollback-PASS-Quittung ist weiterhin gültig. Readiness und Build-Info liefern HTTP 200. '
    'Diese Bereinigung hat keinen Anwendungsbuild, kein Deployment und keinen Produktionsneustart gestartet. Der parallel beobachtete neue Kandidatenbuild stammt aus dem anderen laufenden Arbeitsauftrag.', '',
    'Das gemeinsame zusätzliche Archiv von 24 Images samt SHA-256 und allen 260 geprüften Index-/Konfigurations-/Layerbestandteilen ist in `additional-image-archive-audit.json` gebunden. '
    'Für den zusätzlich entfernten alten Diagnosekandidaten wurde sein bereits vorhandenes unveränderliches Archiv frisch nachgeprüft; Nachweise stehen in `old-diagnostic-archive-reverified.json` und `old-diagnostic-removal.json`. '
    'Originalreceipts und Einzeloperationen stehen in `preserved-receipts/` und `additional-removal-result.json`. '
    'Es wurde weder Force noch Prune verwendet und kein Container eines fremden Arbeitsablaufs entfernt. '
    'Der versuchte gesonderte Nur-Lese-Quellinventur-Helfer wurde nach Docker-Verzögerungen beendet; daraus wird kein vollständiger Funktionsvergleich für die PASS-Historien behauptet.', '',
    '## Einzelbewertung aller ursprünglich 73 Images', '',
    '| Image-Tag | Erstellt (UTC) | Releasebelege | Bewertung |',
    '| --- | --- | --- | --- |']
for row in sorted(roles, key=lambda r: r['created'], reverse=True):
    lines.append('| `' + row['tag'] + '` | ' + row['created'][:10] + ' | '
                 + (', '.join(row['resolved_statuses']) or 'ungeklärt') + ' | ' + texts[row['role']] + ' |')
if new:
    lines += ['', '## Während der Prüfung hinzugekommene, geschützte Arbeitsstände', '']
    for row in new:
        lines.append('- `' + row['tags'][0] + '` / `' + row['id'] + '`; im anderen Arbeitsablauf erzeugt, nicht bereinigt.')
lines += ['', 'Die unveränderlichen vollständigen IDs, Quellidentitäten, Originalbelegpfade, Beleg-Hashes und genauen Policygründe je Image stehen in `image-roles-and-retention.json`.']
(OUT / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
evidence = []
for name in ('inventory-before.json', 'resolved-images.json', 'classification-summary.json',
             'image-roles-and-retention.json', 'post-cleanup-policy-result.json', 'receipt-inventory-completeness.json',
             'additional-cleanup-plan.json', 'additional-image-archive-audit.json',
             'additional-removal-result.json', 'old-diagnostic-archive-reverified.json', 'old-diagnostic-removal.json',
             'inventory-after-extra.json', 'production-and-rollback-after.json', 'REPORT.md'):
    path = OUT / name
    evidence.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT / 'completion.json').write_text(json.dumps({'status': 'COMPLETED', 'scope': 'Classify every initial image, remove the additionally proven unused candidates, preserve protected/uncertain images and active work.',
    'removed': len(targets), 'remaining': len(after['images']), 'new_during_audit': len(new),
    'historical_pass_not_claimed_operationally_required': 40,
    'missing_feature_delivery_audits_disclosed': True, 'evidence': evidence}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'COMPLETED', 'removed': len(targets), 'remaining': len(after['images']), 'new': len(new)}))
