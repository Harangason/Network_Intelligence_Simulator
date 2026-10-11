"""Diagnostic only: replay captured rows into the launcher's disposable SQL DB."""
import cProfile
import faulthandler
import json
import os
import pstats
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

folder = Path(__file__).resolve().parent
sys.path.insert(0, str(folder.parents[2]))
stage = os.environ.get('NIS_SIZING_PROFILE_STAGE', 'before')
assert stage in {'before', 'after', 'final'}

def test_profile_captured_sizing():
    configured = os.environ['DATABASE_URL']
    assert configured == os.environ['ENGINEERING_TEST_DATABASE_URL']
    assert re.fullmatch('/nis_test_[a-z0-9_]+', urlsplit(configured).path)
    runtime = folder / 'profiling-runtime'
    os.environ.update(NIS_DATA_DIR=str(runtime), NIS_RUNTIME_DIR=str(runtime),
                      SIMULATOR_RUNTIME_ROOT=str(runtime))
    from psycopg import sql
    from psycopg.types.json import Jsonb
    from backend.nis.infrastructure.persistence.db import get_connection, close_pool
    from backend.nis.engineering.projects.project_context import activate_project, reset_project
    from backend.nis.workflow.services.service import WorkflowStatusService
    from backend.nis.engineering.capacity.sizing_service import CommunicationSizingService

    project = 'nis-diagnostic-captured-sizing'
    token = activate_project(project)
    workflow = WorkflowStatusService(project)
    workflow.get()
    with get_connection() as connection:
        table_sources = [
            ('engineering_hardware_nodes', 'hardware-nodes'),
            ('engineering_hardware_interfaces', 'hardware-interfaces'),
            ('engineering_functions', 'functions'),
            ('engineering_interfaces', 'interfaces'),
            ('engineering_messages', 'messages'),
            ('engineering_signals', 'signals'),
            ('engineering_routing_entries', 'routing'),
        ]
        for table, source in table_sources:
            rows = json.loads((folder / ('large-' + source + '-objects.json')).read_text())
            metadata = connection.execute('SELECT column_name, data_type FROM information_schema.columns WHERE table_name=%s', (table,)).fetchall()
            names = set().union(*(row.keys() for row in rows))
            columns = [item['column_name'] for item in metadata if item['column_name'] in names
                       and item['column_name'] not in {'created_at', 'modified_at', 'approved_at'}]
            json_fields = {item['column_name'] for item in metadata if item['data_type'] == 'jsonb'}
            if 'project_id' not in columns:
                columns.append('project_id')
            query = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),
                    sql.SQL(',').join(map(sql.Identifier, columns)), sql.SQL(',').join(sql.Placeholder() for _ in columns))
            values = [[project if key == 'project_id' else Jsonb(row.get(key)) if key in json_fields else row.get(key)
                       for key in columns] for row in rows]
            connection.cursor().executemany(query, values)
            print('seeded', table, len(rows), flush=True)
        state = json.loads((folder / 'large-workflow-captured.json').read_text())
        parameters = json.loads((folder / 'large-parameters-captured.json').read_text())['parameters']
        topology = json.loads((folder / 'large-topology-captured.json').read_text())['topology']
        connection.execute('UPDATE engineering_workflow_projects SET parameters=%s, topology=%s, statuses=%s, versions=%s WHERE project_id=%s',
                           (Jsonb(parameters), Jsonb(topology), Jsonb(state['statuses']), Jsonb(state['versions']), project))
    profiler = cProfile.Profile()
    sizing = CommunicationSizingService(project)
    start = time.perf_counter()
    stacks = (folder / ('sizing-' + stage + '-stacks.txt')).open('w')
    faulthandler.dump_traceback_later(30, repeat=True, file=stacks)
    try:
        profiler.enable()
        preview = sizing.preview()
        print('preview seconds', time.perf_counter() - start, 'changes', len(preview['changes']), flush=True)
        result = sizing.apply(preview['source_token'], approve_valid=True)
        print('apply result', result['changed_messages'], result['changed_routes'], flush=True)
        (folder / ('sizing-' + stage + '-result.json')).write_text(json.dumps({
            'elapsed_seconds': time.perf_counter() - start,
            'changed_messages': result['changed_messages'], 'changed_routes': result['changed_routes'],
            'valid_routes': result['valid_routes'], 'invalid_routes': result['invalid_routes'],
            'plan_status': result['plan']['status'],
        }), encoding='utf-8')
    finally:
        profiler.disable()
        faulthandler.cancel_dump_traceback_later()
        stacks.close()
        profiler.dump_stats(str(folder / ('sizing-' + stage + '.prof')))
        with (folder / ('sizing-' + stage + '-profile.txt')).open('w') as stream:
            pstats.Stats(profiler, stream=stream).sort_stats('cumulative').print_stats(45)
        print((folder / ('sizing-' + stage + '-profile.txt')).read_text(), flush=True)
        reset_project(token)
        close_pool()
