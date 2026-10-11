import json,zipfile
from pathlib import Path
out=Path(__file__).parent
trace=out/'catalog-browser/wizard-exact-confirmed-50--c2f3c-gh-real-wizard-review-large/trace.zip'
requests=[]
with zipfile.ZipFile(trace) as archive:
    for name in archive.namelist():
        if name.endswith('.network'):
            for line in archive.read(name).splitlines():
                entry=json.loads(line).get('snapshot',{})
                request=entry.get('request',{});response=entry.get('response',{})
                url=request.get('url','')
                if '/api/' in url and entry.get('time',0)>1000:
                    requests.append({'url':url,'method':request.get('method'),
                        'status':response.get('status'),'elapsed_ms':entry.get('time'),
                        'started':entry.get('startedDateTime')})
requests.sort(key=lambda entry:entry.get('started') or '')
(out/'return-network-diagnostic.json').write_text(json.dumps(requests,indent=2),encoding='utf-8')
print(json.dumps(requests[-20:],indent=2))
