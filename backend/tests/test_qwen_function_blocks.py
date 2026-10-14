"""Independent expectations for actual locally generated QWEN sources."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest

from backend.nis.simulation.signals.core.function_block import QwenFunctionBlock, EcuRuntime, validate_function_spec
from backend.nis.infrastructure.storage.saved_storage import ProjectArtifactStore, _ProjectArtifactWrite

FIXTURES = Path(__file__).parent / 'fixtures' / 'qwen_function_blocks'
def block(name):
    return json.loads((FIXTURES / (name + '.json')).read_text(encoding='utf-8'))

def specification(name='Hysteresis'):
    return {'function_block':block(name), 'block_parameters':{'lower':19., 'upper':21., 'initial':False, 'active_below':True},
        'transport_inputs':{'value':{'signal_id':'temperature', 'type':'number', 'unit':'degC',
            'max_age_ms':25., 'on_stale':'fallback', 'fallback':20.}}, 'on_invalid':'hold_output', 'invalid_output':False}

def test_qwen_hysteresis_preserves_boundaries_and_ecu_isolation():
    parameters = {'lower':19., 'upper':21., 'initial':False, 'active_below':True}
    first, other = QwenFunctionBlock(block('Hysteresis')), QwenFunctionBlock(block('Hysteresis'))
    values = [20, 18, 19, 20, 21, 22, 21, 20, 19, 18]
    assert [first.step({'value':value}, parameters, .1).value for value in values] == [False,True,True,True,True,False,False,False,False,True]
    assert other.step({'value':20}, parameters, .1).value is False
    first.reset()
    assert first.step({'value':20}, parameters, .1).value is False
    parameters['active_below'] = False
    assert [first.step({'value':value}, parameters, .1).value for value in [22,21,19,18]] == [True,True,True,False]

def test_hysteresis_rejects_inverted_or_equal_thresholds():
    for lower, upper in [(21.,19.), (20.,20.)]:
        with pytest.raises(ValueError):
            QwenFunctionBlock(block('Hysteresis')).step({'value':20},
                {'lower':lower,'upper':upper,'initial':False,'active_below':True}, .1)

def test_qwen_filter_rate_limiter_and_validity():
    filter_block = QwenFunctionBlock(block('FirstOrderFilter'))
    assert filter_block.step({'value':10}, {'tau':1.,'initial':0.}, 0).value == 0
    assert filter_block.step({'value':10}, {'tau':1.,'initial':0.}, 1).value == 5
    assert filter_block.step({'value':10}, {'tau':1.,'initial':0.}, 1).value == 7.5
    with pytest.raises(ValueError):
        filter_block.step({'value':10}, {'tau':0.,'initial':0.}, 1)
    limiter = QwenFunctionBlock(block('RateLimiter'))
    parameters = {'rise_rate':2., 'fall_rate':1., 'initial':0.}
    assert [limiter.step({'target':v}, parameters, 1).value for v in [10,10,-10,3]] == [2,4,3,3]
    validity = QwenFunctionBlock(block('ValidityGate'))
    assert validity.step({'value':42., 'valid':False}, {'fallback':-1.}, 1).value == -1
    assert validity.step({'value':42., 'valid':True}, {'fallback':-1.}, 1).value == 42
    threshold = QwenFunctionBlock(block('Threshold'))
    assert threshold.step({'value':100}, {'threshold':100,'active_below':False}, 0).value is False
    assert threshold.step({'value':101}, {'threshold':100,'active_below':False}, 0).value is True

def test_on_delay_uses_elapsed_active_time_and_exact_deadline():
    timer = QwenFunctionBlock(block('OnDelay'))
    parameters = {'delay':1.}
    assert timer.step({'active':False}, parameters, 2).value is False
    assert timer.step({'active':True}, parameters, 5).value is False, 'First active sample starts the timer; previous inactive interval is not active time'
    assert timer.step({'active':True}, parameters, .5).value is False
    assert timer.step({'active':True}, parameters, .5).value is True, 'Delay is reached at equality'
    assert timer.step({'active':False}, parameters, .1).value is False
    timer.reset()
    assert timer.step({'active':False}, {'delay':0.}, 0).value is False
    assert timer.step({'active':True}, {'delay':0.}, 0).value is True

@pytest.mark.parametrize('source', [
    'import os',
    'class X(FunctionBlock):\n def step(self, inputs, parameters, dt):\n  return eval("1")',
    'class X(FunctionBlock):\n def step(self, inputs, parameters, dt):\n  return self.__class__',
    'class X(FunctionBlock):\n def step(self, inputs, parameters, dt):\n  while True: pass',
    'class X(FunctionBlock):\n def step(self, inputs, parameters, dt):\n  return 2 ** 999999999',
    'class X(FunctionBlock):\n def step(self, inputs, parameters, dt):\n  inputs = 3\n  return 1',
])
def test_generated_code_cannot_escape_bounded_interpreter(source):
    with pytest.raises((ValueError, SyntaxError)):
        QwenFunctionBlock({'source_code':source})

def test_runtime_freezes_revision_uses_elapsed_time_and_holds_on_stale_input():
    spec = specification()
    runtime = EcuRuntime()
    value, evidence = runtime.evaluate('heating','command',spec,{'value':18},10,True)
    assert value is True and evidence['dt_s'] == 0
    value, evidence = runtime.evaluate('heating','command',spec,{'value':22},10.5,False)
    assert value is True and evidence['input_valid'] is False
    assert runtime.evaluate('different-ecu','command',spec,{'value':20},10.5,True)[0] is False
    assert runtime.evaluate('heating','command',spec,{'value':22},11,True)[0] is False
    modified = deepcopy(spec)
    modified['block_parameters']['lower'] = 18.
    with pytest.raises(ValueError, match='revision'):
        runtime.evaluate('heating','command',modified,{'value':20},12,True)

def test_binding_units_and_hash_must_match_canonical_inputs():
    spec = specification()
    assert validate_function_spec(spec, {'temperature':{'unit':'degC'}})
    with pytest.raises(ValueError, match='unit'):
        validate_function_spec(spec, {'temperature':{'unit':'m/s'}})
    spec['function_block']['source_code'] += '\n'
    with pytest.raises(ValueError, match='hash'):
        validate_function_spec(spec)

def test_revision_storage_is_scoped_immutable_and_compensates_rollback(tmp_path, monkeypatch):
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    store, neighbour = ProjectArtifactStore('project-one'), ProjectArtifactStore('project-two')
    store.write('revisions/one/snapshot.json', b'{"value":1}')
    with pytest.raises(ValueError, match='Historical'):
        store.write('revisions/one/snapshot.json', b'{"value":2}')
    for path in ['../outside','/absolute','revisions/../../outside']:
        with pytest.raises(ValueError):
            store.write(path, b'bad')
    previous = neighbour.write('manifest.json', b'neighbour')
    transaction = _ProjectArtifactWrite(store, 'logic/blocks/new/source.py', b'new', True)
    transaction.prepare()
    assert store.path(transaction.relative).read_bytes() == b'new'
    transaction.rollback()
    assert not store.path(transaction.relative).exists()
    assert neighbour.path(previous['path']).read_bytes() == b'neighbour'

def test_every_native_artifact_and_complete_values_have_run_revision(tmp_path, monkeypatch):
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path/'SAVED'))
    output = tmp_path / 'external-output'
    (output/'native').mkdir(parents=True)
    (output/'values').mkdir()
    for filename in ['sample.blf','sample.asc','sample.pcapng']:
        (output/'native'/filename).write_bytes(filename.encode())
    (output/'values/events.jsonl').write_text('{"value":18,"decision":true}\n')
    store = ProjectArtifactStore('simulation-project')
    config = {'seed':42,'parameters':{'threshold':20, 'technology_defaults':{'x':{'default':1}}}, 'scenario':{'mode':'NORMAL'}}
    before = deepcopy(config)
    run = store.begin_run('run-1', config)
    result = store.finish_run(run, output, {'status':'completed'})
    assert config == before, 'NIS originals/effective configuration remain intact'
    frozen = json.loads(store.path('runs/run-1/revision/inputs.json').read_text())
    assert frozen['configuration']['seed'] == 42
    assert 'technology_defaults' not in frozen['configuration']['parameters']
    assert len(result['artifacts']) == 4
    for artifact in result['artifacts']:
        content = store.path(artifact['path']).read_bytes()
        assert hashlib.sha256(content).hexdigest() == artifact['sha256']
    assert (output/'native/sample.blf').exists(), 'Historical original is preserved'

def test_function_executes_only_received_input_and_emits_real_trace_payload(tmp_path):
    from backend.tests.test_transport_cascades import cascade_config
    from backend.nis.simulation.hardware_profile import normalize_hardware_config
    from backend.nis.traces.universal_trace import generate_universal_events
    config = cascade_config(tmp_path, 'can_fd')
    spec = specification()
    spec['block_parameters'].update(lower=9., upper=11., active_below=False)
    spec['transport_inputs']['value'].update(signal_id='s0', unit='', max_age_ms=15.)
    spec['on_invalid'] = 'fallback'
    spec['invalid_output'] = False
    config['engineering_model']['behaviors'][0]['parameters']['value'] = 12.
    config['engineering_model']['behaviors'][1] = {'signal_id':'s1','behavior_type':'FUNCTION_BLOCK','parameters':spec,'dependencies':['s0']}
    config['engineering_model']['signals'][1].update(min_value=0,max_value=1,length_bits=1)
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    outputs = [event for event in events if event['route_id'] == 'route-1']
    assert any(e['signals'][0]['value'] == 1 for e in outputs)
    assert any(e['signals'][0]['quality'] == 'STALE_INPUT' and e['signals'][0]['value'] == 0 for e in outputs)
    good = next(e for e in outputs if e['signals'][0]['value'] == 1)
    sample = good['signals'][0]
    assert sample['dependency_evidence']['model'] == 'QWEN_FUNCTION_BLOCK_V1'
    assert sample['dependency_evidence']['inputs'][0]['source_event_id'] in {e['event_id'] for e in events}
    assert sample['received_value'] == 1
    assert int(good['payload_hex'][:2],16) & 1 == 1


def test_failed_hardware_validation_is_archived_as_failed_run(tmp_path, monkeypatch):
    from backend.nis.simulation.service import SimulationService
    from backend.nis.engineering import simulation
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path/'SAVED'))
    service = SimulationService()
    config = {'project_id':'failed-project','scenario':{'mode':'NORMAL'},'engineering_model':{}}
    monkeypatch.setattr(service, 'prepare_config', lambda *_: deepcopy(config))
    monkeypatch.setattr(simulation, 'enrich_simulation_config', lambda config,*_a,**_k:config)
    monkeypatch.setattr(service.simulator, 'run', lambda *_a,**_k:{'status':'validation_failed',
        'hardware_validation':{'valid':False,'findings':[{'severity':'error','message':'explicit model gap'}]}})
    output = tmp_path/'external-failed-run'
    output.mkdir()
    with pytest.raises(ValueError, match='Hardware-Validierung'):
        service.run({'project_id':'failed-project','simulation_job_id':'failed-run'}, output)
    store = ProjectArtifactStore('failed-project')
    manifest = json.loads(store.path('runs/failed-run/revision/manifest.json').read_text())
    assert manifest['status'] == 'FAILED'
    assert 'explicit model gap' in manifest['error']


def test_complete_project_values_are_written_even_with_native_only_formats(tmp_path):
    from backend.tests.test_transport_cascades import cascade_config
    from backend.nis.simulation.communication_simulator import run_simulation
    config = cascade_config(tmp_path, 'can_fd')
    config.update(project_id='native-values-project', formats=['blf'], model_trace_frame_limit=1,
        model_trace_signal_point_limit=1, model_trace_event_limit=1)
    for index, message in enumerate(config['engineering_model']['messages']):
        message.update(message_id_hex=hex(0x100+index), name='TestMessage'+str(index), dlc=8, configuration={})
        config['communications'][index]['arbitration_id'] = 0x100+index
    for signal in config['engineering_model']['signals']:
        signal.update(byte_order='little_endian', data_type='uint16', offset_value=0, unit='')
    result = run_simulation(config)
    events = [json.loads(line) for line in (tmp_path/'values/events.jsonl').read_text().splitlines()]
    assert len(events) > 1
    assert any(path.endswith('.blf') for path in result['artifacts']), result['native_can']
    assert any(sample.get('dependency_evidence') for event in events for sample in event.get('signals') or [])
