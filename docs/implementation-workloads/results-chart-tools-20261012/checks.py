import json,subprocess
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]
node='C:/Program Files/nodejs/node.exe'
checks={'chart-data':[node,'--experimental-strip-types','--test','src/features/workflow/stage_08_results_analysis/runtime-chart-data.test.mjs'],
        'typecheck':[node,'node_modules/typescript/bin/tsc','--noEmit','--incremental','false']}
for name,command in checks.items():
    result=subprocess.run(command,cwd=ROOT/'frontend',capture_output=True,text=True)
    (HERE/(name+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
    record={'status':'PASSED' if result.returncode==0 else 'FAILED','command':command,'exit_code':result.returncode,'completed_at':datetime.now(timezone.utc).isoformat(),'scope':'Targeted frontend checks; no full gate'}
    (HERE/(name+'.json')).write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(name,record['status'],flush=True)
    assert result.returncode==0,result.stdout+result.stderr
