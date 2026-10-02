import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as r
x={'bitrate_bps':100000000,'epl_edition':'DS301_1_5_1','epl_extension':'NONE','epl_mode':'POWERLINK','epl_role':'CN','epl_phy':'100BASE_TX','epl_duplex':'HALF'}
for k in('device_source','physical_source','schedule_source','mapping_source','acceptance_source','address_source'):x['epl_'+k]='synthetic'
for bad in({'bitrate_bps':10000000},{'bitrate_bps':1000000000},{'epl_duplex':'FULL'},{'mtu_bytes':1500},{'can_bus_mode':'CAN_FD'},{'can_cc_variant':'BOSCH_CAN_2_0'}):print(bad,r.validate_parameters('powerlink',{**x,**bad}))
print('empty',r.validate_parameters('powerlink',{'bitrate_bps':100000000}))
