import json,collections
from pathlib import Path
r=Path('.tool-checker');m=json.loads((r/'industry50.normalized.json').read_text(encoding='utf8'));rows=[]
for c in m['test_cases'][:40]:
 p=r/'evidence/industry50'/c['test_id'];d=json.loads((p/'draft.json').read_text(encoding='utf8'))['data'];h=json.loads((p/'history.json').read_text(encoding='utf8'));counts=dict(collections.Counter(x['role'] for x in d['devices']))
 rows.append({'id':c['test_id'],'title':c['title'],'counts':counts,'devices':len(d['devices']),'unknown_kind':sum(not x['known_kind'] for x in d['devices']),'without_technology':sum(not x.get('technology') for x in d['devices']),'status':d.get('status'),'original_retained':d.get('original_requirement')==c['input'],'browser_evidence':(p/'browser.png').exists(),'source_lines':c['source_lines'],'full_e2e_pass':False})
(r/'evidence/industry50/intake-analysis.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(rows[-4:],ensure_ascii=False))

