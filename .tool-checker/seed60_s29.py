import json
from industry60_fixtures import api,ROOT
h=api('nis-e2e-industry60-s29','hardware-nodes',{'name':'CentralGateway','device_type':'Gateway'});(ROOT/'.tool-checker/evidence/industry60/S29/ui-fixture.json').write_text(json.dumps({'hardware':h,'source_finding':'SINGLE_POINT_OF_FAILURE: CentralGateway is articulation point of topology.','limitation':'Precomputed source finding supplied as test fixture, not newly detected topology proof.'},ensure_ascii=False,indent=2),encoding='utf8')
