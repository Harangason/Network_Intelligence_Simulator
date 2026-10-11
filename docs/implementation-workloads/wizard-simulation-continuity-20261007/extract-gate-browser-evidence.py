"""Select actual tested cases from a complete PASS; never execute or invent tests."""
import copy,hashlib,json,re,sys
from pathlib import Path
out=Path(__file__).parent.resolve();root=out.parents[2]
receipt_path=Path(sys.argv[1]).resolve()
assert receipt_path.is_relative_to(root/'backend/test-output/release-gates')
receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['status']=='PASS' and all(check['exit_code']==0 for check in receipt['checks'])
source_path=receipt_path.parent/'browser.json'
report=json.loads(source_path.read_text(encoding='utf-8'))
assert not report.get('errors') and report['stats']['unexpected']==0
kind=sys.argv[2] if len(sys.argv)>2 else 'catalog'
assert kind in {'catalog','duration'}
pattern=re.compile(r'new small wizard|Raspberry Pi|exact confirmed 50|native simulation rates' if kind=='catalog'
                   else r'native simulation rates|CAN-FD scenario defaults')
expected=8 if kind=='catalog' else 2
selected=[]
def filter_suite(suite):
    result=copy.deepcopy(suite)
    result['specs']=[]
    for spec in suite.get('specs',[]):
        if pattern.search(spec['title']):
            result['specs'].append(copy.deepcopy(spec));selected.append(result['specs'][-1])
    result['suites']=[item for child in suite.get('suites',[]) if (item:=filter_suite(child))]
    return result if result['specs'] or result['suites'] else None
suites=[item for suite in report['suites'] if (item:=filter_suite(suite))]
tests=[test for spec in selected for test in spec['tests']]
assert len(selected)==len(tests)==expected
assert all(spec['ok'] for spec in selected)
assert all(test['status']=='expected' and test['expectedStatus']=='passed'
           and len(test['results'])==1 and test['results'][0]['status']=='passed' for test in tests)
for test in tests:
    for result in test['results']:
        for attachment in result.get('attachments',[]):
            if 'path' in attachment:
                path=Path(attachment['path'])
                if not path.is_absolute(): path=receipt_path.parent/path
                assert path.is_file(),path
                attachment['path']=str(path.resolve())
def evidence(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
proof={**report,'suites':suites,'stats':{'expected':len(tests),'unexpected':0,'flaky':0,'skipped':0,
       'startTime':report['stats']['startTime'],
       'duration':sum(test['results'][0]['duration'] for test in tests)},
       '_evidence':{'scope':'Selected actual cases from the complete gate; not an additional execution',
                    'receipt':evidence(receipt_path),'browser_report':evidence(source_path),
                    'image_id':receipt['image_id'],'source_sha256':receipt['release']['source_sha256']}}
destination=out/('catalog-browser.json' if kind=='catalog' else 'duration-intent-browser.json')
if kind=='duration' and destination.is_file():
    history=out/'before-workflow-polling';history.mkdir(exist_ok=True)
    (history/destination.name).write_bytes(destination.read_bytes())
destination.write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps({'cases':len(tests),'source':str(source_path),'image_id':receipt['image_id']}))
