"""Preview or apply only explicit, unambiguous Wizard system assignments."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.system_ownership import migrate_confirmed_system_owners
from backend.engineering.db import close_pool

parser = argparse.ArgumentParser()
parser.add_argument('--project', required=True)
parser.add_argument('--apply', action='store_true')
parser.add_argument('--report', type=Path)
args = parser.parse_args()
try:
    preview = migrate_confirmed_system_owners(args.project)
    report = {'project': args.project, 'preview': preview}
    if args.apply:
        report['applied'] = migrate_confirmed_system_owners(args.project, apply=True)
        report['after'] = migrate_confirmed_system_owners(args.project)
        assert report['after']['count'] == 0 and not report['after']['topology_changes'], report['after']
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'project': args.project, 'applied': args.apply, 'owner_changes': preview['count'],
        'topology_changes': len(preview['topology_changes']), 'skipped': preview['skipped'],
        'idempotent': not report.get('after', {}).get('count') if args.apply else None}, ensure_ascii=False))
finally:
    close_pool()
