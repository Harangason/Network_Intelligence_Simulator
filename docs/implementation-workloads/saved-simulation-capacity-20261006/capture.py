import json
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path(__file__).parent
PROJECT = '20261006151837393-c677c6ca'
PROPOSAL = 'c135343b-46ad-434e-b769-5467b0c2e679'

def capture(label):
    folder = OUT / label
    folder.mkdir(exist_ok=True)
    responses = {}
    for name, path in {
        'parameters': '/api/engineering/workflow/parameters',
        'user-values': '/api/engineering/workflow/parameters/user-defined-values',
        'review': '/api/engineering/workflow/parameters/review?proposal=' + PROPOSAL,
        'proposal': '/api/engineering/agent/proposals/' + PROPOSAL,
        'build': '/api/build-info',
    }.items():
        with urlopen(Request('http://localhost:13500' + path, headers={'X-Project-ID': PROJECT}), timeout=180) as response:
            responses[name] = json.load(response)
        (folder / (name + '.json')).write_text(json.dumps(responses[name], indent=2, ensure_ascii=False), encoding='utf-8')
    p = responses['parameters']['parameters']
    print('build', responses['build'])
    print('review source', responses['review']['source'], 'findings', len(responses['review']['findings']))
    print('first', responses['review']['findings'][:1])
    for technology in ('lin', 'can_fd', 'ethernet'):
        group = (p.get('simulation_parameter_assumptions') or {}).get(technology, {})
        values = group.get('values', {})
        rates = {key: value for key, value in values.items() if 'bitrate' in key}
        print(technology, 'assumed rates', rates, 'reviewed', (p.get('technology_parameters') or {}).get(technology, {}).get('values', {}))

if __name__ == '__main__':
    import sys
    capture(sys.argv[1] if len(sys.argv) > 1 else 'before-live')
