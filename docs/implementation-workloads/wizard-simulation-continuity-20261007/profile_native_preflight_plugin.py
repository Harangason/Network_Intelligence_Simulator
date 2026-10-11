"""Replay captured browser SQL only inside run-isolated-tests; diagnostic, not PASS."""
import importlib.util,json,os,subprocess,sys,time
from pathlib import Path
from urllib.parse import urlsplit
import pytest

@pytest.fixture(autouse=True)
def captured_native_preflight(request, isolated_project_context):
    if request.node.name != 'test_lin_simulation_defaults_never_fabricate_device_ids_or_evidence_sources':
        return
    out=Path(__file__).parent
    parts=urlsplit(os.environ['DATABASE_URL'])
    assert os.environ['DATABASE_URL']==os.environ['ENGINEERING_TEST_DATABASE_URL']
    database=parts.path.lstrip('/');assert database.startswith('nis_test_')
    container='nis-test-db-'+database.removeprefix('nis_test_')
    docker='C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
    assert subprocess.check_output([docker,'inspect',container,'--format','{{ index .Config.Labels "networkis.test" }}'],text=True).strip()=='disposable'
    with (out/'native-preflight-browser.sql').open('rb') as source:
        restored=subprocess.run([docker,'exec','-i',container,'psql','-U','nis_test','-d',database,'-v','ON_ERROR_STOP=1'],stdin=source,capture_output=True)
    assert restored.returncode==0,restored.stderr.decode()[-2000:]
    from backend.nis.engineering.projects.project_context import activate_project,reset_project
    from backend.nis.engineering.capacity import service
    from backend.nis.engineering.capacity.sizing_service import CommunicationSizingService
    captured=json.loads((out/'native-preflight-browser-input.json').read_text())
    project=captured['project'];token=activate_project(project)
    try:
        spec=importlib.util.spec_from_file_location('captured_previous_capacity',out/'pre-native-configuration-capacity.py')
        baseline=importlib.util.module_from_spec(spec);sys.modules[spec.name]=baseline;spec.loader.exec_module(baseline)
        results=[]
        for label,module in [('before',baseline),('after',service)]:
            started=time.perf_counter()
            result=module.CapacityTimingService(project).calculate(persist=False)
            (out/f'native-preflight-capacity-{label}.json').write_text(json.dumps(result,default=str),encoding='utf-8')
            networks=result['results']['networks']
            unresolved=[{'network_id':row['network_id'],'name':row['network_name'],
                'schedule':row.get('simulation_communication_schedule'),
                'simulation_capacity_verified':row.get('simulation_capacity_verified')}
                for row in networks if (row.get('simulation_communication_schedule') or {}).get('status') not in {'FEASIBLE_UNDER_ASSUMPTIONS','EMPTY'}]
            record={'label':label,'elapsed_s':time.perf_counter()-started,'networks':len(networks),'unresolved':unresolved}
            results.append(record);print(json.dumps(record,default=str),flush=True)
        preview=CommunicationSizingService(project).preview()
        (out/'native-preflight-sizing-preview.json').write_text(json.dumps(preview,default=str),encoding='utf-8')
        if preview['changes']:
            applied=CommunicationSizingService(project).apply(preview['source_token'], approve_valid=True)
            result=service.CapacityTimingService(project).calculate(persist=False)
            (out/'native-post-split-sized-capacity.json').write_text(json.dumps(result,default=str),encoding='utf-8')
            unresolved=[{'network_id':row['network_id'],'schedule':row.get('simulation_communication_schedule')}
                for row in result['results']['networks'] if (row.get('simulation_communication_schedule') or {}).get('status') not in {'FEASIBLE_UNDER_ASSUMPTIONS','EMPTY'}]
            record={'label':'post_split_sized','changed_messages':applied['changed_messages'],
                    'invalid_routes':applied['invalid_routes'],'unresolved':unresolved}
            results.append(record);print(json.dumps(record,default=str),flush=True)
        (out/'native-preflight-diagnostic.json').write_text(json.dumps(results,indent=2,default=str),encoding='utf-8')
    finally:
        reset_project(token)
    pytest.fail('DIAGNOSTIC COMPLETE: restored captured SQL inspected; not a passing regression.')
