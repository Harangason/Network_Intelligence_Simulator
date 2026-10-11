from finish_structure_owners import *
import importlib.util

source = (OUT / 'before/technology-owners/backend/nis/communication/catalog.py').read_text(encoding='utf-8-sig')
names = ['CAN_FD_DATA_LENGTHS','DDS_POLICY_ENTITIES','LOCAL_EVIDENCE_FIELDS','REVIEW_RATE_PROPOSALS']
values = {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(source).body
          if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in names}
keys = set(values['REVIEW_RATE_PROPOSALS']) | {k.lower() for k in values['LOCAL_EVIDENCE_FIELDS']}
for key in keys:
    path = 'backend/nis/communication/technologies/' + key + '/review.json'
    value = json.loads(read(path)) if (ROOT / path).is_file() else {}
    if key in values['REVIEW_RATE_PROPOSALS']: value['legacy_rate_projection'] = True
    if key.upper() in values['LOCAL_EVIDENCE_FIELDS']: value['local_evidence_fields'] = values['LOCAL_EVIDENCE_FIELDS'][key.upper()]
    write(path,json.dumps(value,ensure_ascii=False,indent=2) + '\n')
path = 'backend/nis/communication/catalog.py'
write(path,read(path).replace("if (review := technology_review(key)).get('rate_proposal')}",
                             "if (review := technology_review(key)).get('legacy_rate_projection')}") )
write('backend/tests/fixtures/structure_legacy_catalog.json',json.dumps(values,ensure_ascii=False,indent=2) + '\n')
path = 'backend/tests/test_structure_completion.py'
write(path,read(path) + '''

def test_legacy_catalog_exports_preserve_complete_reference_content():
    from backend.nis.communication import catalog
    expected = json.loads((ROOT / 'backend/tests/fixtures/structure_legacy_catalog.json').read_text(encoding='utf-8'))
    actual = {key:getattr(catalog,key) for key in expected}
    assert json.loads(json.dumps(actual)) == expected
    assert len(catalog.REVIEW_RATE_PROPOSALS) == 66
    assert set(catalog.LOCAL_EVIDENCE_FIELDS) == {'I2C','SPI','GPIO','ADC','DAC'}
    assert all(isinstance(fields,tuple) and all(isinstance(field,tuple) for field in fields)
               for fields in catalog.LOCAL_EVIDENCE_FIELDS.values())
''')
path = 'docs/migrations/structure-checks.json'
value = json.loads(read(path))
value['test_cases'][1]['execution_plan'][0]['pytest_targets'].append('backend/tests/test_structure_completion.py::test_legacy_catalog_exports_preserve_complete_reference_content')
write(path,json.dumps(value,indent=2) + '\n')
apply('complete-catalog-contract')
WRITES.clear()
spec = importlib.util.spec_from_file_location('project',ROOT/'scripts/build/project-vocabulary.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
write('frontend/src/features/communication/lib/technology-projection.json',json.dumps(module.technology_projection(ROOT),ensure_ascii=False,indent=2) + '\n')
apply('complete-catalog-projection')
