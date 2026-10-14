import sys,json
from copy import deepcopy
sys.path.insert(0,'/app')
from backend.nis.engineering.communication.device_communication import communication_findings, attach_functional_device_contracts, FUNCTIONAL_DEVICE_REASONING_RULES
from backend.nis.agent.tools.services import TOOLS
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.orchestration.tool_selection import select_tools
def graph(domain='robotics'):
    nodes = {
        'sensor': {'id': 'sensor', 'name': 'Sensor1', 'device_type': 'SensorController', 'device_class': 1,
                   'identity': {'functional_device_contract': {'version': 1, 'role': 'SENSOR', 'measurement': 'image_frame', 'owner_ref': 'camera'}}},
        'camera': {'id': 'camera', 'name': 'CameraProcessing', 'device_type': 'IndustrialPC', 'device_class': 4,
                   'identity': {'functional_device_contract': {'version': 1, 'role': 'PERCEPTION', 'required_measurement': 'image_frame',
                               'input_refs': ['sensor'], 'output_signal': 'Objects'}}},
        'actuator': {'id': 'actuator', 'name': 'Valve', 'device_type': 'ActuatorController', 'device_class': 1,
                     'identity': {'functional_device_contract': {'version': 1, 'role': 'ACTUATOR', 'owner_ref': 'camera'}}},
    }
    messages = {name: {'id': name, 'interface_id': producer, 'direction': 'tx',
                      'configuration': {'transport_unit': {'producer_ref': producer, 'consumer_refs': receivers}}}
                for name, producer, receivers in [('raw', 'sensor', ['camera']), ('objects', 'camera', ['navigation']), ('command', 'camera', ['actuator'])]}
    return {'HardwareNode': nodes, 'Function': {'function': {'id': 'function', 'hardware_node_id': 'camera', 'domain': domain}},
            'Interface': {ref: {'id': ref, 'hardware_node_id': ref} for ref in nodes}, 'Message': messages,
            'Signal': {'image': {'id': 'image', 'name': 'Image', 'message_id': 'raw'},
                       'objects': {'id': 'objects', 'name': 'Objects', 'message_id': 'objects', 'configuration': {'structured_payload': {'version': 1}}},
                       'command': {'id': 'command', 'name': 'ValveCommand', 'message_id': 'command', 'configuration': {'generation_role': 'COMMAND'}},
                       'status': {'id': 'status', 'name': 'CameraStatus', 'message_id': 'command', 'semantic': {'meaning': 'Betriebszustand'}}}}
results=[]
def codes(model):
 return {f['code'] for f in communication_findings(model)}
for industry in ('automotive','robotics','aerospace','building','custom'):
 model=graph(industry)
 model['HardwareNode']['navigation']={'id':'navigation','name':'Navigator','device_class':1,'device_type':'ECU','identity':{'functional_device_contract':{'version':1,'role':'PROCESSOR','input_refs':['camera']}}}
 assert not codes(model)
 wrong=deepcopy(model);wrong['Message']['objects']['configuration']['transport_unit']['consumer_refs']=['gateway']
 assert 'FUNCTION_INPUT_ROUTE_MISSING' in codes(wrong)
 status=deepcopy(model);status['Signal']['image']['configuration']={'generation_role':'DEVICE_STATUS'}
 assert 'FUNCTION_INPUT_ROUTE_MISSING' in codes(status)
 badcommand=deepcopy(model);badcommand['Signal']['command']['configuration']={'generation_role':'MEASUREMENT'}
 assert 'ACTUATOR_COMMAND_MISSING' in codes(badcommand)
 legacy=deepcopy(model)
 for n in legacy['HardwareNode'].values():n['identity'].pop('functional_device_contract',None)
 before=deepcopy(legacy);findings=communication_findings(legacy,include_legacy=True)
 assert any(f['code']=='FUNCTIONAL_CONTRACT_REVIEW_REQUIRED' for f in findings) and legacy==before
 results.append({'industry':industry,'checks':['valid_chain','missing_intended_receiver','status_is_not_measurement','measurement_is_not_command','legacy_read_only_review']})
