"""Derive bibliographic metadata; unrecorded historical dates remain unknown."""
from pathlib import Path
import json
import re
from urllib.parse import urlsplit,unquote
from backend.app.simulation_service import SimulationService
from backend.communication.technologies.sources import canonical_source_url,directory_from_profiles

root=Path(__file__).resolve().parents[1]
path=root/'backend/communication/technologies/source_metadata.json'
data=json.loads(path.read_text(encoding='utf-8'))
catalog=SimulationService().catalog()
profiles={p['id']:p for d in catalog['domains'] for p in d['technologies']}
directory=directory_from_profiles(list(profiles.values()))
for row in directory['sources']:
 url=row['url']; host=urlsplit(url).hostname
 meta=data['sources'].setdefault(url,{})
 revisions=row['revisions']
 filename=unquote(urlsplit(url).path.rstrip('/').rsplit('/',1)[-1])
 name=next((re.split(r';|\bsections?\b|\bpages?\b|\bread\b|\baccessed\b',s,flags=re.I)[0].strip(' ,:') for s in revisions if len(s)>8),filename)
 meta.setdefault('name',name[:170] or filename or host)
 meta.setdefault('publisher',host)
 dates=[m.group(1) for s in revisions for m in re.finditer(r'(?:accessed|read|retrieved)\s*(20\d\d-\d\d-\d\d)',s,re.I)]
 if dates:
  meta.setdefault('accessed_at',max(dates)); meta.setdefault('access_date_basis','RECORDED_TECHNICAL_REVIEW')
 if host=='www.rfc-editor.org' and re.fullmatch(r'/rfc/rfc\d+\.html',urlsplit(url).path):
  meta['name']='RFC '+re.search(r'rfc(\d+)',urlsplit(url).path)[1]
  meta['rights_rule']='RFC'
 if url=='https://csa-iot.org/wp-content/uploads/2026/09/23-27349-012_Matter-1.6.1-Core-Specification.pdf':
  meta.update(name='Matter 1.6.1 – Core Specification',publisher='Connectivity Standards Alliance',rights_rule='MATTER_CORE')
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'sources':len(directory['sources']),'technologies':len(profiles),'recorded_access_dates':sum(bool(x.get('accessed_at')) for x in data['sources'].values())}))
