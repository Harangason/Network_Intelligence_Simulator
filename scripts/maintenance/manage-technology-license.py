"""Operator-only review of submitted license references, no HTTP self-approval."""

import sys as _entry_sys
from pathlib import Path as _EntryPath
_entry_sys.path.insert(0, str(_EntryPath(__file__).resolve().parents[1]))
import argparse
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from backend.nis.communication.services.licensing import review_evidence
from backend.nis.engineering.projects.project_context import normalize_context_project_id

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    parser.add_argument('--record',required=True)
    parser.add_argument('--reviewer',required=True)
    parser.add_argument('--rationale',required=True)
    parser.add_argument('--evidence',type=Path)
    parser.add_argument('--decision',choices=['approve','revoke'],required=True)
    args=parser.parse_args()
    row=review_evidence(normalize_context_project_id(args.project),args.record,reviewer=args.reviewer,
                        evidence=args.evidence,approve=args.decision=='approve',rationale=args.rationale)
    print(json.dumps({'id':row['id'],'status':row['status'],'project':args.project}))

if __name__=='__main__':
    main()
