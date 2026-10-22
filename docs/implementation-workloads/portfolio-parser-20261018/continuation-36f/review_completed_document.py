"""Independently inspect a completed real document proposal; no requests or writes to NIS."""
import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--proposal',type=Path,required=True)
parser.add_argument('--oracle',type=Path,required=True)
parser.add_argument('--profile-oracle',type=Path)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root))
from backend.nis.agent.orchestration.project_intake import validate_document_interpretation

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
raw=args.source.read_bytes()
source=raw.decode('utf-8')
source_sha=hashlib.sha256(raw).hexdigest()
proposal=json.loads(args.proposal.read_text(encoding='utf-8'))
oracles=json.loads(args.oracle.read_text(encoding='utf-8'))['sources']
oracle=next(row for row in oracles if row['sha256']==source_sha)
assert oracle['characters']==len(source)
assert proposal['source_complete'] and proposal['source_sha256']==source_sha
assert proposal['source_chars']==len(source)
assert proposal['status']=='REVIEW_REQUIRED' and proposal['canonical_writes'] is False
assert proposal['provider']=='local_ollama'
interpretation=proposal['interpretation']
# Validate a detached copy so the actual captured response is never rewritten.
validate_document_interpretation(copy.deepcopy(interpretation),source,aggregate=True)
facts=interpretation['components']
missing=[]
row_count=0
for unit in oracle['mandatory_units']:
    policy=unit.get('policy') or {}
    eligible=[fact for fact in facts if fact['source_context']==unit['source_context']
              and (not policy.get('kind') or fact['kind']==policy['kind'])]
    for row in unit['text'].splitlines():
        if not row.strip():
            continue
        row_count+=1
        if not any(row in fact['source_quote'] for fact in eligible):
            missing.append({'source_ref':unit['source_ref'],'source_context':unit['source_context'],
                            'required_kind':policy.get('kind'),'literal_row':row})
req_ids=sorted(set(re.findall(r'REQ[-\u2010-\u2014\u2212][^\s:*,;]+',source)))
all_quotes='\n'.join(fact['source_quote'] for fact in facts)
missing_ids=[identity for identity in req_ids if identity not in all_quotes]
profiles=[]
if args.profile_oracle:
    profile_oracle=json.loads(args.profile_oracle.read_text(encoding='utf-8'))
    assert profile_oracle['source_sha256']==source_sha
    for profile in profile_oracle['profiles']:
        eligible=[fact for fact in facts if fact['kind']=='REQUIREMENT'
                  and profile['context_heading'] in fact['source_context']]
        missing_lines=[line for line in profile['requirement_lines']
                       if not any(line in fact['source_quote'] for fact in eligible)]
        profiles.append({'profile_id':profile['profile_id'],'context_heading':profile['context_heading'],
                         'required_lines':len(profile['requirement_lines']),'missing_requirement_lines':missing_lines,
                         'facts_in_profile':sum(profile['context_heading'] in fact['source_context'] for fact in facts)})
report={'at_utc':datetime.now(timezone.utc).isoformat(),'scope':__doc__,
        'source_sha256':source_sha,'source_chars':len(source),'public_aggregate_validation_pass':True,
        'facts':len(facts),'by_kind':dict(Counter(f['kind'] for f in facts)),
        'mandatory_units':len(oracle['mandatory_units']),'mandatory_nonblank_rows':row_count,
        'missing_required_rows':missing,'original_requirement_ids':len(req_ids),
        'missing_requirement_ids':missing_ids,'profiles':profiles,
        'literal_source_review_pass':not missing and not missing_ids and not any(p['missing_requirement_lines'] for p in profiles),
        'native_semantic_reference_plan_pass':False,'simulation_pass':False,'productive_delivery':False,
        'evidence':{'path':str(args.proposal.resolve()),'sha256':digest(args.proposal)},
        'source_oracle':{'path':str(args.oracle.resolve()),'sha256':digest(args.oracle)}}
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({key:report[key] for key in ['literal_source_review_pass','facts','by_kind','mandatory_units','mandatory_nonblank_rows','original_requirement_ids']},ensure_ascii=False))
assert report['literal_source_review_pass'], 'Actual response has literal source coverage findings; inspect saved report.'
