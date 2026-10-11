"""Record classification scope without publishing any original document text."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.simulation_service import SimulationService
from backend.communication.technologies.sources import directory_from_profiles, source_metadata

catalog = SimulationService().catalog()
profiles = {item['id']: item for domain in catalog['domains'] for item in domain['technologies']}
directory = directory_from_profiles(list(profiles.values()))
metadata = source_metadata()
sources = []
for row in directory['sources']:
    specific = metadata['sources'].get(row['url'], {})
    rights = row['rights']
    sources.append({'url': row['url'], 'name': row['name'], 'technologies': [item['id'] for item in row['technologies']],
        'publication': rights['publication'], 'rule': rights['rule_id'], 'explanation': rights['explanation'],
        'evidence_url': rights.get('evidence_url'),
        'basis': 'NO_ESTABLISHED_PERMISSION' if rights['publication'] == 'UNRESOLVED' else
            'RECORDED_DOCUMENT_SPECIFIC_RULE' if specific.get('rights_rule') else 'PUBLISHER_TERMS_WITHOUT_INDIVIDUAL_PERMISSION',
        'accessed_at': row['accessed_at'], 'access_date_basis': row['access_date_basis']})
proofs = []
for relative in ('work/matter-primary/source-access.json', 'work/matter-primary/sdk-manifest.json'):
    path = ROOT / relative
    assert path.is_file()
    proofs.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
report = {'scope': 'Document publication classification and explicit unresolved cases; no legal permission granted, no copied original text, no claim of implementation/patent/certification clearance.',
    'reviewed_at': directory['rights_reviewed_at'], 'sources': sources,
    'counts': dict(Counter(row['publication'] for row in sources)),
    'source_access_proofs': proofs,
    'custom_definitions_without_external_standard': ['custom_binary', 'custom_protocol'],
    'technology_clearance': {'precautionary_scoped_policy': ['nmea0183', 'nmea2000', 'mipi_csi2', 'mipi_dsi'],
        'not_equivalent_to_document_publication_permission': True,
        'no_claim_that_every_abstract_simulation_requires_implementation_license': True}}
output = ROOT / 'docs/implementation-workloads/source-directory-20261003/rights-review.json'
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'sources': len(sources), 'counts': report['counts'], 'report': str(output)}))
