from pathlib import Path
from pprint import pformat
import runpy
data=runpy.run_path(str(Path(__file__).with_name('write-gpio-review-spec.py')))
declarations,removed,SOURCE,REVISION=(data[k] for k in ('declarations','removed','SOURCE','REVISION'))
path=Path('backend/communication/technologies/catalog.py')
text=path.read_text(encoding='utf-8')
required=['gpio_profile','gpio_pin','gpio_device_source','gpio_wiring_source','gpio_direction']
constraints=[]
def rule(key,when=None,**kwargs): constraints.append({'when':when or {},'parameter':key,**kwargs})
st={'gpio_profile':'STM8TL5_RM0312_3'}
reset={**st,'gpio_phase':'RESET','gpio_reset_exception':False}
rule('gpio_direction',reset,allowed=['DIGITAL_INPUT'])
rule('gpio_pull',reset,allowed=['NONE'])
rule('gpio_pull',st,allowed=['NONE','UP'])
rule('gpio_drive',{'gpio_direction':'DIGITAL_INPUT'},allowed=[])
rule('gpio_input_mode',{'gpio_direction':'DIGITAL_OUTPUT'},allowed=[])
rule('gpio_event',{'gpio_direction':'DIGITAL_OUTPUT'},allowed=[])
rule('gpio_pull',{**st,'gpio_direction':'DIGITAL_OUTPUT'},allowed=['NONE'])
for key in ('gpio_source_load_ma','gpio_sink_load_ma'):
    rule(key,{'gpio_direction':'DIGITAL_INPUT'},allowed=[])
for drive in ('PSEUDO_OPEN_DRAIN','TRUE_OPEN_DRAIN'):
    rule('gpio_pull_source',{'gpio_direction':'DIGITAL_OUTPUT','gpio_drive':drive},required=True)
rule('gpio_event',{'gpio_input_mode':'POLLED'},allowed=[])
rule('gpio_vdd_v',exclusive_minimum=0)
rule('gpio_pull_ohms',exclusive_minimum=0)
rule('gpio_vil_max_v',maximum_parameter='gpio_vih_min_v')
rule('gpio_vol_max_v',maximum_parameter='gpio_vil_max_v')
rule('gpio_voh_min_v',minimum_parameter='gpio_vih_min_v')
rule('gpio_sink_load_ma',maximum_parameter='gpio_sink_bound_ma')
rule('gpio_source_load_ma',maximum_parameter='gpio_source_bound_ma')
sem={'rate_model':{'type':'DIRECT_IO_NO_PACKET_RATE','fields':[]},'required_parameters':required,'native_parameter_prefixes':['gpio_'],
     'mechanisms':{'access':['ACTUAL_PIN_MODE_AND_REGISTER_TASK_INTERRUPT_SCHEDULE'],
                   'integrity':['ACTUAL_VOLTAGE_THRESHOLD_CURRENT_LOAD_AND_NOISE_EVIDENCE'],
                   'scope':['LOCAL_DIGITAL_IO_NOT_FRAMED_BUS']},'parameter_constraints':constraints}
text=text.replace("TECHNOLOGY_SEMANTICS['goose'] =",f"TECHNOLOGY_SEMANTICS['gpio'] = {pformat(sem,width=110,sort_dicts=False)}\n\nTECHNOLOGY_SEMANTICS['goose'] =",1)
proposal={'kind':'ACTUAL_DEVICE_NO_PACKET_RATE','status':'REVIEW_REQUIRED','source':SOURCE,'source_revision':REVISION,
          'note':'GPIO has no standard packet speed/voltage/timing. Qualified STM8TL5 non-exception reset input/no-pull proposal is conditional; programmed outputs and real pin/peer evidence remain actual.'}
text=text.replace("    'goose':",f"    'gpio': {proposal!r},\n    'goose':",1)
text=text.replace("'fsoe','generic_can','generic_serial'} else", "'fsoe','generic_can','generic_serial','gpio'} else",1)
text=text.replace('("gpio", "GPIO", "embedded_systems", "PHYSICAL", "PROCESS_DATA", ("SIGNAL", "STATUS"), "gpio_port", (), None, 1, (), True)',
 '("gpio", "GPIO", "generic_networking", "PHYSICAL", "PROCESS_DATA", ("SIGNAL", "STATUS"), "gpio_port", (), None, None, (), False)',1)
local='''    if technology_id == 'gpio':
        fields.append({'key':'update_bound_ms','label':'Output-update bound (ms)','numeric':True,'boolean':False,'optional':True})
        conditions={'sample_bound_ms':{'gpio_direction':'DIGITAL_INPUT','gpio_input_mode':'POLLED'},
                    'debounce_bound_ms':{'gpio_debounce_enabled':True},
                    'edge_detection_bound_ms':{'gpio_direction':'DIGITAL_INPUT','gpio_input_mode':'INTERRUPT'},
                    'update_bound_ms':{'gpio_direction':'DIGITAL_OUTPUT'}}
        source=REVIEW_RATE_PROPOSALS['gpio']
        for item in fields:
            item.update(unit='ms',minimum=0,optional=True,required_when=conditions[item['key']],
                        parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',scope='device',
                        source=source['source'],source_revision=source['source_revision'],
                        description='Actual matching pin/task/interrupt/debounce/update timing bound, not a bus rate or generic period. Confirm only with actual datasheet/measurement source.')
'''
text=text.replace("    if technology_id == 'adc':\n",local+"    if technology_id == 'adc':\n",1)
block=f'''    if technology_id == 'gpio':
        source=REVIEW_RATE_PROPOSALS['gpio']
        fields=[item for item in fields if item['key'] not in {set(removed)!r}]
        for key,kind,unit,options,minimum,maximum,meaning in {pformat(declarations,width=110)}:
            native=field(key,key.replace('gpio_','').replace('_',' '),'physical','device',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['gpio']['required_parameters'],
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],source_revision=source['source_revision'])
            if key in {{'gpio_direction','gpio_pull'}}:
                native.update(conditional_defaults=[{{'when':{{'gpio_profile':'STM8TL5_RM0312_3','gpio_phase':'RESET','gpio_reset_exception':False}},
                    'value':'DIGITAL_INPUT' if key=='gpio_direction' else 'NONE'}}],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
'''
text=text.replace("    if technology_id == 'goose':\n",block+"    if technology_id == 'goose':\n",1)
path.write_text(text,encoding='utf-8')
print({'native_fields':len(declarations),'constraints':len(constraints)})
