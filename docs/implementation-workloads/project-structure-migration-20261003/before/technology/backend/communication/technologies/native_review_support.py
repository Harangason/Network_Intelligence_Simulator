"""Field metadata construction only; every technology owns its rules and sources."""
WIRE_KEYS=('bitrate','reserved_bandwidth_percent','sync_method','retransmission_enabled',
 'retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput',
 'gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')
ETHERNET_KEYS=('mtu_bytes','duplex','vlan_id','rate_limit_bit_s')

def declaration(prefix,key,kind,description,source,revision,**bounds):
 return dict(key=prefix+key,type=kind,description=description,source=source,source_revision=revision,**bounds)

def fields(declarations,required,conditional_defaults=None):
 out=[]
 for declaration in declarations:
  v={k:value for k,value in declaration.items()if value is not None}
  key=v['key']
  v.update(label=key.replace('_',' '),category='technology',scope='network',editable=True,
   required=key in required,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',
   validation_relevant=True,simulation_relevant=False)
  defaults=(conditional_defaults or{}).get(key)
  if defaults:v.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=defaults)
  out.append(v)
 return out
