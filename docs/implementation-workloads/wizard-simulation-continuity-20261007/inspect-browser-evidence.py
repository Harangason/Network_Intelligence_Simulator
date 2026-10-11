import json, zipfile
from pathlib import Path

root = Path(__file__).parent.parents[2]
base = root/'backend/test-output/release-gates/delivery-e9e540f4d7a2/951b0d517929/browser'
for directory in sorted([*base.glob('wizard-Raspberry*'), *base.glob('wizard-exact*')]):
    results = {}
    with zipfile.ZipFile(directory/'trace.zip') as archive:
        for name in archive.namelist():
            if not name.startswith('resources/'):
                continue
            try:
                value = json.loads(archive.read(name))
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(value, dict) or 'artifact_checks' not in value:
                continue
            check = value['artifact_checks'].get('parameters') or {}
            if check.get('profile_findings'):
                result = {'required':check.get('required'), 'profile_findings':check['profile_findings']}
                results[json.dumps(result, sort_keys=True)] = result
    print(json.dumps({'test':directory.name, 'checks':list(results.values())}, ensure_ascii=False))
