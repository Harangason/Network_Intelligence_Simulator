"""Condense one immutable standalone round without changing test outcomes."""
import argparse
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('round', type=Path)
    args = parser.parse_args()
    report = json.loads(args.round.read_text(encoding='utf-8'))
    groups = defaultdict(list)
    rows = []
    for case in report['cases']:
        case_id = case['case_id']
        detail = case.get('technical_detail', '')
        findings = []
        job_id = case.get('job_id')
        if job_id:
            job = Path('.tool-checker/state/jobs') / job_id
            for result_path in job.glob('*-result.json'):
                result = json.loads(result_path.read_text(encoding='utf-8'))
                findings += result.get('data', {}).get('observations', {}).get('findings', [])
            errors = glob.glob(str(job / 'adapter-evidence-*' / case_id / 'adapter-error.txt'))
            if errors:
                detail = Path(errors[0]).read_text(encoding='utf-8', errors='replace').splitlines()[0]
        codes = [item.get('code') for item in findings if item.get('blocking') and item.get('code')]
        if 'Ausgangsmodell' in detail or 'Ausgangsmodell' in str(case.get('messages', [])):
            group = 'DEPENDENT_MODEL_INCOMPLETE'
        elif 'Testcontainer fehlt' in detail or 'Testcontainer fehlt' in str(case.get('messages', [])):
            group = 'OLD_EA_STACK_MISSING'
        elif 'TC_UNCONFIRMED_ENCODING_PROPOSAL' in codes:
            group = 'UNCONFIRMED_ENCODING'
        elif detail.startswith('Error: Wizard blieb trotz Fortsetzen'):
            group = 'REPEATED_PRODUCT_VALIDATION_BLOCK'
        elif 'Stellbefehl: Kodierung fachlich offen' in detail:
            group = 'SOURCE_ENCODING_UNSPECIFIED'
        elif 'fehlende' in detail and 'Transporte' in detail:
            group = 'ROUTING_TRANSPORT_GAP'
        elif 'Adapter BLOCKED' in str(case.get('messages', [])):
            group = 'ADAPTER_EVIDENCE_BLOCK'
        elif detail:
            group = 'OTHER_DETAIL'
        elif codes:
            group = codes[0]
        else:
            group = 'OTHER'
        groups[group].append(case_id)
        rows.append({'case_id': case_id, 'status': case['status'], 'group': group,
                     'detail': detail[:600], 'blocking_codes': codes[:12], 'job_id': job_id})
    output = {'status_counts': dict(Counter(case['status'] for case in report['cases'])),
              'groups': {key: {'count': len(ids), 'cases': ids} for key, ids in sorted(groups.items())},
              'cases': rows}
    target = args.round.with_name(args.round.stem + '-analysis.json')
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(target), 'status_counts': output['status_counts'],
                      'group_counts': {key: value['count'] for key, value in output['groups'].items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
