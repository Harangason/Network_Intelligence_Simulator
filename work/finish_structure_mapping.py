from finish_structure_owners import *
import importlib.util

path = 'scripts/migrations/structure_mapping.py'
source = read(path).replace('import subprocess', 'import os')
source = source.replace("'/runtime/', '/build/',", "'/runtime/', '/backend/build/',")
start = source.index('    result = ', source.index('def inventory'))
end = source.index('\ndef module_name', start)
source = source[:start] + '''    paths = []
    pruned = {'.venv', 'node_modules', 'test-output', 'runtime', 'before', 'archive',
              'archives', '__pycache__', '.next', 'project-scanner', 'implementation-workloads'}
    for folder in ['backend', 'frontend/src', 'scripts', 'docs']:
        for directory, dirs, files in os.walk(root / folder):
            dirs[:] = [name for name in dirs if name not in pruned]
            for name in files:
                path = (Path(directory) / name).relative_to(root).as_posix()
                if not any(part in '/' + path for part in EXCLUDED) and Path(path).suffix in {
                    '.py', '.ts', '.tsx', '.mjs', '.json', '.md', '.ps1', '.sh', '.yml', '.yaml'}:
                    paths.append(path)
    return sorted(paths)

''' + source[end:]
write(path, source)
apply('mapping-generator-portability')
WRITES.clear()
spec = importlib.util.spec_from_file_location('mapping_generator', ROOT / path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
write('docs/migrations/structure_mapping.csv', module.reconcile())
apply('transition-mapping')
