"""Audit-first release image retention; planning only, never Docker deletion.

Docker snapshots and feature dispositions must be supplied by a human-reviewed
audit. A tag, age or successful gate alone never proves features were delivered.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import os
import math
from pathlib import Path
import re
import shutil

REQUIRED_CHECKS = {'typecheck', 'frontend-tests', 'backend-tests', 'browser-e2e', 'small-http', 'large-http'}
RETENTION_SECONDS = 7 * 24 * 60 * 60
MAX_NETWORKIS_IMAGES = 100
CACHE_POLICY = {'scope': 'dedicated NIS buildx builder only', 'max_used_space': '20GB',
                'min_free_space': '10GB', 'keep_duration': '168h', 'automatic_cleanup': False}


def disk_readiness(paths, *, minimum_bytes=20 * 1024**3, disk_usage=shutil.disk_usage):
    if minimum_bytes < 20 * 1024**3:
        raise ValueError('Release builds require at least 20 GiB free; the guard cannot be lowered.')
    rows = []
    for path in paths:
        existing = Path(path).resolve()
        while not existing.exists() and existing != existing.parent:
            existing = existing.parent
        free = disk_usage(existing).free
        rows.append({'path': str(path), 'free_bytes': free, 'minimum_bytes': minimum_bytes,
                     'ready': free >= minimum_bytes})
    return {'ready': all(row['ready'] for row in rows), 'volumes': rows}


def default_storage_paths(root):
    # Docker Desktop commonly stores its VHDX on the Windows system volume,
    # even when the source checkout is on another drive. Explicit custom paths
    # add a check; they never remove the system-volume safety check.
    paths = [root]
    if os.name == 'nt':
        paths.append(Path(os.environ.get('SystemDrive', 'C:') + '/'))
    return paths


def image_budget(image_ids):
    count = len(set(image_ids))
    return {'ready': count < MAX_NETWORKIS_IMAGES, 'existing_image_count': count,
            'maximum_image_count': MAX_NETWORKIS_IMAGES,
            'action': 'Review feature audit before scoped cleanup; never prune automatically'}


def immutable_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r'sha256:[0-9a-f]{64}', value))


def epoch(value):
    return type(value) in (int, float) and 0 <= value <= 253402300799 and math.isfinite(value)


def evidence_json(reference):
    if not isinstance(reference, dict):
        raise ValueError('Evidence must be a path/hash object')
    path = Path(reference['path'])
    digest = reference['sha256']
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Invalid evidence hash')
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('Evidence missing or changed')
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError('Evidence document must be an object')
    return data


def container_inventory(snapshot, now):
    try:
        ids = snapshot['container_image_ids']
        if snapshot.get('container_inventory_complete') is not True or not isinstance(ids, list) or not all(immutable_id(i) for i in ids):
            raise ValueError('Explicit complete container inventory required')
        evidence = evidence_json(snapshot['container_inventory_evidence'])
        captured = evidence.get('captured_epoch')
        containers = evidence.get('containers')
        if (evidence.get('schema') != 'nis-container-inventory-v1' or
                not isinstance(evidence.get('engine_id'), str) or not evidence['engine_id'].strip() or
                not epoch(captured) or not epoch(now) or not 0 <= now - captured <= 300 or
                not isinstance(containers, list)):
            raise ValueError('Container inventory provenance/freshness invalid')
        for item in containers:
            if (not isinstance(item, dict) or not isinstance(item.get('name'), str) or not item['name'].strip()
                    or not isinstance(item.get('container_id'), str) or not re.fullmatch('[0-9a-f]{64}', item['container_id'])
                    or not immutable_id(item.get('image_id'))):
                raise ValueError('Invalid container record')
        if set(ids) != {c['image_id'] for c in containers} or snapshot.get('production_image_id') not in ids:
            raise ValueError('Inventory must bind all containers including production')
        return set(ids), None
    except (KeyError, TypeError, OSError, ValueError):
        return set(), 'CONTAINER_INVENTORY_UNVERIFIED'


def audit_evidence_valid(image, production):
    try:
        path = Path(image['audit_evidence_path'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != image['audit_evidence_sha256']:
            return False
        audit = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(audit, dict) or not (audit.get('accepted') is True and audit.get('image_id') == image.get('image_id')
                and audit.get('disposition') == 'SUPERSEDED_DELIVERED' and audit.get('delivered_to_image_id') == production):
            return False
        refs = audit.get('feature_delivery_evidence')
        if not isinstance(refs, list) or len(refs) != 2 or not all(isinstance(ref, dict) for ref in refs):
            return False
        if {ref.get('role') for ref in refs} != {'running_manifest', 'delivery_comparison'}:
            return False
        documents = {ref['role']: evidence_json(ref) for ref in refs}
        running, comparison = documents['running_manifest'], documents['delivery_comparison']
        source = running.get('source_sha256')
        features = comparison.get('feature_ids')
        return (running.get('image_id') == production and immutable_id(production)
                and isinstance(source, str) and bool(re.fullmatch('[0-9a-f]{64}', source))
                and comparison.get('candidate_image_id') == image.get('image_id')
                and comparison.get('delivered_to_image_id') == production
                and comparison.get('delivered_source_sha256') == source
                and isinstance(comparison.get('candidate_source_sha256'), str)
                and bool(re.fullmatch('[0-9a-f]{64}', comparison['candidate_source_sha256']))
                and comparison.get('coverage') == 'FULL_CANDIDATE_FEATURES'
                and isinstance(features, list) and bool(features)
                and all(isinstance(feature, str) and feature.strip() for feature in features))
    except (KeyError, TypeError, OSError, ValueError):
        return False


def complete_pass(receipt):
    if not isinstance(receipt, dict) or receipt.get('status') != 'PASS':
        return False
    if 'development_only' in receipt and receipt['development_only'] is not False:
        return False
    release, rows = receipt.get('release'), receipt.get('checks')
    if not isinstance(release, dict) or not isinstance(rows, list):
        return False
    checks = set()
    for row in rows:
        if not isinstance(row, dict):
            return False
        name, code = row.get('name'), row.get('exit_code')
        if (not isinstance(name, str) or not re.fullmatch('[A-Za-z0-9_.-]+', name)
                or name in checks or type(code) is not int or code != 0):
            return False
        checks.add(name)
    source = receipt.get('initial_source_sha256')
    verification = receipt.get('verification_sha256')
    if (not isinstance(source, str) or not re.fullmatch('[0-9a-f]{64}', source)
            or not isinstance(verification, str) or not re.fullmatch('[0-9a-f]{64}', verification)
            or source != release.get('source_sha256') or not REQUIRED_CHECKS <= checks):
        return False
    # Old receipts predating commit binding remain supported. Every recorded
    # commit must nevertheless be a full Git ID, and paired identities must agree.
    commits = [obj[key] for obj, key in ((receipt, 'initial_commit_id'), (release, 'commit_id')) if key in obj]
    if any(not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', commit) for commit in commits):
        return False
    return len(set(commits)) <= 1


def retention_plan(snapshot, *, now):
    """Keep by default; propose only aged, audited, superseded inactive IDs.

    Snapshot binds the running production ID, a verified rollback PASS ID, every
    container's image, all historical receipts, and immutable audited image IDs.
    Missing/incomplete inventories block the entire plan rather than guessing.
    """
    malformed = []
    if not isinstance(snapshot, dict):
        snapshot = {}
        malformed.append('SNAPSHOT_MALFORMED')
    images = snapshot.get('images')
    receipts = snapshot.get('receipts')
    if not isinstance(images, list):
        images = []
        malformed.append('IMAGE_INVENTORY_MALFORMED')
    if not isinstance(receipts, list):
        receipts = []
        malformed.append('RECEIPT_INVENTORY_MALFORMED')
    if any(not isinstance(image, dict) or not immutable_id(image.get('image_id')) for image in images):
        malformed.append('IMAGE_INVENTORY_MALFORMED')
    if any(not isinstance(receipt, dict) or not immutable_id(receipt.get('image_id'))
           or not isinstance(receipt.get('status'), str) for receipt in receipts):
        malformed.append('RECEIPT_INVENTORY_MALFORMED')
    receipts = [receipt for receipt in receipts if isinstance(receipt, dict)]
    production = snapshot.get('production_image_id')
    rollback = snapshot.get('rollback_image_id')
    blockers = list(dict.fromkeys(malformed))
    if not epoch(now):
        blockers.append('AUDIT_TIMESTAMP_INVALID')
    if snapshot.get('inventory_complete') is not True:
        blockers.append('INVENTORY_INCOMPLETE')
    if not immutable_id(production) or not immutable_id(rollback):
        blockers.append('PRODUCTION_OR_ROLLBACK_UNVERIFIED')
    if not any(r.get('image_id') == rollback and complete_pass(r) for r in receipts):
        blockers.append('ROLLBACK_PASS_UNVERIFIED')
    if snapshot.get('receipt_inventory_complete') is not True:
        blockers.append('RECEIPT_INVENTORY_INCOMPLETE')
    container_ids, container_error = container_inventory(snapshot, now)
    if container_error:
        blockers.append(container_error)
    result = {'schema_version': 1, 'mode': 'PLAN_ONLY', 'blockers': blockers,
              'protected': [], 'eligible': [], 'cache_policy': CACHE_POLICY}
    for image in images:
        if not isinstance(image, dict):
            result['protected'].append({'image_id': None, 'reasons': ['IMAGE_ENTRY_MALFORMED', *blockers]})
            continue
        identity = image.get('image_id')
        if not isinstance(identity, str):
            identity = None
        reasons = []
        related = [r for r in receipts if r.get('image_id') == identity]
        if not isinstance(identity, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', identity):
            reasons.append('IMMUTABLE_ID_UNVERIFIED')
        if identity == production:
            reasons.append('PRODUCTION')
        if identity == rollback:
            reasons.append('ROLLBACK_PASS')
        if identity in container_ids:
            reasons.append('CONTAINER_REFERENCED')
        if not related or any(not isinstance(r.get('status'), str) or r['status'] not in {'PASS', 'FAIL'} for r in related):
            reasons.append('UNCLASSIFIED_OR_ACTIVE_RECEIPT')
        if any(r.get('status') == 'PASS' and not complete_pass(r) for r in related):
            reasons.append('INCOMPLETE_PASS_RECEIPT')
        if image.get('audit_disposition') != 'SUPERSEDED_DELIVERED':
            reasons.append('UNDELIVERED_OR_UNCLASSIFIED_FEATURES')
        if not audit_evidence_valid(image, production):
            reasons.append('AUDIT_EVIDENCE_MISSING_OR_CHANGED')
        created = image.get('created_epoch')
        if not epoch(created) or not epoch(now) or created > now or now - created < RETENTION_SECONDS:
            reasons.append('RETENTION_WINDOW')
        reasons.extend(blockers)
        entry = {'image_id': identity, 'reasons': reasons}
        result['protected' if reasons else 'eligible'].append(entry)
    result['status'] = 'BLOCKED' if blockers else 'REVIEW_REQUIRED'
    return result


def cache_cleanup_proposal(builder):
    """A reviewed command for an existing dedicated builder; never executes it."""
    if not re.fullmatch(r'nis-[a-z0-9][a-z0-9_.-]*', builder):
        raise ValueError('An explicitly owned nis-* dedicated builder is required; default/shared builders are forbidden.')
    return ['docker', 'buildx', 'prune', '--builder', builder, '--filter', 'until=168h',
            '--max-used-space', '20GB', '--min-free-space', '10GB']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--now', required=True, type=float, help='Audit timestamp (Unix seconds)')
    parser.add_argument('--dedicated-builder', help='Emit a scoped cache proposal; does not execute it')
    args = parser.parse_args()
    plan = retention_plan(json.loads(args.snapshot.read_text(encoding='utf-8-sig')), now=args.now)
    if args.dedicated_builder:
        plan['cache_cleanup_proposal'] = cache_cleanup_proposal(args.dedicated_builder)
        plan['cache_prerequisites'] = ['Verify builder ownership and no active builds',
                                     'Verify installed buildx supports size flags',
                                     'Review audit before executing; shared/default cache untouched']
    print(json.dumps(plan, indent=2))


if __name__ == '__main__':
    main()
