"""Collect unchanged mocked wire tests under the read-only staging overlay."""
from pathlib import Path

source = Path(__file__).parent / 'staged/backend/tests/test_reference_reasoner.py'
exec(compile(source.read_text(encoding='utf-8'), str(source), 'exec'), globals())
