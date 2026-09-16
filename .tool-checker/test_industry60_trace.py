"""Fresh observation probes. Synthetic inputs are labelled, never simulation evidence."""
import asyncio, copy, json, time
from pathlib import Path
from uuid import uuid4
import pytest
pytest_plugins=['backend.tests.conftest']
OUT=Path(__file__).resolve().parent/'evidence/industry60/trace'
def save(name,data):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')

def test_simulator_gateway_trace_probe(monkeypatch):
    from backend.tests.test_transport_integrity import gateway_config
    from hardware_profile import normalize_hardware_config
    from universal_trace import generate_universal_events
    from backend.app.runtime_analysis import analyze_runtime_trace
    cfg=gateway_config.__wrapped__(monkeypatch)
    cfg.update(duration_s=18,max_events=20000,seed=42)
    # Explicit CAN-FD -> Ethernet variant of the existing two-hop fixture.
    def ethernet(value):
        if isinstance(value,dict): return {k:ethernet(v) for k,v in value.items()}
        if isinstance(value,list): return [ethernet(v) for v in value]
        if value=='LIN':return 'Ethernet'
        if value=='lin':return 'ethernet'
        if value==19200:return 100000000
        return value
    cfg=ethernet(cfg)
    traces={}
    for label in ['golden','repeat','fault']:
        current=copy.deepcopy(cfg)
        if label=='fault':current['scenario']={'mode':'USER_DEFINED_FAULT','faults':[{'scope':'NETWORK','type':'GATEWAY_DELAY','target':{'id':'gateway'},'start_s':12,'end_s':15,'delay_ms':100}]}
        events=generate_universal_events(current,normalize_hardware_config(current),start_utc=1700000000)[1]
        traces[label]=events
        save(label+'-config.json',current)
        save(label+'-events.json',events)
        save(label+'-metrics.json',analyze_runtime_trace({'model_simulation':{'frames':events}},current))
    save('generation-summary.json',{'origin':'Real simulator on explicit config; config builder model reads stubbed. Not canonical snapshot E2E.',
        'reproducible':traces['golden']==traces['repeat'],'counts':{k:len(v) for k,v in traces.items()},
        'max_queue':max(e.get('queue_depth_estimate',0) or 0 for e in traces['fault']),
        'sample':traces['fault'][:2]})
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.simulator_engineering_mcp.server import create_server
    from backend.engineering.agent_tools.runtime import ToolAuthority
    async def probe():
        async with EngineeringMCPClient(create_server(ToolAuthority('nis-e2e-industry60-trace-'+uuid4().hex))) as client:
            calls={}
            for label,name,args in [
                ('load','load_trace',{'events':traces['fault'],'start_s':12,'end_s':13,'limit':20}),
                ('compare','compare_golden_trace',{'events':traces['fault'],'golden_events':traces['golden']}),
                ('root-cause','find_trace_root_cause',{'events':traces['fault'],'configuration':cfg}),
                ('missing-time','load_trace',{'events':[{'message_id':'missing-time'}]}),
                ('bad-time','load_trace',{'events':[{'time_s':'not-a-time'}]}),
            ]:
                calls[label]={'tool':name,'result':(await client.call(name,args)).model_dump(mode='json')}
            save('mcp-inline.json',calls)
    asyncio.run(probe())

def test_large_trace_window_probe(tmp_path):
    from universal_trace import write_jsonl
    from backend.app.trace_service import read_trace_window
    events=[{'time_s':i/1000,'sequence':i,'source':'src','destination':'dst','network':'test-net','technology':'CAN_FD','message_id':'MotorStatus','route_id':'route-test'} for i in range(100501)]
    path=tmp_path/'large.jsonl';write_jsonl(path,events)
    start=time.monotonic();late=read_trace_window(path,start_s=99,end_s=100,limit=500)
    page2=read_trace_window(path,cursor=late['next_cursor'],start_s=99,end_s=100,limit=500)
    save('large-window.json',{'origin':'100501 synthetic paging-fixture events, not simulator output','event_count':len(events),'duration_seconds':time.monotonic()-start,'first':late,'second':page2})
    assert len(late['events'])==500 and late['events'][0]['sequence']==99000
