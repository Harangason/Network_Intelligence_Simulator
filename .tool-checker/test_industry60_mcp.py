"""Observation probes, not product-PASS assertions. SQL isolated by launcher."""
import asyncio, json, os
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
pytest_plugins=['backend.tests.conftest']
OUT=Path(os.environ.get(
    'TOOL_CHECKER_EVIDENCE_ROOT',
    str(Path(__file__).resolve().parent/'evidence/industry60'),
))/'mcp'

def test_observe_registered_protocol_and_failures():
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.simulator_engineering_mcp.server import create_server
    from backend.engineering.agent_tools.runtime import ToolAuthority
    from backend.engineering.agent_tools.services import TOOLS
    async def run():
        output={}; server=create_server(ToolAuthority('nis-e2e-industry60-mcp-'+uuid4().hex))
        async with EngineeringMCPClient(server) as client:
            raw=await client.client.list_tools()
            output['wire_registry']=[t.model_dump(mode='json') for t in raw.tools]
            output['agent_registry']=await client.tools()
            output['core_permissions']={name:str(t.permission) for name,t in TOOLS.items()}
            calls=[('unknown','nonexistent_industry60_capability',{}),
                ('invalid','calculate_message_size',{'technology':'CAN_FD','payload_bytes':-2}),
                ('unsupported','calculate_message_size',{'technology':'INDUSTRY60_UNKNOWN','payload_bytes':1}),
                ('bits','calculate_signal_bit_length',{'signal':{'name':'MotorRPM','min_value':0,'max_value':5000,'factor':50,'offset_value':0,'unit':'rpm','data_type':'unsigned','length_bits':4}}),
                ('encoding','resolve_signal_encoding',{'signal':{'name':'MotorRPM','min_value':0,'max_value':5000,'factor':50,'offset_value':0,'unit':'rpm','data_type':'unsigned','length_bits':4}}),
                ('validation','validate_signal',{'signal':{'name':'MotorRPM','min_value':0,'max_value':5000,'factor':50,'offset_value':0,'unit':'rpm','data_type':'unsigned','length_bits':4}}),
                ('capabilities','inspect_assistant_capabilities',{})]
            for label,name,args in calls:
                try: output[label]={'tool':name,'arguments':args,'result':(await client.call(name,args)).model_dump(mode='json')}
                except Exception as exc: output[label]={'tool':name,'arguments':args,'exception':type(exc).__name__,'message':str(exc)}
            original=client.client.call_tool
            client.client.call_tool=AsyncMock(side_effect=TimeoutError('scripted transient transport timeout'))
            try: output['timeout']={'result':(await client.call('inspect_project',{})).model_dump(mode='json')}
            except Exception as exc: output['timeout']={'exception':type(exc).__name__,'message':str(exc),'fault_injection':'client transport only; no domain writes'}
            finally: client.client.call_tool=original
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'protocol.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    asyncio.run(run())

def test_observe_full_channel_rejection():
    from backend.engineering.goal_execution.graph import ModelGraphService
    from backend.engineering.goal_execution.ports import inspect_port_decision
    from backend.tests.test_goal_execution import graph_fixture
    model,resources=graph_fixture()
    resources['CommunicationController'][0].update(max_channels=2,active_channels=[1,2])
    resources['CommunicationCapability'][0].update(max_channels=2,max_ports=2)
    result=inspect_port_decision(ModelGraphService(model,resources),'adas','CAN_FD','can')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'full-channels.json').write_text(json.dumps({'model':model,'resources':resources,'result':result},ensure_ascii=False,indent=2),encoding='utf-8')
