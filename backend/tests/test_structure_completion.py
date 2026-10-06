"""Regression guards for the completed migration responsibilities."""
import ast
import csv
import importlib.util
import json
from pathlib import Path
import pytest
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
from backend.nis.communication.core.physical import validate_physical_realization

ROOT = Path(__file__).resolve().parents[2]

def load_script(relative):
    spec = importlib.util.spec_from_file_location('structure_' + Path(relative).stem.replace('-', '_'), ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def technology_branches(source):
    """Detect concrete protocol comparisons inside generic timing services."""
    names = {'CAN', 'CAN_CLASSIC', 'CAN_FD', 'CANFD', 'LIN', 'ETHERNET', 'I2C', 'SPI'}
    return [node.lineno for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.If, ast.IfExp))
            and any(isinstance(value, ast.Constant) and value.value in names for value in ast.walk(node.test))]

def test_timing_dispatch_has_no_concrete_protocol_rules():
    for path in ['backend/nis/engineering/capacity/calculators.py', 'backend/nis/communication/core/components.py']:
        source = (ROOT / path).read_text(encoding='utf-8')
        tree = ast.parse(source)
        scope = next((node for node in tree.body if getattr(node, 'name', '') == 'TechnologyTimingModel'), None)
        assert not technology_branches(ast.unparse(scope) if scope else source), path
        assert not any(isinstance(node, ast.ImportFrom) and (node.module or '').startswith('backend.nis.engineering')
                       for node in ast.walk(scope or tree)), path
    # Prove the guard detects the former misplaced rule and a new inline default.
    assert technology_branches("if protocol == 'CAN_FD':\n    bits = 64 * 8")
    assert technology_branches("limit = 8 if protocol == 'LIN' else None")

def test_runtime_arbitration_and_phy_rules_have_technology_owners():
    scheduler = (ROOT / 'backend/nis/simulation/runtime/event_scheduler.py').read_text()
    assert 'can_id' not in scheduler
    physical = (ROOT / 'backend/nis/communication/core/physical.py').read_text()
    assert not technology_branches(physical)
    assert '100BASE_TX' not in physical and 'RS485_2W' not in physical
    for key in ['can', 'can_fd', 'ethernet', 'lin', 'i2c', 'spi']:
        implementation = DEFAULT_TECHNOLOGY_REGISTRY.timing_implementation(key)
        assert implementation.__name__ == f'backend.nis.communication.technologies.{key}.timing'

def test_frontend_technology_data_is_exact_backend_projection():
    generator = load_script('scripts/build/project-vocabulary.py')
    actual = json.loads((ROOT / 'frontend/src/features/communication/lib/technology-projection.json').read_text(encoding='utf-8'))
    assert actual == generator.technology_projection(ROOT)
    assert {profile['id'] for profile in actual['technologies']} == {p['id'] for p in DEFAULT_TECHNOLOGY_REGISTRY.profiles()}

def test_mapping_covers_current_application_and_every_transition():
    mapping = load_script('scripts/migrations/structure_mapping.py')
    rows = list(csv.DictReader((ROOT / 'docs/migrations/structure_mapping.csv').read_text(encoding='utf-8').splitlines()))
    covered = {r['source_path'] for r in rows} | {r['target_path'] for r in rows}
    assert set(mapping.inventory()) <= covered
    for row in rows:
        assert row['owner'] and isinstance(json.loads(row['consumers']), list)
        if row['action'] == 'move-with-forwarding-entry':
            assert row['source_path'] in row['removal_criterion']
            assert row['owner'] in row['removal_criterion']
            assert (ROOT / row['target_path']).is_file()
    for path in ['scripts/build/project-vocabulary.py', 'scripts/tests/test_release_frontend_discovery.py',
                 'frontend/src/app/api/simulations/[id]/artifacts/[format]/route.ts']:
        assert path in covered

def test_technology_entry_documents_match_actual_capabilities():
    for profile in DEFAULT_TECHNOLOGY_REGISTRY.profiles():
        document = ROOT / 'backend/nis/communication/technologies' / profile['id'] / 'README.md'
        text = document.read_text(encoding='utf-8')
        assert profile['id'] in text and profile['implementation_status'] in text
        assert 'profile.json' in text and 'Tests' in text


def test_review_rates_are_projected_from_profile_without_copies():
    from backend.nis.communication.catalog import REVIEW_RATE_PROPOSALS
    for path in (ROOT / 'backend/nis/communication/technologies').glob('*/review.json'):
        review = json.loads(path.read_text(encoding='utf-8'))
        profile = json.loads(path.with_name('profile.json').read_text(encoding='utf-8'))
        assert 'rate_proposal' not in review
        if path.parent.name in REVIEW_RATE_PROPOSALS:
            assert REVIEW_RATE_PROPOSALS[path.parent.name] == profile['parameter_proposals']


def test_legacy_catalog_exports_preserve_complete_reference_content():
    from backend.nis.communication import catalog
    expected = json.loads((ROOT / 'backend/tests/fixtures/structure_legacy_catalog.json').read_text(encoding='utf-8'))
    actual = {key:getattr(catalog,key) for key in expected}
    assert json.loads(json.dumps(actual)) == expected
    assert len(catalog.REVIEW_RATE_PROPOSALS) == 66
    assert set(catalog.LOCAL_EVIDENCE_FIELDS) == {'I2C','SPI','GPIO','ADC','DAC'}
    assert all(isinstance(fields,tuple) and all(isinstance(field,tuple) for field in fields)
               for fields in catalog.LOCAL_EVIDENCE_FIELDS.values())
