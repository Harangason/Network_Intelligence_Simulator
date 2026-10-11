import json, zipfile
from pathlib import Path

out = Path(__file__).parent
trace = next((out/'before-topology-catalog-browser').glob('wizard-exact*/trace.zip'))
rows = []
with zipfile.ZipFile(trace) as archive:
    for name in archive.namelist():
        if not name.endswith('.network'):
            continue
        for line in archive.read(name).splitlines():
            item = json.loads(line)
            if item.get('type') != 'resource-snapshot':
                continue
            snapshot = item['snapshot']
            request, response = snapshot['request'], snapshot['response']
            if '/api/' not in request['url']:
                continue
            row = {'started':snapshot['startedDateTime'], 'method':request['method'],
                   'url':request['url'], 'status':response['status'], 'ms':snapshot['time']}
            content = response.get('content',{})
            resource = content.get('_file')
            if resource and resource in archive.namelist():
                try:
                    body = json.loads(archive.read(resource))
                    data = body.get('data',body)
                    if request['url'].endswith('/workflow/parameters') and request['method'] == 'GET':
                        row['saved_parameters_resource'] = resource
                    if '/proposals/' in request['url']:
                        row['proposal'] = {key:data.get(key) for key in
                                           ('id','status','proposal_type','revision','change_count','validation_summary')}
                except (ValueError,AttributeError):
                    pass
            rows.append(row)
rows.sort(key=lambda row:row['started'])
parameters_resource = next(row['saved_parameters_resource'] for row in reversed(rows) if 'saved_parameters_resource' in row)
with zipfile.ZipFile(trace) as archive:
    (out/'topology-return-saved-parameters.json').write_bytes(archive.read(parameters_resource))
selected = rows[-90:]
(out/'topology-return-request-diagnostic.json').write_text(json.dumps(selected,indent=2),encoding='utf-8')
for row in selected:
    if '/proposals/' in row['url'] or row['method'] == 'PATCH':
        print(json.dumps(row,ensure_ascii=False))
