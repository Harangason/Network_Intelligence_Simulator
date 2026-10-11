import hashlib,json,subprocess
from pathlib import Path
out=Path(__file__).parent.resolve()
docker='C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
db='nis-e2e-db-860f9d4a7375';app='nis-e2e-app-860f9d4a7375'
project='nis-e2e-large-efbde825-d726-46c0-af82-d85123f578e8'
for name in (db,app):
    assert subprocess.check_output([docker,'inspect',name,'--format','{{index .Config.Labels "networkis.test"}}'],text=True).strip()=='disposable'
tables=['engineering_workflow_projects','engineering_hardware_nodes','engineering_functions',
 'engineering_hardware_interfaces','engineering_interfaces','engineering_messages','engineering_signals',
 'engineering_routing_entries','engineering_analysis_snapshots']
query='SELECT json_build_object('+','.join("'"+table+"',(SELECT COALESCE(json_agg(t),'[]'::json) FROM "+table+" t WHERE project_id='"+project+"')" for table in tables)+')'
fixture=json.loads(subprocess.check_output([docker,'exec',db,'psql','-U','nis_test','-d','nis_test_e2e','-At','-c',query],text=True))
target=out/'workflow-polling-frozen-fixture.json'
target.write_text(json.dumps(fixture),encoding='utf-8')
env=json.loads(subprocess.check_output([docker,'inspect',app,'--format','{{json .Config.Env}}'],text=True))
settings=dict(item.split('=',1) for item in env)
assert not settings.get('SIMULATOR_SAVED_ROOT') and not settings.get('SIMULATOR_RUNTIME_ROOT')
assert settings.get('NIS_DATA_DIR')=='/app/var/data'
copied=out/'workflow-polling-user-defined-values.json'
subprocess.run([docker,'cp',app+':/app/var/data/projects/'+project+'/user_defined_values.json',str(copied)],check=True,capture_output=True)
proof={'source_project':project,'coverage':'READ_ONLY_FROZEN_TEST_FIXTURE_NOT_RELEASE_PASS',
 'fixture_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size,
 'counts':{table:len(rows) for table,rows in fixture.items()},
 'user_values_sha256':hashlib.sha256(copied.read_bytes()).hexdigest()}
(out/'workflow-polling-frozen-fixture-evidence.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps(proof))
