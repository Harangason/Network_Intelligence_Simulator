import json,re,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
base=Path(sys.argv[1]) if len(sys.argv)>1 else root/'backend/test-output/release-gates'
receipts=list(base.glob('**/receipt.json')) if base.exists() else []
receipts=[path for path in receipts if path.stat().st_mtime >= (float(sys.argv[2]) if len(sys.argv)>2 else 0)]
if not receipts:
    print(json.dumps({'phase':'INITIAL_MANIFEST_SCAN'}))
    raise SystemExit(0)
path=max(receipts,key=lambda p:p.stat().st_mtime)
receipt=json.loads(path.read_text(encoding='utf-8'))
summary={'receipt':str(path),'status':receipt['status'],'checks':receipt['checks']}
for name in ('typecheck','frontend-tests','backend-tests','browser-e2e','small-http','large-http'):
    log=path.parent/(name+'.log')
    if not log.exists():continue
    text=log.read_text(encoding='utf-8',errors='replace')
    lines=text.splitlines()
    relevant=[line for line in lines if re.search(r'\[\s*\d+%\]|\d+ passed|\d+ failed|\d+ skipped|# (tests|pass|fail) |[✓✘]|\bok\s+\d+\s+e2e|\bx\s+\d+\s+e2e|Error:|Traceback',line)]
    summary[name]={'bytes':log.stat().st_size,'progress':relevant[-2:]}
    if name=='browser-e2e':
        summary[name]['passed_cases']=sum(bool(re.search(r'\bok\s+\d+\s+e2e',line)) for line in lines)
        summary[name]['failed_cases']=sum(bool(re.search(r'\bx\s+\d+\s+e2e',line)) for line in lines)
if receipt.get('error'):summary['error']=receipt['error']
print(json.dumps(summary,ensure_ascii=False))
