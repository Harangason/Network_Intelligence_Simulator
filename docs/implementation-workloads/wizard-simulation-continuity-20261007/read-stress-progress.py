import json,subprocess,sys
docker='C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
container=sys.argv[1]
assert container.startswith('nis-test-db-')
assert subprocess.check_output([docker,'inspect',container,'--format','{{ index .Config.Labels "networkis.test" }}'],text=True).strip()=='disposable'
database='nis_test_'+container.removeprefix('nis-test-db-')
query="""SELECT json_build_object('project',project_id,'statuses',statuses,'versions',versions,'updated',updated_at)
 FROM engineering_workflow_projects WHERE project_id LIKE '%pytest-wizard-full-routing%'
 ORDER BY updated_at DESC LIMIT 1"""
print(subprocess.check_output([docker,'exec',container,'psql','-U','nis_test','-d',database,'-At','-c',query],text=True).strip())
