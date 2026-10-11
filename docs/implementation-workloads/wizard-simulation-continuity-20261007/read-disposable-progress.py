import json,subprocess,sys
from pathlib import Path
docker='C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
receipt_path=Path(sys.argv[1]).resolve()
assert receipt_path.is_relative_to(Path(__file__).parent.resolve()/'performance-stack')
receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
container=receipt['containers']['db']
assert container.startswith('nis-e2e-db-')
assert subprocess.check_output([docker,'inspect',container,'--format','{{ index .Config.Labels "networkis.test" }}'],text=True).strip()=='disposable'
query="""SELECT json_build_object('project', project_id, 'statuses',statuses,
    'execution',context->'agent_execution', 'parameter_revision', versions->'parameters',
    'seed',parameters->'seed') FROM engineering_workflow_projects
    WHERE project_id LIKE '%nis-e2e-large-%' ORDER BY updated_at DESC LIMIT 1"""
result=subprocess.check_output([docker,'exec',container,'psql','-U','nis_test','-d','nis_test_e2e','-At','-c',query],text=True).strip()
print(result or json.dumps({'large_project':'not_started'}))
