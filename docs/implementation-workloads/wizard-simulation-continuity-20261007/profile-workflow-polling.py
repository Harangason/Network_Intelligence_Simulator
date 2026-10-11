"""Diagnostic frozen SQL replay; run only through run-isolated-tests.py.

Load backend.tests.conftest as a plugin. This measurement is not a full release
or independent campaign result and never targets the live product database.
"""
import cProfile,hashlib,json,os,pstats,shutil,time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

def test_frozen_workflow_polling(tmp_path,monkeypatch):
    approved=os.environ['ENGINEERING_TEST_DATABASE_URL']
    assert os.environ['DATABASE_URL']==approved
    assert urlsplit(approved).path.startswith('/nis_test_')
    out=Path(__file__).parent.resolve();phase=os.environ.get('NIS_PROFILE_PHASE','before')
    assert phase in ('before','after')
    fixture=json.loads((out/'workflow-polling-frozen-fixture.json').read_text(encoding='utf-8'))
    from backend.nis.infrastructure.persistence.db import get_connection
    from backend.nis.infrastructure.storage import saved_storage
    from backend.nis.workflow.services import service
    project=fixture['engineering_workflow_projects'][0]['project_id']
    assert project=='nis-e2e-large-efbde825-d726-46c0-af82-d85123f578e8'
    monkeypatch.setattr(saved_storage,'saved_root',lambda:tmp_path)
    folder=saved_storage.project_folder(project);folder.mkdir()
    shutil.copyfile(out/'workflow-polling-user-defined-values.json',folder/'user_defined_values.json')
    with get_connection() as connection:
        for table,rows in fixture.items():
            assert table.startswith('engineering_') and table.isidentifier()
            connection.execute('INSERT INTO '+table+' SELECT * FROM json_populate_recordset(NULL::'+table+', %s::json)',
                (json.dumps(rows),))
    workflow=service.WorkflowStatusService(project)
    baseline=workflow.get(summary=True)
    assert baseline['context']['agent_execution']['state']=='COMPLETED'
    for name in ('engineering_model','routing','network_editor','parameters'):
        assert baseline['artifact_checks'][name]['complete'], name
    assert baseline['artifact_checks']['engineering_model']['counts']['signals']==1404
    assert baseline['artifact_checks']['routing']['counts']['total']==766
    sql=[]
    class Cursor:
        def __init__(self,cursor,item):self.cursor,self.item=cursor,item
        def __getattr__(self,key):return getattr(self.cursor,key)
        def fetchone(self):
            started=time.perf_counter()
            try:return self.cursor.fetchone()
            finally:self.item['seconds']+=time.perf_counter()-started
        def fetchall(self):
            started=time.perf_counter()
            try:return self.cursor.fetchall()
            finally:self.item['seconds']+=time.perf_counter()-started
    class Connection:
        def __init__(self,connection):self.connection=connection
        def __getattr__(self,key):return getattr(self.connection,key)
        def execute(self,query,*args,**kwargs):
            item={'sql':' '.join(query.split()),'seconds':0};sql.append(item)
            started=time.perf_counter()
            try:return Cursor(self.connection.execute(query,*args,**kwargs),item)
            finally:item['seconds']+=time.perf_counter()-started
    original=service.get_connection
    @contextmanager
    def measured_connection():
        with original() as connection:yield Connection(connection)
    monkeypatch.setattr(service,'get_connection',measured_connection)
    profiler=cProfile.Profile();durations=[]
    for _ in range(3):
        started=time.perf_counter();result=profiler.runcall(workflow.get,summary=True)
        durations.append(time.perf_counter()-started)
        assert result==baseline
    profiler.dump_stats(str(out/f'workflow-polling-{phase}.prof'))
    with (out/f'workflow-polling-{phase}-profile.txt').open('w',encoding='utf-8') as stream:
        pstats.Stats(profiler,stream=stream).sort_stats('cumulative').print_stats(55)
    encoded=json.dumps(baseline,sort_keys=True,default=str).encode()
    if phase=='after':
        assert encoded==(out/'workflow-polling-before-state.json').read_bytes()
    proof={'coverage':'ISOLATED_FROZEN_WORKFLOW_SUMMARY_REPLAY_NOT_RELEASE_PASS',
        'phase':phase,'seconds':durations,'identical_results':True,
        'state_sha256':hashlib.sha256(encoded).hexdigest(),'sql':sql}
    (out/f'workflow-polling-{phase}-result.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    (out/f'workflow-polling-{phase}-state.json').write_bytes(encoded)
    print(json.dumps({key:proof[key] for key in ('coverage','phase','seconds','identical_results','state_sha256')}))
