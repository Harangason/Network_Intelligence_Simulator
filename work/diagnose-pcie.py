import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.tests.test_pcie_parameter_review import actual
x={**actual(),'pcie_implementation':'AGILEX3_GTS_25_3','pcie_tlp_payload_bytes':17,
 'pcie_needed_data_credits':2,'pcie_data_credits':2,'pcie_header_credits':1,
 'pcie_transmission_started':True,'pcie_link_active':True,'pcie_training':False}
for bad in ({'pcie_needed_data_credits':1},{'pcie_data_credits':1},{'pcie_header_credits':0},{'pcie_training':True},{'pcie_link_active':False}):
 result=registry.validate_parameters('pcie',{**x,**bad});print(bad,result['status'],result['findings'])
