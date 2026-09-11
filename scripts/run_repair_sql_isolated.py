import os,json,subprocess,sys
from pathlib import Path
docker=r'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
info=json.loads(subprocess.check_output([docker,'inspect','NetworkIS'],text=True))[0]
env=os.environ.copy(); env['DATABASE_URL']=next(s.split('=',1)[1] for s in info['Config']['Env'] if s.startswith('DATABASE_URL='))
network=next(iter(info['NetworkSettings']['Networks']))
script=sys.argv[1] if len(sys.argv)>1 else 'verify_communication_repair_sql.py'
assert script in {'verify_communication_repair_sql.py','verify_function_architecture_sql.py', 'verify_assistant_sql.py', 'verify_routing_scope_sql.py', 'verify_routing_scope_baseline.py'}
cmd=[docker,'run','--rm','--network',network,'-e','DATABASE_URL','-v',str(Path.cwd())+':/work:ro','--tmpfs','/work/backend/runtime','-w','/work','--entrypoint','/bin/sh',info['Config']['Image'],'-c','python -m pip install --quiet --disable-pip-version-check --root-user-action=ignore --target /tmp/testdeps pytest && PYTHONPATH=/tmp/testdeps:/work python scripts/'+script]
raise SystemExit(subprocess.call(cmd,env=env))

