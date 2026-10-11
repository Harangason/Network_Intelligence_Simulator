import hashlib,json,sys,time
from copy import deepcopy
from pathlib import Path
out=Path(__file__).parent.resolve();sys.path.insert(0,str(out.parents[2]))
from backend.nis.engineering.simulation_observation import mark_user_duration,plan_observation_window
from backend.nis.simulation.hardware_profile import normalize_hardware_config
from backend.nis.traces.universal_trace import generate_universal_events
from backend.nis.simulation.runtime_analysis import analyze_runtime_trace
source=out/'observation-frozen-configuration.json'
config=json.loads(source.read_text())
before=deepcopy(config['communications'])
# The captured1s originated in the whole-form bug, not in a duration edit.
# Restore only that origin in this detached counterfactual; routes, rates,
# requirement limits, schedules and event budget are the exact frozen values.
original_default={'duration_s':1,'parameter_provenance':{'duration_s':{'source':'TECHNOLOGY_DEFAULT','value':1}}}
config['parameters']=mark_user_duration(config['parameters'],previous=original_default,edited_fields=[])
config.pop('duration_s');config.pop('duration',None)
planned=plan_observation_window(config)
assert planned['communications']==before
assert planned['duration_s']==1.071
started=time.monotonic()
events=generate_universal_events(planned,normalize_hardware_config(planned),start_utc=1700000000)[1]
metrics=analyze_runtime_trace({'model_simulation':{'frames':events}},planned)
routes=metrics['routes']
proof={'coverage':'DETACHED_FROZEN_TRANSPORT_REPLAY_NOT_COMPLETE_RELEASE',
 'source_configuration_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'duration':planned['duration_s'],'window_source':planned['observation_window']['source'],
 'communications_unchanged':planned['communications']==before,
 'max_events_unchanged':planned['max_events']==config['max_events'],
 'route_count':len(routes),'statuses':{status:sum(r['status']==status for r in routes) for status in ['PASS','FAIL','NOT_EVALUATED']},
 'slow_route_receipts':[{'route_id':r['canonical_route_id'],'received':r['received_event_count'],'checks':r['requirement_statuses']} for r in routes if r['configured_cycle_ms']==1000],
 'frame_count':len(events),'elapsed_seconds':round(time.monotonic()-started,3)}
(out/'observation-frozen-replay.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps(proof))
assert len(routes)==766 and proof['statuses']=={'PASS':766,'FAIL':0,'NOT_EVALUATED':0}
