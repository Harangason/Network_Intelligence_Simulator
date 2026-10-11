from pathlib import Path
import importlib.util
import itertools
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
from backend.nis.communication.core.components import TechnologyTimingModel
out = ROOT / 'docs/implementation-workloads/structure-completion-20261003'
path = out / 'before/technology-owners/backend/nis/communication/core/components.py'
spec = importlib.util.spec_from_file_location('structure_before_components',path)
old = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = old
spec.loader.exec_module(old)
differences, count = [], 0
for technology, payload, rate, options in itertools.product(
    ['can','can_fd','ethernet','lin','i2c','spi'], [0,8,9,64,1500], [None,0,19200,500000,2000000],
    [{},{'can_frame_format':'BASE_11'},{'arbitration_bitrate':500000,'data_bitrate':2000000},
     {'can_fd_brs':False,'arbitration_bitrate':500000}]):
    profile = DEFAULT_TECHNOLOGY_REGISTRY.profile(technology)
    values = []
    for cls in [old.TechnologyTimingModel,TechnologyTimingModel]:
        try: values.append({'result':cls(technology,profile).transmission_time_us(payload,rate,**options)})
        except Exception as error: values.append({'error':type(error).__name__,'message':str(error)})
    count += 1
    if values[0] != values[1]: differences.append({'technology':technology,'payload':payload,'rate':rate,'options':options,'values':values})
(out / 'adapter-equivalence.json').write_text(json.dumps({'cases':count,'differences':differences},indent=2),encoding='utf-8')
print(json.dumps({'cases':count,'differences':len(differences),'first':differences[:1]}))
assert not differences