tool=TOOLS['validate_device_communication']
assert tool.input_model().include_legacy is True and tool.permission==Permission.VALIDATE
selected=select_tools('Kameraverarbeitung Objektdaten Fahrerassistenz Sensor Aktor Routing Simulation', [{'name':n} for n in TOOLS])
assert 'validate_device_communication' in {t['name'] for t in selected}
assert FUNCTIONAL_DEVICE_REASONING_RULES
changes=[{'object_type':'HardwareNode','local_ref':'nav','data':{'name':'Navigator','device_type':'ECU'}},{'object_type':'Function','local_ref':'nf','data':{'hardware_node_id':'$nav'}},{'object_type':'Message','local_ref':'objects','data':{'configuration':{'communication_contract':{'scope':'FUNCTION_OUTPUT'},'transport_unit':{'producer_ref':'$camera','consumer_refs':['$nav']}}}},{'object_type':'Signal','local_ref':'value','data':{'message_id':'$objects','configuration':{'generation_role':'FUNCTION_OUTPUT'}}}]
attach_functional_device_contracts(changes,[],{},enabled=True)
contract=changes[1]['data']['configuration']['functional_device_contract']
assert contract['role']=='PROCESSOR' and contract['input_refs']==['$camera']
from backend.nis.agent.orchestration.project_intake import document_segments, validate_document_interpretation
native_tool=TOOLS['interpret_project_document']
assert native_tool.permission==Permission.GENERATE_PROPOSAL
native_source='Sensorik (Kamera) \u2011 Daten\r\n'
proposal={'summary':'Quellengebundene Kategorie','components':[{'name':'Sensorik','kind':'CATEGORY','role':'SENSOR','quantity':None,'source_quote':native_source.strip()}],'technologies':[],'proposed_task':'Stueckzahl im Review klaeren','assumptions':[],'open_questions':['Wie viele Kameras sind vorgesehen?']}
accepted=validate_document_interpretation(proposal,native_source)
assert accepted['components'][0]['quantity'] is None
for key,value in [('quantity',1),('source_quote',native_source.strip().replace('\u2011','-'))]:
 invalid=deepcopy(proposal);invalid['components'][0][key]=value
 try:validate_document_interpretation(invalid,native_source)
 except ValueError:pass
 else:raise AssertionError('Invented quantity or altered source quote accepted')
long_source=('Pruefzeile \u03bc.\r\n')*900
segments=document_segments(long_source)
assert ''.join(x['text'] for x in segments)==long_source
assert segments[0]['start']==0 and segments[-1]['end']==len(long_source)
assert all(left['end']==right['start'] for left,right in zip(segments,segments[1:]))
native_checks={'registered_permission':'GENERATE_PROPOSAL','unquantified_category_kept_unknown':True,'invented_quantity_rejected':True,'changed_quotation_rejected':True,'full_contiguous_source_coverage':True,'local_model_execution':'Not invoked by this pure production probe; real full-source model acceptance is separate evidence'}
transport_source='Ethernet-Backbone. CAN-FD-Backbone.'
transport_proposal={'summary':'Registrierte Transporte','components':[],'technologies':[{'name':'Ethernet','kind':'TRANSPORT','source_quote':'Ethernet-Backbone.'},{'name':'CAN-FD','kind':'TRANSPORT','source_quote':'CAN-FD-Backbone.'}],'proposed_task':'Transportvarianten im Review erhalten','assumptions':[],'open_questions':[]}
validate_document_interpretation(transport_proposal,transport_source)
invalid=deepcopy(transport_proposal);invalid['technologies'][1]['name']='CAN'
try:validate_document_interpretation(invalid,transport_source)
except ValueError:pass
else:raise AssertionError('CAN-FD silently accepted as CAN')
native_checks['structural_transport_suffix_accepted']=True
native_checks['can_fd_not_replaced_by_can']=True
from backend.nis.agent.orchestration.project_intake import document_source_references, resolve_document_references
reference_rows=document_source_references(native_source)
assert ''.join(row['text'] for row in reference_rows)==native_source
selection=deepcopy(proposal)
selection['components']=[{'source_ref':reference_rows[0]['source_ref'],'kind':'CATEGORY','role':'SENSOR','quantity':None}]
resolved=resolve_document_references(selection,reference_rows)
assert resolved['components'][0]['source_quote']==native_source.strip()
assert resolved['components'][0]['name'] in resolved['components'][0]['source_quote']
validate_document_interpretation(resolved,native_source)
for change in ('unknown_reference','free_name','duplicate_reference'):
 invalid=deepcopy(selection)
 if change=='unknown_reference':invalid['components'][0]['source_ref']='R9999'
 elif change=='free_name':invalid['components'][0]['name']='InventedCamera'
 else:invalid['components'].append(deepcopy(invalid['components'][0]))
 try:resolve_document_references(invalid,reference_rows)
 except ValueError:pass
 else:raise AssertionError('Invalid source-reference claim accepted: '+change)
native_checks['source_name_and_quote_coupled']=True
native_checks['invalid_and_duplicate_source_references_rejected']=True
print(json.dumps({'native_document_checks':native_checks,'status':'PASSED','cases':results,'agent_tool_permission':'VALIDATE','legacy_default':True,'downstream_processor_attached':True,'mutation':'NONE; pure in-memory models only'}))
