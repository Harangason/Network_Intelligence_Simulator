"""Bind completed cleanup and tested host changes to immutable evidence."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


work_path = OUT / 'workload.json'
work = json.loads(work_path.read_text())
removed = json.loads((OUT / 'removal-result.json').read_text())
live = json.loads((OUT / 'live-tooling-verification.json').read_text())
protected = json.loads((OUT / 'protected-identity-and-health.json').read_text())
assert removed['status'] == 'COMPLETED' and removed['production_and_all_protected_images_preserved']
assert live['status'] == protected['status'] == 'PASSED'
test_log = (OUT / 'release-tool-tests.log').read_text(encoding='utf-8-sig')
assert 'Ran 38 tests' in test_log and test_log.rstrip().endswith('OK')
changed, after, diffs = [], [], []
for name in work['revision_before']:
    source = ROOT / name
    old = OUT / 'before' / name
    before_bytes = old.read_bytes() if old.exists() else b''
    after_bytes = source.read_bytes() if source.exists() else b''
    if before_bytes == after_bytes:
        continue
    changed.append(name)
    target = OUT / 'after' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    after.append(ref(target))
    diffs.extend(difflib.unified_diff(before_bytes.decode('utf-8').splitlines(keepends=True),
                                    after_bytes.decode('utf-8').splitlines(keepends=True),
                                    fromfile='a/' + name, tofile='b/' + name))
diff = OUT / 'owned-changes.diff'
diff.write_text(''.join(diffs), encoding='utf-8')
work['files_changed'] = changed
work['after'] = after
work['diff'] = [ref(diff)]
work['outcomes'] = {
    'safe_cleanup': {'status': 'PASSED', 'evidence': [ref(OUT / name) for name in (
        'cleanup-plan.json', 'image-archive-audit.json', 'stack-backup-audit.json', 'removal-result.json')]},
    'reuse_and_bounded_stacks': {'status': 'PASSED', 'evidence': [ref(OUT / 'release-tool-tests.log'), ref(OUT / 'live-tooling-verification.json'), ref(diff)]},
    'production_and_rollback_preserved': {'status': 'PASSED', 'evidence': [ref(OUT / 'protected-identity-and-health.json'), ref(OUT / 'inventory-after.json')]},
}
work['validations'] = {
    'release_tool_regressions': {'status': 'PASSED', 'evidence': [ref(OUT / 'release-tool-tests.log'), ref(OUT / 'live-tooling-verification.json')]},
    'cleanup_archive_and_identity_checks': {'status': 'PASSED', 'evidence': [ref(OUT / 'image-archive-audit.json'), ref(OUT / 'stack-backup-audit.json'), ref(OUT / 'removal-result.json')]},
    'production_health': {'status': 'PASSED', 'evidence': [ref(OUT / 'protected-identity-and-health.json')]},
}
work['status'] = 'COMPLETED'
work['completion_status'] = '28 obsolete stopped containers, 13 networks, 13 archived volumes and 26 archived unused PREPARED images removed exactly. 73 protected images/tags preserved. 38 host release-tool regressions plus live read-only reuse/rejection and production health passed. No application build, product deployment, production restart or full app release gate performed.'
work['tests'] = {'count': 38, 'failures': 0, 'scope': 'Host release tooling; no SQL or application E2E claims'}
work['remaining_findings'] = []
work_path.write_text(json.dumps(work, indent=2) + '\n', encoding='utf-8')
report = '''# Sichere Teststack- und Kandidatenbereinigung, 21.10.2026

28 alte gestoppte Testcontainer, 13 zugehörige Netzwerke und 13 zuvor gesicherte
Laufzeitvolumes wurden entfernt. 26 alte ausschließlich PREPARED-belegte
Kandidaten wurden vollständig archiviert und danach exakt mit --no-prune
entfernt. 99 NIS-Images wurden dadurch auf 73 reduziert; nur der aktuelle
Teststack 6d6fe881f4bd bleibt erhalten. Keine Force-/Prune-Bereinigung.

Die Sicherung umfasst ein gemeinsames 16.870.832.640-Byte-Imagearchiv auf F,
270 vollständig gehashte Index-/Konfigurations-/Layerbestandteile,
13 Laufzeitvolume-Archive, 28 Containerlogs und die unveränderten Receipts.
SHA-256-Nachweise, genaue Einzeloperationen und Wiederherstellungshinweise
stehen in image-archive-audit.json, stack-backup-audit.json,
removal-result.json und RESTORE.md. Bereits vor der Bereinigung verlorene
tmpfs-Datenbankinhalte werden nicht als gesichert behauptet; bestehende frühere
Dumps und Projektexporte bleiben erhalten.

Produktion bleibt auf Image 3792d2e086e4, Rollback auf 09d1f624dfdd mit geprüftem
vollständigem PASS. Produktionscontainer, Produktdatenbank und ihre Speicher
bleiben unverändert und gesund. Alle 73 geschützten Images einschließlich aller
PASS-Images, ungeklärten Historien und des aktuellen Arbeitskandidaten samt Tags
sind nach der Bereinigung erneut geprüft. Keine fremden Projektobjekte entfernt.

Die kanonischen Hostskripte wählen auch PREPARED-Images für exakt dieselbe
Anwendungsquelle/Git-Revision wieder aus. Direkte Gates und Lieferungen halten
eine gemeinsame Betriebssystemsperre. Wiederholte Vorbereitung nutzt den
gesunden identischen Teststack; abweichende oder alte erhaltene Stacks und
verwaiste Ressourcen verhindern einen zweiten dauerhaften Stack vor dem Build.
--no-reuse erneuert Tests, erzwingt keinen Image-Neubau. Fehlgeschlagene
Bereinigung erzeugt FAIL und sperrt weitere Gates bis zur Klärung.
AGENTS.md und WIZARD_RELEASE_GATE.md halten die Vorgaben zusätzlich fest.

38 Tests des Releasewerkzeugs bestanden, einschließlich echter
Prozesskonkurrenz, Freigabe der Sperre nach Fehler, Wiederverwendung, fremder
Datenbank-/Image-/Quell-/AI-Konfiguration und Sperre nach Bereinigungsfehlern.
Der echte aktuelle Stack wurde anschließend rein lesend als wiederverwendbar
bestätigt; eine abweichende Quelle wird vor einem Build blockiert. Die
Containerliste blieb dabei unverändert. Produktions-Readiness und Build-Info
lieferten HTTP 200. Syntaxprüfung und Diffprüfung bestanden.

Es wurden ausschließlich Hostwerkzeuge, Tests und Dokumentation geändert.
Diese Änderungen sind lokal unmittelbar wirksam und gehören nicht zur
Anwendungsimage-Identität. Kein neuer Build, kein Produktionsneustart, keine
Anwendungsbereitstellung und kein vollständiger App-Releasegate-Lauf wurden
ausgeführt oder behauptet. Bestehende andere Arbeitsänderungen bleiben erhalten.
'''
(OUT / 'REPORT.md').write_text(report, encoding='utf-8')
print(json.dumps({'status': work['status'], 'changed_files': changed, 'tests': 38}))
