import json,sys,hashlib,re,subprocess
from pathlib import Path
base=Path(__file__).resolve().parent;root=base.parents[2]
path=Path(sys.argv[1]);result={}
if path.is_file():
 receipt=json.loads(path.read_text(encoding='utf-8'));result.update(status=receipt['status'],checks=receipt['checks'],error=receipt.get('error'),image=receipt.get('image_id'))
 for name in ('backend-tests','production-build','browser-e2e','small-http','large-http'):
  log=path.parent/(name+'.log')
  if log.exists():
   lines=log.read_text(encoding='utf-8',errors='replace').splitlines()
   result[name]=lines[-2:];result[name+'_failures']=[l for l in lines if re.match(r'^\s*[x\u00d7]\s+\d+',l) or 'FAILED ' in l][-5:]
   result[name+'_progress_failure']=any('F' in l and re.fullmatch(r'[.FsEx]+(?:\s+\[\s*\d+%\])?',l.strip()) for l in lines)
freeze=json.loads((base/'source-freeze.json').read_text(encoding='utf-8'))
result['changed_frozen_files']=[name for name,sha in freeze['files'].items() if not (root/name).is_file() or hashlib.sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=sha]
result['commit_changed']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=freeze['commit']
print(json.dumps(result,ensure_ascii=True))
