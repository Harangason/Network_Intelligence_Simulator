import json, subprocess
from pathlib import Path
out=Path(__file__).parent
docker='C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
container='nis-e2e-db-999af6c2d1bb'
assert subprocess.check_output([docker,'inspect',container,'--format','{{ index .Config.Labels "networkis.test" }}'],text=True).strip()=='disposable'
query="""SELECT json_build_object('project',project_id,'snapshot',id,
'assessment',(result->'assessment')-'scope_coverage',
'duration',configuration->'duration_s',
'duration_origin',configuration->'parameters'->'parameter_provenance'->'duration_s',
'observation',(configuration->'observation_window')-'routes',
'unevaluated',(SELECT jsonb_agg(r) FROM jsonb_array_elements(result->'runtime_metrics'->'routes') r WHERE r->>'status'='NOT_EVALUATED'))
FROM engineering_simulation_snapshots WHERE project_id='nis-e2e-large-f7bf8eea-cc00-46ab-975f-040f36d49cf5' ORDER BY created_at DESC LIMIT 1"""
proof=json.loads(subprocess.check_output([docker,'exec',container,'psql','-U','nis_test','-d','nis_test_e2e','-At','-c',query],text=True))
assert proof['assessment']['unevaluated_route_count']==5
assert proof['observation']['source']=='EXPLICIT_PARAMETERS'
assert proof['observation']['requirement_minimum_duration_s']==1.071
(out/'observation-failure.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
config_query="""SELECT configuration FROM engineering_simulation_snapshots
WHERE project_id='nis-e2e-large-f7bf8eea-cc00-46ab-975f-040f36d49cf5' ORDER BY created_at DESC LIMIT 1"""
config=json.loads(subprocess.check_output([docker,'exec',container,'psql','-U','nis_test','-d','nis_test_e2e','-At','-c',config_query],text=True))
(out/'observation-frozen-configuration.json').write_text(json.dumps(config),encoding='utf-8')
print(json.dumps({key:proof[key] for key in ['duration','duration_origin','observation']},ensure_ascii=False))
