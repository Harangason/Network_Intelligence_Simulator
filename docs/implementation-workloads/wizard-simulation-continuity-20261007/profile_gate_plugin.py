"""Diagnostic observation only: execute the existing isolated test unchanged."""
import cProfile, json, pstats, time
from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def observe_parameter_generation(monkeypatch, request):
    if request.node.name != 'test_full_captured_model_and_all_routing_validate_without_rewriting_inputs':
        return
    from backend.nis.agent.tools import wizard_generation
    original = wizard_generation.generate_parameters
    output = Path(__file__).parent
    def observed(*args, **kwargs):
        profiler = cProfile.Profile()
        started = time.perf_counter()
        try:
            return profiler.runcall(original, *args, **kwargs)
        finally:
            profiler.dump_stats(str(output/'parameter-generation.prof'))
            with (output/'parameter-generation-profile.txt').open('w',encoding='utf-8') as stream:
                stream.write(json.dumps({'elapsed_s':time.perf_counter()-started})+'\n')
                pstats.Stats(profiler, stream=stream).sort_stats('cumulative').print_stats(45)
    monkeypatch.setattr(wizard_generation, 'generate_parameters', observed)
