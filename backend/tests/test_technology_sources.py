"""Bibliographic identity, provenance and rights remain separate from execution."""
from backend.nis.app import create_app
from backend.nis.simulation.service import SimulationService
from backend.nis.communication.services.sources import canonical_source_url, directory_from_profiles, source_rights


def test_same_document_deduplicates_across_buses_and_fragments_without_merging_editions():
    raw = 'https://raw.githubusercontent.com/example/repo/abcdef/src/main.c'
    blob = 'https://github.com/example/repo/blob/abcdef/src/main.c'
    profiles = [{'id': 'can', 'label': 'CAN', 'refs': [{'source': raw + '#one'}, {'source': blob}]},
                {'id': 'i2c', 'label': 'I2C', 'refs': [{'source': blob + '#two'},
                     {'source': blob.replace('abcdef', 'fedcba')}] }]
    data = directory_from_profiles(profiles)
    assert data['source_count'] == 2
    shared = next(row for row in data['sources'] if row['url'] == blob)
    assert {row['id'] for row in shared['technologies']} == {'can', 'i2c'}
    assert shared['accessed_at'] is None
    assert shared['rights']['publication'] == 'UNRESOLVED'


def test_untrusted_link_schemes_credentials_and_version_queries():
    assert canonical_source_url('javascript:alert(1)') is None
    assert canonical_source_url('file:///secret') is None
    assert canonical_source_url('https://user:secret@example.com/doc') is None
    assert canonical_source_url('https://example.com/doc?edition=1#page=4') == 'https://example.com/doc?edition=1'
    assert canonical_source_url('https://example.com/doc?edition=2') != canonical_source_url('https://example.com/doc?edition=1')


def test_rfc_landing_html_text_and_pdf_keep_one_document_and_all_bus_assignments():
    base = 'https://www.rfc-editor.org/rfc/rfc8200'
    profiles = [{'id': identity, 'label': identity, 'refs': [{'source': base + suffix}]}
                for identity, suffix in [('ip', ''), ('udp', '.html'), ('tcp', '.txt'), ('ethernet', '.pdf#page=3')]]
    rows = directory_from_profiles(profiles)['sources']
    assert len(rows) == 1
    assert rows[0]['url'] == base + '.html'
    assert len(rows[0]['aliases']) == 4
    assert {item['id'] for item in rows[0]['technologies']} == {'ip', 'udp', 'tcp', 'ethernet'}
    assert canonical_source_url(base.replace('8200', '791')) != rows[0]['url']


def test_matter_document_and_sdk_are_not_one_license():
    core = source_rights('https://csa-iot.org/wp-content/uploads/2026/09/23-27349-012_Matter-1.6.1-Core-Specification.pdf')
    assert core['publication'] == 'PERMISSION_REQUIRED'
    assert '#page=5' in core['evidence_url']
    sdk = source_rights('https://github.com/project-chip/connectedhomeip/blob/3bcdd56ba54fb88b2afb4bfef575014671df7aa7/src/lib/core/CHIPConfig.h')
    assert sdk['rule_id'] != core['rule_id']


def test_complete_source_view_does_not_mutate_profile_parameters_and_tracks_unknown_dates():
    service = SimulationService()
    before = service.catalog_json()
    catalog = service.catalog()
    profiles = {p['id']: p for domain in catalog['domains'] for p in domain['technologies']}
    data = directory_from_profiles(list(profiles.values()))
    assert data['technology_count'] == 125
    assert data['source_count'] >= 450
    assert len({row['url'] for row in data['sources']}) == data['source_count']
    assert any(row['accessed_at'] is None for row in data['sources'])
    assert all(row['rights']['explanation'] and row['technologies'] for row in data['sources'])
    assert service.catalog_json() == before


def test_http_directory_is_metadata_only_and_never_serves_original_contents():
    client = create_app(testing=True).test_client()
    response = client.get('/api/technology-sources', headers={'X-Project-ID': 'sources-test'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['technology_count'] == 125
    assert 'document_content' not in str(data.keys())
    assert data['licenses']['mipi_csi2']['blocked']
    assert not data['licenses']['ethernet']['blocked']
