"""Compare complete native review outputs for the captured pending large graph."""
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

out = Path(__file__).parent.resolve()
root = out.parents[2]
sys.path.insert(0, str(root))
from backend.nis.agent.tools import validation as current

spec = importlib.util.spec_from_file_location('pre_full_request_validation', out / 'pre-full-request-validation.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
data = json.loads((out / 'large-review-diagnostic-input.json').read_text(encoding='utf-8'))
changes = data['proposal']['changes']
state = data['workflow']
# This captured model is pending review and its canonical tables are empty.
# The diagnostic exercises only pure native calculations; no SQL or writes.
previous.objects = current.objects = lambda kind: []
for name in ('review_simulation_capacity', 'review_parameter_findings', 'review_bus_rate_plans'):
    started = time.perf_counter()
    expected = getattr(previous, name)(state, changes)
    baseline_seconds = time.perf_counter() - started
    started = time.perf_counter()
    result = getattr(current, name)(state, changes)
    assert result == expected, name
    print(json.dumps({'function': name, 'identical_results': True, 'rows': len(result),
                      'baseline_s': baseline_seconds, 'current_s': time.perf_counter() - started,
                      'sha256': hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()}), flush=True)
