import runpy, sys, subprocess
sys.argv = ['scripts/run-isolated-tests.py', 'backend/tests/test_simulation_parameter_defaults.py',
            'backend/tests/test_technology_parameter_review.py', 'backend/tests/test_workflow.py', '-q']
try:
    runpy.run_path(sys.argv[0], run_name='__main__')
except subprocess.CalledProcessError as error:
    print(error.stderr)
    raise SystemExit(1)
