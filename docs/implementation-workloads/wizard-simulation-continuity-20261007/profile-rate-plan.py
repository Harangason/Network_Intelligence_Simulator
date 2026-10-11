"""Read-only native calculator probe; no model, API, or SQL access."""
import cProfile, json, pstats, time
from pathlib import Path
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.engineering.capacity.dimensioning import bus_rate_plan

output = Path(__file__).parent
parameters = registry.simulation_defaults_for_project({'technology':'can_fd'}, ['can_fd'])
messages = [{'dlc':8, 'cycle_ms':100} for _ in range(250)]
profiler = cProfile.Profile()
started = time.perf_counter()
result = profiler.runcall(bus_rate_plan, 'can_fd', messages, parameters, alternatives=False)
with (output/'rate-plan-profile.txt').open('w',encoding='utf-8') as stream:
    stream.write(json.dumps({'elapsed_s':time.perf_counter()-started,
                            'status':result['status'], 'candidate_count':len(result['candidates'])})+'\n')
    pstats.Stats(profiler,stream=stream).sort_stats('cumulative').print_stats(35)
print(json.dumps({'status':result['status'], 'candidate_count':len(result['candidates'])}))
