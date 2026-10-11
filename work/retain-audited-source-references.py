from pathlib import Path
import json
from urllib.parse import urlsplit,unquote
from backend.communication.technologies.sources import canonical_source_url

root=Path(__file__).resolve().parents[1]
path=root/'backend/communication/technologies/source_metadata.json'
data=json.loads(path.read_text(encoding='utf-8'))
for file in (root/'docs/implementation-workloads/technology-full-parameter-audit-20261001/individual').glob('*.json'):
 record=json.loads(file.read_text(encoding='utf-8'))
 for source in record.get('sources',[]):
  url=canonical_source_url(source)
  if not url: continue
  meta=data['sources'].setdefault(url,{'name':unquote(urlsplit(url).path.rstrip('/').rsplit('/',1)[-1]) or urlsplit(url).hostname,'publisher':urlsplit(url).hostname})
  meta['technology_ids']=sorted(set([*meta.get('technology_ids',[]),record['technology']]))
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'distinct_sources':len(data['sources'])}))
