"""Use the canonical isolation runner, retaining Docker startup diagnostics."""
import runpy
import subprocess
import sys

sys.argv[0] = 'scripts/run-isolated-tests.py'
try:
    runpy.run_path(sys.argv[0], run_name='__main__')
except subprocess.CalledProcessError as error:
    print(error.stderr, file=sys.stderr, flush=True)
    raise
