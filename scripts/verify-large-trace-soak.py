"""Bounded multi-GiB trace-window + reasoning soak, no production writes.

The load fixture repeats real simulator event shapes with unique times/IDs.
It tests storage/window/analysis stability, not a multi-hour physical simulation.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gc
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'backend'), str(ROOT / 'backend/simulator')]
from backend.tests.test_model_based_simulation import simulation_config
from backend.app.trace_service import read_trace_window
from backend.engineering.reasoning.engine import EngineeringReasoningEngine
from universal_trace import generate_universal_events, write_jsonl
from hardware_profile import normalize_hardware_config
import os


def rss_bytes():
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                *[(name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                   'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]]
        info = Counters()
        info.cb = ctypes.sizeof(info)
        function = ctypes.windll.psapi.GetProcessMemoryInfo
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if not function(wintypes.HANDLE(-1), ctypes.byref(info), info.cb):
            raise ctypes.WinError()
        return info.WorkingSetSize
    return int(Path('/proc/self/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gib', type=float, default=2)
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    directory = ROOT / 'backend/test-output' / ('trace-soak-' + str(time.time_ns()))
    directory.mkdir(parents=True)
    config = simulation_config(directory)
    _, originals = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    template = originals[0]
    size = len(json.dumps(template).encode()) + 600
    count = max(1024, int(args.gib * 1024**3 / size))
    def records():
        for i in range(count):
            yield {**template, 'event_id': f'soak:{i}', 'sequence': i, 'time_s': i * .01, 'scheduled_time_s': i * .01,
                'timestamp_unix': 1700000000+i*.01, 'stress_padding': 'x' * 600}
    path = directory / 'universal_trace.jsonl'
    started = time.monotonic()
    write_jsonl(path, records())
    generation_s = time.monotonic()-started
    print(json.dumps({'phase': 'fixture-ready', 'bytes': path.stat().st_size, 'events': count, 'generation_s': generation_s}), flush=True)
    gc.collect()
    initial_rss = rss_bytes()
    peak_rss, requests, samples, analysis_samples = initial_rss, 0, [], []
    def query(index):
        low = ((index * 7919) % max(1, count-601)) * .01
        began = time.monotonic()
        page = read_trace_window(path, start_s=low, end_s=low+1, limit=200)
        elapsed = time.monotonic()-began
        assert 99 <= len(page['events']) <= 102, page['count']
        assert page['next_cursor'] is None
        assert page['scanned'] <= 615, page['scanned']
        if index % 8 == 0:
            began = time.monotonic()
            reasoning = EngineeringReasoningEngine().analyze(project_id='soak-qa', job_id='soak', events=page['events'],
                window={'start_s': low, 'end_s': low+1, 'next_cursor': None},
                context={'snapshot_available': True, 'trusted_simulation': True, 'configuration': {**config, 'duration_s': count*.01}, 'faults': [], 'routes': []})
            assert len(reasoning.evidence_refs) <= 2000 and len(reasoning.observations) <= 500
            return elapsed, time.monotonic()-began
        return elapsed, None
    began = time.monotonic()
    with ThreadPoolExecutor(max_workers=4) as pool:
        while time.monotonic()-began < args.seconds:
            result = list(pool.map(query, range(requests, requests+16)))
            requests += 16
            samples.extend(r[0] for r in result)
            analysis_samples.extend(r[1] for r in result if r[1] is not None)
            peak_rss = max(peak_rss, rss_bytes())
            if requests % 1024 == 0:
                print(json.dumps({'phase': 'soak', 'requests': requests, 'seconds': round(time.monotonic()-began), 'rss_mib': peak_rss/1024**2}), flush=True)
    gc.collect()
    final_rss = rss_bytes()
    assert final_rss-initial_rss < 128*1024**2, 'Sustained memory growth exceeds 128 MiB'
    assert peak_rss-initial_rss < 256*1024**2, 'Peak growth exceeds 256 MiB'
    report = {'fixture': str(path), 'fixture_kind': 'STREAMED_LOAD_FIXTURE_BASED_ON_REAL_SIMULATOR_EVENTS',
        'bytes': path.stat().st_size, 'events': count, 'generation_s': generation_s, 'duration_s': time.monotonic()-began,
        'workers': 4, 'window_requests': requests, 'reasoning_requests': len(analysis_samples),
        'p95_window_ms': statistics.quantiles(samples, n=100)[94]*1000, 'max_window_ms': max(samples)*1000,
        'p95_reasoning_ms': statistics.quantiles(analysis_samples, n=100)[94]*1000,
        'initial_rss_mib': initial_rss/1024**2, 'peak_rss_mib': peak_rss/1024**2, 'final_rss_mib': final_rss/1024**2,
        'errors': 0, 'status': 'PASSED', 'scope': 'Indexed storage reader and bounded reasoning; no claim of full-file reasoning aggregation.'}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
