"""Check saved actual NIS source findings against unchanged source literals."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--case', choices=['vehicle', 'robot'], required=True)
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[5]
state = json.loads(args.state.read_text(encoding='utf-8'))
source_bytes = Path(state['source']).read_bytes()
source = source_bytes.decode('utf-8')
assert hashlib.sha256(source_bytes).hexdigest() == state['original_sha256']
proposal_file = Path(state['document_response'])
assert hashlib.sha256(proposal_file.read_bytes()).hexdigest() == state['document_response_sha256']
proposal = json.loads(proposal_file.read_text(encoding='utf-8'))
assert proposal['source_sha256'] == state['original_sha256'] and proposal['source_chars'] == len(source)
assert proposal['source_complete'] and proposal['canonical_writes'] is False and proposal['status'] == 'REVIEW_REQUIRED'
facts = proposal['interpretation']['components']
bad_quotes = [index for index, fact in enumerate(facts) if fact['source_quote'] not in source]
bad_context_labels = [index for index, fact in enumerate(facts) if any(label not in source for label in fact.get('source_context', []))]
assert not bad_quotes and not bad_context_labels
cursor = 0
for segment in proposal['segments']:
    assert segment['start'] == cursor and segment['end'] > cursor
    assert hashlib.sha256(source[cursor:segment['end']].encode()).hexdigest() == segment['sha256']
    cursor = segment['end']
assert cursor == len(source)
oracle_file = ROOT / 'docs/implementation-workloads/portfolio-parser-20261018/continuation-b2bb/literal-source-oracle.json'
oracle = next(row for row in json.loads(oracle_file.read_text())['sources'] if row['name'] == args.case)
assert oracle['sha256'] == state['original_sha256'] and oracle['characters'] == len(source)
missing_rows = []
row_count = 0
for unit in oracle['mandatory_units']:
    matching = [fact for fact in facts if fact['kind'] == unit['policy']['kind']
                and fact.get('source_context', []) == unit['source_context']]
    for row in unit['text'].splitlines():
        if not row.strip(): continue
        row_count += 1
        if not any(row in fact['source_quote'] for fact in matching):
            missing_rows.append({'source_ref': unit['source_ref'], 'kind': unit['policy']['kind'],
                                 'context': unit['source_context'], 'literal_row': row})
requirements = [row.strip() for row in source.splitlines() if re.match(r'^\s*REQ[^\s:]+\s*:', row)]
requirement_facts = [fact for fact in facts if fact['kind'] == 'REQUIREMENT']
missing_requirements = [row for row in requirements if not any(row in fact['source_quote'] for fact in requirement_facts)]
assert not missing_rows and not missing_requirements, (missing_rows, missing_requirements)
observations = json.loads((args.state.parent/'intake/canonical-model-observations.json').read_text())
assert len(observations) == 2 and all(row['verified_empty'] for row in observations)
result = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'LITERAL_SOURCE_FINDINGS_REVIEW_PASSED',
          'scope': 'Actual unchanged source and saved native document response only. No allocation, model, simulation or release acceptance.',
          'project_id': state['project_id'], 'original_sha256': state['original_sha256'],
          'actual_response_sha256': state['document_response_sha256'],
          'segments_full_and_contiguous': len(proposal['segments']), 'facts': len(facts),
          'kinds': dict(Counter(fact['kind'] for fact in facts)),
          'mandatory_source_units': len(oracle['mandatory_units']), 'mandatory_nonblank_rows': row_count,
          'formal_requirement_lines': len(requirements), 'missing_rows': missing_rows,
          'missing_requirements': missing_requirements, 'nonliteral_quotes': bad_quotes,
          'nonliteral_context_labels': bad_context_labels,
          'oracle': {'path': str(oracle_file), 'sha256': hashlib.sha256(oracle_file.read_bytes()).hexdigest()},
          'canonical_model_observation': 'VERIFIED_EMPTY_BEFORE_AND_AFTER', 'simulation_pass': False}
(args.state.parent/'document-literal-review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False), flush=True)
