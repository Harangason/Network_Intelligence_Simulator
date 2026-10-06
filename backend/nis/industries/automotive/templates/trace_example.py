"""Preserved Automotive demonstration data; never project transport defaults."""
import json
from pathlib import Path

def trace_example():
    """Return a fresh example so callers cannot mutate the shared definition."""
    return json.loads(Path(__file__).with_name('trace-example.json').read_text(encoding='utf-8'))
