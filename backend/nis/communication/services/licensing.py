"""Scoped NIS clearance policy, separate from copyright in referenced documents.

Only an operator review command can approve evidence. HTTP requests can submit
pending references, never set approvals or assert that a license is authentic.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from threading import RLock
import uuid

POLICY_REVISION = 'NIS_TECHNOLOGY_CLEARANCE_2026_10_03'
_LOCK = RLock()
_NMEA = {'issuer': 'National Marine Electronics Association',
         'evidence_url': 'https://www.nmea.org/nmea-2000.html',
         'reason': 'NMEA beschreibt Lizenz- und Zertifizierungsanforderungen für entsprechende Produkte. NIS verlangt vorsorglich eine geprüfte Freigabe des konkreten Simulations-/Implementierungsumfangs; dies ist keine Aussage, dass jede abstrakte Simulation gesetzlich lizenzpflichtig wäre.'}
_MIPI = {'issuer': 'MIPI Alliance',
         'evidence_url': 'https://www.mipi.org/resources/frequently-asked-questions',
         'reason': 'MIPI beschreibt Mitgliedschafts-/Lizenzrechte für Implementierungen von CSI-/DSI-Spezifikationen. Eine öffentlich sichtbare Produktbeschreibung gewährt diese Rechte nicht. NIS verlangt eine geprüfte Freigabe des tatsächlich verwendeten Umfangs. I3C Basic wird ausdrücklich nicht über diese Regel gesperrt.'}
REQUIREMENTS = {'nmea2000': _NMEA, 'nmea0183': {**_NMEA, 'evidence_url': 'https://www.nmea.org/standards.html'},
                'mipi_csi2': _MIPI, 'mipi_dsi': _MIPI}


def licensing_policy(technology_id: str) -> dict:
    requirement = REQUIREMENTS.get(technology_id)
    return {'revision': POLICY_REVISION, 'clearance_required': bool(requirement),
            'policy_basis': 'NIS_PRECAUTIONARY_SCOPED_CLEARANCE' if requirement else 'NO_ESTABLISHED_NIS_LICENSE_GATE',
            **(requirement or {}),
            'scope': 'NIS_SIMULATION',
            'publication_rights_separate': True}


def declared_technology_ids(value, registry) -> set[str]:
    """Only actual declared identities; no inference from industries or names."""
    result = set()
    def collect(item, parent=''):
        if isinstance(item, dict):
            for key, child in item.items():
                if (key in ('technology', 'technology_id', 'bus_type', 'bus', 'protocol')
                        or key == 'type' and parent in ('buses', 'networks')) and isinstance(child, str) and child:
                    result.add(registry.normalize_id(child))
                elif key in ('technology_stack', 'default_stack') and isinstance(child, list):
                    result.update(registry.normalize_id(part) for part in child if isinstance(part, str))
                collect(child, key if key in ('buses', 'networks') else parent)
        elif isinstance(item, list):
            for child in item:
                collect(child, parent)
    collect(value)
    return result


def _root() -> Path:
    from backend.nis.infrastructure.paths import DATA_ROOT
    return DATA_ROOT / 'technology-license-evidence'


@contextmanager
def _ledger(project_id: str, *, write=False):
    # Project IDs never become filesystem paths. The recorded ID is checked
    # as well, so a directory name cannot silently switch evidence ownership.
    root = _root()
    path = root / (hashlib.sha256(project_id.encode()).hexdigest() + '.json')
    with _LOCK:
        if not write and not path.exists():
            yield {'project_id': project_id, 'records': [], 'events': []}
            return
        root.mkdir(parents=True, exist_ok=True)
        with (root / 'ledger.lock').open('a+b') as lock:
            if lock.seek(0, 2) == 0:
                lock.write(b'0'); lock.flush()
            lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
                    'project_id': project_id, 'records': [], 'events': []}
                if data.get('project_id') != project_id:
                    raise ValueError('Lizenznachweis gehört zu einem anderen Projekt.')
                yield data
                if write:
                    temporary = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
                    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                    temporary.replace(path)
            finally:
                lock.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError(f'{field}: Text mit 1 bis 500 Zeichen erforderlich.')
    return value.strip()


def submit_evidence(project_id: str, technology_id: str, payload: dict) -> dict:
    if technology_id not in REQUIREMENTS:
        raise ValueError('Für diese Technik ist kein Lizenzfreigabe-Verfahren registriert.')
    if set(payload) - {'technology', 'issuer', 'reference', 'scope_description', 'expires_on'}:
        raise ValueError('Unzulässige Felder: Eine Einreichung kann keine Lizenzfreigabe setzen.')
    expiry = payload.get('expires_on') or None
    if expiry is not None:
        date.fromisoformat(expiry)
    row = {'id': uuid.uuid4().hex, 'technology': technology_id,
           'issuer': _text(payload.get('issuer'), 'Lizenzgeber'),
           'reference': _text(payload.get('reference'), 'Nachweisreferenz'),
           'scope_description': _text(payload.get('scope_description'), 'Nutzungsumfang'),
           'expires_on': expiry, 'status': 'PENDING', 'policy_revision': POLICY_REVISION,
           'submitted_at': datetime.now(timezone.utc).isoformat()}
    with _ledger(project_id, write=True) as data:
        data['records'].append(row)
        data['events'].append({'action': 'SUBMITTED', 'record_id': row['id'], 'at': row['submitted_at']})
    return row


def review_evidence(project_id: str, record_id: str, *, reviewer: str, evidence: Path | None,
                    approve: bool, rationale: str) -> dict:
    reviewer = _text(reviewer, 'Prüfer')
    rationale = _text(rationale, 'Prüfbegründung')
    evidence_hash = hashlib.sha256(evidence.read_bytes()).hexdigest() if evidence else None
    if approve and not evidence_hash:
        raise ValueError('Freigabe benötigt einen tatsächlich geprüften Nachweis.')
    with _ledger(project_id, write=True) as data:
        row = next((row for row in data['records'] if row['id'] == record_id), None)
        if row is None:
            raise ValueError('Nachweis nicht gefunden.')
        if approve and row.get('expires_on') and date.fromisoformat(row['expires_on']) < date.today():
            raise ValueError('Abgelaufener Nachweis kann nicht freigegeben werden.')
        row.update(status='APPROVED' if approve else 'REVOKED', reviewed_by=reviewer,
                   reviewed_at=datetime.now(timezone.utc).isoformat(),
                   evidence_sha256=evidence_hash, review_rationale=rationale,
                   policy_revision=POLICY_REVISION, verified_scope='NIS_SIMULATION' if approve else None)
        data['events'].append({'action': row['status'], 'record_id': record_id,
                               'by': reviewer, 'at': row['reviewed_at'], 'rationale': rationale,
                               'evidence_sha256': evidence_hash})
        return dict(row)


def license_states(project_id: str, profiles: list[dict], *, today: date | None = None) -> dict:
    today = today or date.today()
    with _ledger(project_id) as ledger:
        records = list(ledger['records'])
    result = {}
    for profile in profiles:
        technology_id = profile['id']
        policy = profile.get('licensing_policy') or licensing_policy(technology_id)
        rows = [row for row in records if row.get('technology') == technology_id]
        approved = [row for row in rows if row.get('status') == 'APPROVED'
                    and row.get('policy_revision') == policy['revision']
                    and row.get('verified_scope') == 'NIS_SIMULATION'
                    and row.get('reviewed_by') and row.get('evidence_sha256')
                    and (not row.get('expires_on') or date.fromisoformat(row['expires_on']) >= today)]
        required = policy['clearance_required']
        status = 'APPROVED' if approved else 'PENDING' if any(row['status'] == 'PENDING' for row in rows) else 'MISSING'
        result[technology_id] = {**policy, 'status': status if required else 'NOT_REQUIRED_BY_NIS_POLICY',
                                'blocked': required and not bool(approved),
                                'records': [{key: row.get(key) for key in ('id', 'issuer', 'reference', 'scope_description',
                                           'expires_on', 'status', 'reviewed_at', 'review_rationale')} for row in rows]}
    return result


def assert_technology_clearance(project_id: str, technology_ids, registry) -> None:
    profiles = [registry.profile(value) for value in sorted(set(technology_ids)) if value in REQUIREMENTS]
    if not profiles:
        return
    states = license_states(project_id, profiles)
    blocked = [key for key, row in states.items() if row['blocked']]
    if blocked:
        raise ValueError('TECHNOLOGY_LICENSE_REQUIRED: Ausführung gesperrt ohne geprüfte projektbezogene Freigabe: '
                         + ', '.join(blocked) + '. Nachweis im Quellenverzeichnis einreichen.')
