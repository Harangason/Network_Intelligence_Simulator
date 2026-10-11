from pathlib import Path
import json
import re

path=Path('backend/test-output/release-gates/delivery-12bbdd6bffbb/b4c8fffb0ff0/backend-tests.log')
text=path.read_text(encoding='utf-8',errors='replace')
section=text.split('FAILURES',1)[1].split('warnings summary',1)[0]
rows=[]
chunks=re.split(r'^_+ (.*?) _+\s*$',section,flags=re.M)
for i in range(1,len(chunks),2):
    body=chunks[i+1]
    lines=body.splitlines()
    errors=[line for line in lines if line.startswith('E   ') or line.startswith('E    ') or line.startswith('E     ')]
    rows.append({'test':chunks[i], 'body':body, 'errors':errors})
Path('work/second-gate-failure-blocks.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
nodes=[line.split(' ')[1] for line in text.splitlines()if line.startswith('FAILED ')]
Path('work/second-gate-failed-nodeids.json').write_text(json.dumps(nodes,indent=2),encoding='utf-8')
for row in rows:
    print(row['test']+' | '+' '.join(row['errors'][:3])[:650])
