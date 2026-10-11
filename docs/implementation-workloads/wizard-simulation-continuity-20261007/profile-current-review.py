"""Pure replay of captured proposal input; does not call SQL or alter the model."""
import cProfile,json,pstats,sys,time
from pathlib import Path
out=Path(__file__).parent.resolve();root=out.parents[2];sys.path.insert(0,str(root))
from backend.nis.agent.tools import validation
from backend.nis.agent.tools.model import SECTIONS
data=json.loads((out/'topology-native-review-input.json').read_text(encoding='utf-8'))
rows={kind:data['model'][section] for section,kind in SECTIONS.items()}
validation.objects=lambda kind:rows[kind]
profile=cProfile.Profile();started=time.perf_counter()
result=profile.runcall(validation.review_parameter_findings,data['workflow'],data['proposal']['changes'])
profile.dump_stats(str(out/'native-review-current.prof'))
with (out/'native-review-current-profile.txt').open('w',encoding='utf-8') as log:
    pstats.Stats(profile,stream=log).strip_dirs().sort_stats('cumulative').print_stats(45)
(out/'native-review-current-result.json').write_text(json.dumps(result,default=str),encoding='utf-8')
print(json.dumps({'elapsed_s':time.perf_counter()-started,'findings':len(result),'pure_replay':True}),flush=True)
