"""Bibliographic view of the canonical profiles; never serves source contents."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit, unquote


def canonical_source_url(value: str) -> str | None:
    try:
        parts = urlsplit(value.strip())
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
            return None
        host = parts.netloc.lower()
        path = parts.path
        # These are two representations of the exact same pinned repository file.
        if host == 'raw.githubusercontent.com':
            bits = path.strip('/').split('/', 3)
            if len(bits) == 4:
                host, path = 'github.com', '/' + '/'.join(bits[:2]) + '/blob/' + bits[2] + '/' + bits[3]
        if host in ('rfc-editor.org', 'www.rfc-editor.org'):
            match = re.fullmatch(r'/rfc/rfc(\d+)(?:\.(?:html|txt|pdf))?/?', path)
            if match:
                host, path = 'www.rfc-editor.org', f'/rfc/rfc{match[1]}.html'
        # Keep queries: editions and publisher document IDs can live there.
        return urlunsplit((parts.scheme.lower(), host, path, parts.query, ''))
    except ValueError:
        return None


@lru_cache(maxsize=1)
def source_metadata() -> dict:
    return json.loads(Path(__file__).with_name('source_metadata.json').read_text(encoding='utf-8'))


def additional_profile_references(technology_id: str) -> list[dict]:
    """Retain reviewed bibliography references beyond an individual field."""
    return [{'source': url, 'source_revision': 'Previously recorded individual technical source review; publication rights assessed separately'}
            for url, metadata in source_metadata().get('sources', {}).items()
            if technology_id in metadata.get('technology_ids', [])]


def _references(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('source', 'url') and isinstance(item, str):
                url = canonical_source_url(item)
                if url:
                    yield url, value.get('source_revision', ''), item
            yield from _references(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _references(item)


def source_rights(url: str) -> dict:
    metadata = source_metadata()
    exact = metadata.get('sources', {}).get(url, {})
    rule_id = exact.get('rights_rule')
    if not rule_id:
        host = urlsplit(url).hostname
        rule_id = metadata.get('publisher_rules', {}).get(host, 'UNRESOLVED')
    result = deepcopy(metadata['rights_rules'].get(rule_id, metadata['rights_rules']['UNRESOLVED']))
    result['rule_id'] = rule_id
    return result


def directory_from_profiles(profiles: list[dict]) -> dict:
    metadata = source_metadata()
    entries: dict[str, dict] = {}
    for profile in profiles:
        technology = {'id': profile['id'], 'abbreviation': profile['id'].replace('_', ' ').upper(),
                      'name': profile.get('display_name') or profile.get('label') or profile['id']}
        for url, revision, original in _references(profile):
            known = metadata.get('sources', {}).get(url, {})
            row = entries.setdefault(url, {
                'id': hashlib.sha256(url.encode()).hexdigest()[:24], 'url': url,
                'name': known.get('name') or unquote(urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1]) or urlsplit(url).hostname,
                'publisher': known.get('publisher') or urlsplit(url).hostname,
                'accessed_at': known.get('accessed_at'),
                'access_date_basis': known.get('access_date_basis', 'NOT_RECORDED'),
                'rights': source_rights(url), 'technologies': {}, 'revisions': set(), 'aliases': set(),
            })
            row['technologies'][technology['id']] = technology
            row['aliases'].add(original)
            if revision:
                row['revisions'].add(str(revision))
    rows = []
    for row in entries.values():
        row['technologies'] = sorted(row['technologies'].values(), key=lambda item: (item['abbreviation'], item['id']))
        row['revisions'] = sorted(row['revisions'])
        row['aliases'] = sorted(row['aliases'])
        rows.append(row)
    rows.sort(key=lambda row: (row['technologies'][0]['abbreviation'], row['name'].casefold(), row['url']))
    return {'sources': rows, 'source_count': len(rows), 'technology_count': len(profiles),
            'rights_reviewed_at': metadata['reviewed_at'],
            'scope': 'Bibliographic metadata and publisher rights review; no original documents, copied standard tables or license grants.'}
