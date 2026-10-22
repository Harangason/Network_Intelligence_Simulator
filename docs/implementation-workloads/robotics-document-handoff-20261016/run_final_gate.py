"""Run the full canonical release gate and retain its process output."""
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[2]
with (OUT / 'full-release-process.log').open('w', encoding='utf-8') as log:
    result = subprocess.run([sys.executable, '-u', str(ROOT / 'scripts/run-release-gate.py'),
                             '--output', str(ROOT / 'backend/test-output/release-gates/robotics-document-handoff-20261016')],
                            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
print({'full_release_gate_exit_code': result.returncode})
raise SystemExit(result.returncode)
