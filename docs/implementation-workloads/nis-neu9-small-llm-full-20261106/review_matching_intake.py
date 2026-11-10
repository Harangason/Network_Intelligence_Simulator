"""Review a fresh intake only when identical to independently reviewed literal findings."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state',type=Path,required=True)
parser.add_argument('--native-session',type=int,required=True)
parser.add_argument('--native-exit',type=int,required=True)
args=parser.parse_args()
state_path=args.state.resolve(strict=True)
assert state_path.is_relative_to(HERE)
state=read(state_path)
assert args.native_exit==0
directory=state_path.parent/'intake'
destination=directory/'independent-literal-source-review.json'
assert not destination.exists(), 'Do not overwrite a prior review'
proposal_path=directory/'proposal.json'
projection_path=directory/'actual-product-review.json'
proposal,projection=read(proposal_path),read(projection_path)
source_path=Path(state['source'])
source=source_path.read_bytes().decode('utf-8')
assert sha(source_path)==state['original_sha256']==proposal['source_sha256']
assert len(source)==state['original_chars']==proposal['source_chars']
assert proposal['source_complete'] and proposal['model']=='qwen3.5:9b'
assert proposal['provider']=='local_ollama' and proposal['canonical_writes'] is False
assert state['document_response_sha256']==sha(proposal_path)
position=0
for segment in proposal['segments']:
    assert segment['start']==position and segment['end']>position
    assert hashlib.sha256(source[position:segment['end']].encode()).hexdigest()==segment['sha256']
    position=segment['end']
assert position==len(source)
baseline=HERE/'attempt-21/intake'
review=read(baseline/'independent-literal-source-review.json')
assert review['decision']=='APPROVE_LITERAL_DOCUMENT_FINDINGS_ONLY'
assert review['proposal_sha256']==sha(baseline/'proposal.json')
assert review['product_projection_sha256']==sha(baseline/'actual-product-review.json')
assert proposal['interpretation']==read(baseline/'proposal.json')['interpretation'], 'Changed findings need a fresh semantic review'
assert projection==read(baseline/'actual-product-review.json'), 'Changed product projection needs review'
facts=proposal['interpretation']['components']
for row in facts:
    assert row['source_quote'] in source
quantities={role:sum(row['quantity'] for row in facts if row['kind']=='INSTANCE' and row['role']==role)
            for role in ['SENSOR','ACTUATOR','CONTROLLER','GATEWAY']}
assert quantities=={'SENSOR':100,'ACTUATOR':100,'CONTROLLER':50,'GATEWAY':1}
report={'at':datetime.now(timezone.utc).isoformat(),'decision':'APPROVE_LITERAL_DOCUMENT_FINDINGS_ONLY',
        'native_session':args.native_session,'native_exit':args.native_exit,
        'proposal_sha256':sha(proposal_path),'original_sha256':sha(source_path),
        'source_characters':len(source),'contiguous_hashed_segments':len(proposal['segments']),
        'facts':len(facts),'fact_kinds':dict(Counter(row['kind'] for row in facts)),
        'instance_quantities':quantities,'interpretation_and_projection_equal_reviewed_attempt21':True,
        'prior_review':{'path':str(baseline/'independent-literal-source-review.json'),
                        'sha256':sha(baseline/'independent-literal-source-review.json')},
        'product_projection_sha256':sha(projection_path),'human_clarification':'25 LIN bound separately; original unchanged',
        'canonical_model_approved':False,'simulation_pass':False,'production_delivered':False}
save(destination,report)
state.update(document_review_status='APPROVED_LITERAL_SOURCE_FINDINGS',
             reviewed_document_response_sha256=sha(proposal_path),independent_document_review=str(destination))
save(state_path,state)
print(json.dumps(report,ensure_ascii=False))
