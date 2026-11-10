"""Replay real native findings through the actual product accumulation.

Surrounding source/device/port decisions are authored mocked fixtures, not a
native original or simulation. No model requests, SQL, or canonical writes.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path.cwd()
sys.path.insert(0,str(ROOT))
import pytest
from backend.nis.agent.orchestration import local_reasoner as r
from backend.tests.test_reference_reasoner import reasoner_with_transport, run_reference, effective_reference_context

OUT=Path(__file__).resolve().parent
raw_path=OUT/'native-v3/response.json'
raw_bytes=raw_path.read_bytes()
response=json.loads(raw_bytes)
findings=json.loads(response['message']['content'])['unresolved']
assert len(findings)==2 and findings[0]['target_ref']=='offline-a' and findings[1]['target_ref']=='offline-b'
wire_replies=[]
with pytest.MonkeyPatch.context() as patch:
    reasoner,prepared,observed=reasoner_with_transport(patch)
    original=r._reference_stream_response
    async def replay(client,url,payload,callback):
        context=effective_reference_context(payload['messages'])
        current=context['current_candidate']['unresolved']
        assert current in ([],findings[:1],findings)
        body=await original(client,url,payload,callback)
        value=json.loads(body['message']['content'])
        # First stage establishes the prior finding. Subsequent responses use
        # exactly the actual two native finding records, without deduplication.
        value['unresolved']=deepcopy(findings[:1] if not wire_replies else findings)
        body['message']['content']=json.dumps(value)
        wire_replies.append(deepcopy(value['unresolved']))
        return body
    patch.setattr(r,'_reference_stream_response',replay)
    result=run_reference(reasoner,prepared)
assert result['status']=='REVIEW_REQUIRED' and result['canonical_writes'] is False
assert result['proposal']['unresolved']==findings
assert any(row['current_candidate']['unresolved']==findings[:1] for row in observed)
assert sum(row['current_candidate']['unresolved']==findings for row in observed)>4
assert all(rows==findings for rows in wire_replies[1:])
assert raw_path.read_bytes()==raw_bytes
proof={'status':'PASS_NATIVE_FINDINGS_PRODUCT_RUNTIME_REPLAY',
       'scope':'Actual native finding records through actual planner; all surrounding workflow decisions mocked. Not a fresh native original or full-native workflow.',
       'native_raw_response_sha256':hashlib.sha256(raw_bytes).hexdigest(),
       'actual_native_generation_requests_in_source_counter':1,'new_generation_requests':0,
       'old_and_new_findings_retained':findings,'mocked_stage_responses':len(wire_replies),
       'native_prompt_only_deduplication':'FAILED_PRESERVED',
       'original_acceptance':False,'simulation_acceptance':False,'production_delivered':False}
(OUT/'native-runtime-replay.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(proof),flush=True)
