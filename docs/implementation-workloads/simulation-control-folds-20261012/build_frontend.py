from pathlib import Path
import json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
s=json.loads((HERE/'stage.json').read_text());docker=json.loads((ROOT/'config/networkis.resources.json').read_text())['paths']['docker_cli']
r=subprocess.run([docker,'exec','-w',s['stage'],'NetworkIS','node','node_modules/next/dist/bin/next','build'],capture_output=True,text=True)
(HERE/'build.log').write_text(r.stdout+r.stderr,encoding='utf-8')
(HERE/'build.json').write_text(json.dumps({'status':'PASSED' if r.returncode==0 else 'FAILED','exit_code':r.returncode,'stage':s['stage'],'scope':'Frontend compilation only; no image or full test campaign'},indent=2))
print(r.stdout+r.stderr);assert r.returncode==0
