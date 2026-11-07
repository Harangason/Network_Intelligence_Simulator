"""Capture normal terminal GETs and the actual first private payload without inference."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request
import httpx

out = Path(__file__).resolve().parent
root = out.parents[2]
sys.path.insert(0,str(root))
state = json.loads((out/'state.json').read_text(encoding='utf-8'))
response = json.loads((out/'intake/response.json').read_text(encoding='utf-8'))
assert state['status'] == 'NATIVE_INTAKE_FAILED' and response['success'] is False
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
rows = {}
for name,path in [('export','/api/engineering/projects/export'),('draft','/api/engineering/agent/project-draft'),('jobs','/api/simulations')]:
    with opener.open(urllib.request.Request(state['base_url']+path,headers={'X-Project-ID':state['project_id']}),timeout=15) as result:
        raw = result.read()
    (out/('terminal-intake-'+name+'.json')).write_bytes(raw)
    rows[name] = {'sha256':hashlib.sha256(raw).hexdigest(),'body':json.loads(raw)}
counts = {key:len(value) for key,value in rows['export']['body']['source_data'].items()}
assert not any(counts.values()) and rows['jobs']['body']['jobs'] == []
os.environ['LOCAL_AI_MODEL'] = 'llama3.1:8b'
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
class CapturedPayload(Exception):
    pass
observed = []
async def capture():
    reasoner = LocalEngineeringReasoner()
    await reasoner.client.aclose()
    def transport(request):
        if request.url.path.endswith('/show'):
            return httpx.Response(200,json={'details':{'family':'llama','format':'gguf','parameter_size':'8B'},'model_info':{'general.parameter_count':8030261312},'capabilities':['completion','tools']})
        payload = json.loads(request.content)
        observed.append(payload)
        raise CapturedPayload()
    reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    try:
        await reasoner.interpret_document(Path(state['source']).read_bytes().decode('utf-8'),'neu 9.txt')
    except CapturedPayload:
        pass
    finally:
        await reasoner.client.aclose()
asyncio.run(capture())
payload, = observed
(out/'first-private-payload.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
components = payload['format']['properties']['components']
report = {'at':datetime.now(timezone.utc).isoformat(),'status':'REPRODUCED_PRIVATE_DECODER_CARDINALITY_GAP',
          'scope':'Actual terminal native failure plus pure reconstruction of the first unchanged product payload; fake transport intercepts before any inference',
          'observed_native_driver_exit_code':1,'terminal_result':response,'canonical_counts_after_failure':counts,'jobs':[],
          'required_component_count':len(components['required']),'permitted_component_key_count':len(components['properties']),
          'declared_max_properties':components['maxProperties'],'first_request_model':payload['model'],
          'context':payload['options'],'exact_last_native_raw_answer_available':False}
assert len(components['required']) <= 24 < len(components['properties'])
(out/'intake-terminal-and-schema-gap.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({key:value for key,value in report.items() if key not in ['terminal_result','canonical_counts_after_failure']}))
