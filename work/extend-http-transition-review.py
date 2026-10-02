"""Add source-required HTTP semantic and transition conditions to the current review once."""
import ast
from pathlib import Path
from pprint import pformat
new=[
 ('http_transition_token','select',None,['TLS','WEBSOCKET','CONNECT_UDP','CONNECT_IP','CONNECT_TCP','DEVICE_SPECIFIC'],None,None,'Actual upgrade/CONNECT protocol, unknown. RFC9931 distinguishes TLS, WebSocket, UDP/IP tunneling and untrusted TCP CONNECT; source alone does not override prohibited optimistic sending.'),
 ('http_connect_untrusted','boolean',None,None,None,None,'Actual CONNECT forwarding on behalf of untrusted TCP client, unknown. Do not assume trusted false; wait-success or Connection:close required for HTTP1.'),
 ('http_wait_success','boolean',None,None,None,None,'Actual proxy waits for successful2xx before forwarding TCP payload, unknown. Distinct from application deadline and declared source text.'),
 ('http_connection_close','boolean',None,None,None,None,'Actual Connection:close request/rejection connection behavior. HTTP1 untrusted CONNECT requires close or wait; rejecting proxy must close underlying connection under RFC9931.'),
 ('http_transition_rejected','boolean',None,None,None,None,'Actual CONNECT transition rejection state, unknown. Underlying connection must be closed by HTTP1 rejecting proxy without processing further requests.')]
writer=Path('work/write-http-review-spec.py')
s=writer.read_text(encoding='utf-8')
s=s.replace("removed={",'declarations.extend('+pformat(new,width=110)+')\nremoved={',1)
writer.write_text(s,encoding='utf-8')
rules=[
 {'when':{'http_message_kind':'RESPONSE'},'when_not':{'http_method':'HEAD','http_status':304},'parameter':'http_length_semantics','allowed':['MESSAGE_BODY']},
 {'when':{'http_transition_optimistic':True},'parameter':'http_transition_token','required':True},
 {'when':{'http_transition_token':'WEBSOCKET'},'parameter':'http_transition_optimistic','allowed':[False]},
 *[{'when':{'http_version':'HTTP_1_1','http_transition_token':token},'parameter':'http_transition_optimistic','allowed':[False]} for token in ('CONNECT_UDP','CONNECT_IP')],
 {'when':{'http_version':'HTTP_1_1','http_transition_token':'CONNECT_TCP','http_connect_untrusted':True},'when_not':{'http_connection_close':True},'parameter':'http_wait_success','required':True,'allowed':[True]},
 {'when':{'http_version':'HTTP_1_1','http_transition_token':'CONNECT_TCP','http_transition_rejected':True,'http_role':'PROXY'},'parameter':'http_connection_close','required':True,'allowed':[True]},
 {'when':{'http_version':'HTTP_3','http_role':'CLIENT'},'parameter':'http3_frame_type','forbidden':['5']},
 {'when':{'http_version':'HTTP_3','http_role':'SERVER'},'parameter':'http3_frame_type','forbidden':['13']},
]
path=Path('backend/communication/technologies/catalog.py');s=path.read_text(encoding='utf-8')
a=s.index("TECHNOLOGY_SEMANTICS['http'] =");b=s.index("TECHNOLOGY_SEMANTICS['hart'] =",a)
sem=ast.literal_eval(s[a:b].split('=',1)[1].strip())
sem['parameter_constraints'].extend(rules)
for item in sem['parameter_constraints']:
    if item['parameter']=='http_body_bytes' and item.get('allowed')==['0']:
        item.pop('allowed');item['pattern']=r'0+'
s=s[:a]+"TECHNOLOGY_SEMANTICS['http'] = "+pformat(sem,width=110,sort_dicts=False)+'\n\n'+s[b:]
# Insert extra form declarations directly before the shared append, scoped to HTTP's block.
a=s.index("    if technology_id == 'http':\n        source=");b=s.index("    if technology_id == 'hart':\n        source=",a)
block=s[a:b]
addition=f'''        for key,kind,unit,options,minimum,maximum,meaning in {pformat(new,width=110)}:
            native=field(key,key.replace('http_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=False,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',
                source='https://www.rfc-editor.org/rfc/rfc9931.html',source_revision='RFC9931 March2026 sections6/8')
            fields.append(native)
'''
s=s[:a]+block+addition+s[b:]
path.write_text(s,encoding='utf-8')
# Keep the one-shot applier reproducible if the original before snapshot is ever restored.
applier=Path('work/apply-http-review.py');s=applier.read_text(encoding='utf-8')
s=s.replace("sem={'rate_model':",'constraints.extend('+pformat(rules,width=110)+')\n'+"sem={'rate_model':",1)
applier.write_text(s,encoding='utf-8')
