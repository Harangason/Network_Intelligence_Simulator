"""Observe existing isolated SQL regression without changing its execution."""
import cProfile
import json
import pstats
import time
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def observe_full_proposal_validation(monkeypatch, request):
    if request.node.name != 'test_full_captured_model_and_all_routing_validate_without_rewriting_inputs':
        return
    from backend.nis.agent.tools import proposal_service
    original = proposal_service.validate
    output = Path(__file__).parent
    count = 0

    def observed(*args, **kwargs):
        nonlocal count
        count += 1
        if count > 2:
            return original(*args, **kwargs)
        profiler = cProfile.Profile()
        started = time.perf_counter()
        try:
            return profiler.runcall(original, *args, **kwargs)
        finally:
            profiler.dump_stats(str(output / f'full-validate-{count}.prof'))
            with (output / f'full-validate-{count}-profile.txt').open('w', encoding='utf-8') as stream:
                stream.write(json.dumps({'elapsed_s': time.perf_counter() - started}) + '\n')
                pstats.Stats(profiler, stream=stream).sort_stats('cumulative').print_stats(65)

    monkeypatch.setattr(proposal_service, 'validate', observed)
