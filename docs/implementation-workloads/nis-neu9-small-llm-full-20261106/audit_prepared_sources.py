"""Audit every actual prepared private reference against the public resolver, without inference."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import urllib.request
import httpx

goal=Path(__file__).resolve().parent
root=goal.parents[2]
sys.path.insert(0,str(root))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state',type=Path,required=True)
parser.add_argument('--name',default='prepared-source-audit')
args=parser.parse_args()
out=args.state.resolve().parent
assert out.is_relative_to(goal)
state=json.loads(args.state.read_text(encoding='utf-8'))
source=Path(state['source']).read_bytes().decode('utf-8')
assert hashlib.sha256(source.encode()).hexdigest()==state['original_sha256']
if (out/'backend-terminal.log').exists():
    lines=(out/'backend-terminal.log').read_text(encoding='utf-8').splitlines()
    records=[json.loads(line.split('Native document validation failed: ',1)[1]) for line in lines if 'Native document validation failed: ' in line]
    for record in records:
        assert hashlib.sha256(record['response'].encode()).hexdigest()==record['response_sha256']
    (out/'native-terminal-diagnostics.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
counts={}
for name,path in [('export','/api/engineering/projects/export'),('draft','/api/engineering/agent/project-draft'),('jobs','/api/simulations')]:
    with opener.open(urllib.request.Request(state['base_url']+path,headers={'X-Project-ID':state['project_id']}),timeout=15) as response:
        raw=response.read()
    body=json.loads(raw)
    (out/(args.name+'-terminal-'+name+'.json')).write_bytes(raw)
    if name=='export':
        counts={key:len(value) for key,value in body['source_data'].items()}
        assert not any(counts.values())
    if name=='jobs':
        assert body['jobs']==[]
os.environ['LOCAL_AI_MODEL']='llama3.1:8b'
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.nis.agent.orchestration.project_intake import document_component_sources,resolve_document_references
captured={}
class PreparedCaptured(Exception):
    pass
async def run():
    reasoner=LocalEngineeringReasoner()
    await reasoner.client.aclose()
    def transport(request):
        assert request.url.path.endswith('/show'), 'No inference request is permitted in this audit'
        frame=inspect.currentframe()
        while frame and frame.f_code.co_name!='interpret_document':
            frame=frame.f_back
        assert frame is not None
        captured.update(json.loads(json.dumps({key:frame.f_locals[key] for key in ['prepared','segments']})))
        raise PreparedCaptured()
    reasoner.client=httpx.AsyncClient(transport=httpx.MockTransport(transport))
    try:
        with_error=False
        try:
            await reasoner.interpret_document(source,'neu 9.txt')
        except PreparedCaptured:
            with_error=True
        assert with_error
    finally:
        await reasoner.client.aclose()
asyncio.run(run())
segments,prepared=captured['segments'],captured['prepared']
assert ''.join(segment['text'] for segment in segments)==source
assert segments[0]['start']==0 and segments[-1]['end']==len(source)
assert all(left['end']==right['start'] for left,right in zip(segments,segments[1:]))
audit=[]
for index,(segment,item) in enumerate(zip(segments,prepared),1):
    prefix=source[:segment['start']]
    units={unit['source_ref']:unit for unit in document_component_sources(item['rows'],scope_prefix=prefix)}
    keys=item['schema']['properties']['components']['properties']
    invalid=[]
    for key in keys:
        unit=units.get(key)
        if unit is None or not unit['text'].strip() or len(unit['text'].strip())>1200:
            invalid.append({'reference':key,'reason':'missing' if unit is None else 'empty' if not unit['text'].strip() else 'overlong',
                            'unit':unit})
    public_error=None
    try:
        resolve_document_references({'components':{key:{} for key in keys},'technologies':{}},item['rows'],model_schema=item['schema'],scope_prefix=prefix)
    except ValueError as error:
        public_error=str(error)
    assert bool(public_error)==bool(invalid)
    audit.append({'segment':index,'start':segment['start'],'end':segment['end'],'allowed_components':len(keys),
                  'required_components':len(item['schema']['properties']['components']['required']),
                  'invalid_references':invalid,'public_projection_error':public_error})
(out/(args.name+'-payloads.json')).write_text(json.dumps(captured,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report={'at':datetime.now(timezone.utc).isoformat(),'scope':'Pure actual product preparation captured before metadata/inference; no native acceptance or canonical writes',
        'source_sha256':state['original_sha256'],'source_chars':len(source),'complete_contiguous_source':True,
        'all_key_sets_bounded':all(row['allowed_components']<=24 for row in audit),'canonical_counts_after_failure':counts,'jobs':[],
        'sections':audit,'invalid_reference_count':sum(len(row['invalid_references']) for row in audit)}
(out/(args.name+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({key:value for key,value in report.items() if key not in ['sections','canonical_counts_after_failure']},ensure_ascii=True))
print(json.dumps([{'segment':row['segment'],'invalid':[(item['reference'],item['reason']) for item in row['invalid_references']]} for row in audit if row['invalid_references']]))
