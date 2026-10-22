"""Collect unchanged proposed regressions in the explicit staging overlay."""
from pathlib import Path

source = Path(__file__).parent / 'staged/backend/tests/test_reference_design_integration.py'
exec(compile(source.read_text(encoding='utf-8'), str(source), 'exec'), globals())
