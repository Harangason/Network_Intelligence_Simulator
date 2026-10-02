from pathlib import Path
from pprint import pformat
import runpy
data=runpy.run_path(str(Path(__file__).with_name('write-generic-can-review-spec.py')))
declarations,removed,SOURCE,REVISION=(data[k] for k in ('declarations','removed','SOURCE','REVISION'))
path=Path('backend/communication/technologies/catalog.py')
text=path.read_text(encoding='utf-8')
required=['gcan_family','gcan_transport_binding','gcan_implementation_source','gcan_schedule_source']
constraints=[]
def rule(key,when,**kwargs): constraints.append({'when':when,'parameter':key,**kwargs})
for family,formats,minimum,maximum in [('CAN_CC',['STANDARD','EXTENDED'],0,8),('CAN_FD',['STANDARD','EXTENDED'],0,64),('CAN_XL',['XL'],1,2048)]:
    rule('gcan_frame_format',{'gcan_family':family},allowed=formats)
    rule('payload_bytes',{'gcan_family':family},minimum=minimum,maximum=maximum)
    if family!='CAN_CC':
        rule('gcan_frame_kind',{'gcan_family':family},allowed=['DATA'])
        rule('gcan_requested_bytes',{'gcan_family':family},allowed=[])
    if family!='CAN_XL':
        for key in ('gcan_priority_id','gcan_acceptance_field'):
            rule(key,{'gcan_family':family},allowed=[])
rule('gcan_identifier',{'gcan_frame_format':'STANDARD'},maximum=2047)
rule('gcan_identifier',{'gcan_family':'CAN_XL'},allowed=[])
rule('payload_bytes',{'gcan_family':'CAN_CC','gcan_frame_kind':'REMOTE'},allowed=[0])
rule('gcan_requested_bytes',{'gcan_frame_kind':'DATA'},allowed=[])
rule('payload_bytes',{'gcan_family':'CAN_FD'},allowed=[*range(9),12,16,20,24,32,48,64])
sem={'rate_model':{'type':'APPLICATION_TRANSPORT_DEPENDENT','fields':[]},'required_parameters':required,
     'mechanisms':{'access':['EXPLICIT_CC_FD_XL_REGISTERED_LINK_IDENTIFIER_ARBITRATION'],
                   'integrity':['SELECTED_FAMILY_CRC_AND_STUFFING_REQUIRED'],
                   'scope':['GENERIC_WRAPPER_NOT_NEW_NORMATIVE_CAN_GENERATION']},'parameter_constraints':constraints}
text=text.replace("TECHNOLOGY_SEMANTICS['fsoe'] =",f"TECHNOLOGY_SEMANTICS['generic_can'] = {pformat(sem,width=110,sort_dicts=False)}\n\nTECHNOLOGY_SEMANTICS['fsoe'] =",1)
proposal={'kind':'CONFIGURED_TRANSPORT_PROFILE','status':'REVIEW_REQUIRED','source':SOURCE,'source_revision':REVISION,
          'note':'Generic CAN is an NIS abstraction. Actual CC/FD/XL transmitted family and lower link required; no own universal500kbit/s or8-byte proposal.'}
text=text.replace("    'fsoe':",f"    'generic_can': {proposal!r},\n    'fsoe':",1)
text=text.replace("'foundation_fieldbus_h1','fsoe'} else", "'foundation_fieldbus_h1','fsoe','generic_can'} else",1)
text=text.replace('("generic_can", "Generic CAN", "custom", "DATA_LINK", "FRAME", ("SIGNAL", "RAW_DATA"), "can_controller", (), 500_000, 8, ("multicast",), True)',
 '("generic_can", "Generic CAN", "generic_networking", "DATA_LINK", "FRAME", ("SIGNAL", "RAW_DATA"), "explicit_can_family_binding", (), None, 2048, ("multicast",), False)',1)
block=f'''    if technology_id == 'generic_can':
        source=REVIEW_RATE_PROPOSALS['generic_can']
        fields=[item for item in fields if item['key'] not in {set(removed)!r}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                    description='Actual selected CAN-family wire data field. CC, FD discrete encoded lengths and XL limits are separate; no implicit padding or payload8 default.')
        for key,kind,unit,options,minimum,maximum,meaning in {pformat(declarations,width=110)}:
            native=field(key,key.replace('gcan_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['generic_can']['required_parameters'],integer=kind=='number',
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],source_revision=source['source_revision'])
            fields.append(native)
'''
text=text.replace("    if technology_id == 'fsoe':\n",block+"    if technology_id == 'fsoe':\n",1)
path.write_text(text,encoding='utf-8')
print({'fields':len(declarations),'constraints':len(constraints)})
