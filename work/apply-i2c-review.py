"""One-shot catalog form insertion. I2C definitions remain in their own profile."""
from pathlib import Path
p=Path('backend/communication/technologies/catalog.py');s=p.read_text(encoding='utf-8')
block='''    if technology_id == 'i2c':
        fields=[item for item in fields if item['key'] not in i2c_rules.REMOVED]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None);item.pop('max',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=i2c_rules.SOURCE,source_revision=i2c_rules.REVISION,simulation_relevant=False,
                    description='Actual encoded data octets; I2C imposes no255-byte transfer maximum. Address/register/ninth-clock/layout overhead is separate.')
        for key,kind,unit,options,minimum,maximum,meaning in i2c_rules.DECLARATIONS:
            native=field(key,key.replace('i2c_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['i2c']['required_parameters'],
                integer=kind=='number' and unit not in {'ns','V','mA','pF','Ohm'},
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=i2c_rules.SOURCE,source_revision=i2c_rules.REVISION)
            if key=='i2c_mode': native.update(default='STANDARD',default_status='PROPOSED_STANDARD')
            if key=='i2c_ack_policy':
                native.update(conditional_defaults=[{'when':{'i2c_mode':mode},'value':'NINTH_HIGH_NO_ACK' if mode=='ULTRA_FAST' else 'ACK_NACK'} for mode in i2c_rules.MODES],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
'''
needle="    if technology_id == 'http':\n        source="
assert needle in s and "    if technology_id == 'i2c':\n        fields=" not in s
s=s.replace(needle,block+needle,1)
s=s.replace('(\"i2c\", \"I2C\", \"embedded_systems\", \"DATA_LINK\", \"MESSAGE\", (\"REGISTER\", \"RAW_DATA\"), \"i2c_controller\", (), 400_000, 255, (\"request_response\",), True)',
 '(\"i2c\", \"I2C\", \"generic_networking\", \"DATA_LINK\", \"MESSAGE\", (\"REGISTER\", \"RAW_DATA\"), \"explicit_i2c_port\", (), None, None, (\"request_response\",), False)',1)
p.write_text(s,encoding='utf-8')
