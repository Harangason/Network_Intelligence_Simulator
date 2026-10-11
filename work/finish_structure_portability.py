from finish_structure_owners import *
import importlib.util

path = 'frontend/src/features/network/lib/topology.ts'
write(path, read(path).replace("from '../../communication/lib/bus-technology';", "from '../../communication/lib/bus-technology.ts';"))
path = 'scripts/migrations/structure_mapping.py'
source = read(path)
start = source.index('        for match in re.finditer', source.index("if path.startswith('frontend/src/')"))
# Replace only the literal-path scanner after the TypeScript block.
start = source.index('        for match in re.finditer', start + 1)
end = source.index('    return reverse', start)
source = source[:start] + '''        # Quoted/backtick tokens cover CLI and Markdown references without
        # catastrophic path-regex backtracking through large fixture payloads.
        for value in re.findall(r"[\\\"'`](.{1,400}?)[\\\"'`]", text):
            value = value.replace('\\\\', '/')
            if '/' not in value or Path(value).suffix not in {'.py', '.ts', '.tsx', '.mjs', '.json', '.md', '.ps1', '.sh'}:
                continue
            edge(value, path)
            candidate = (root / Path(path).parent / value).resolve()
            if candidate.is_relative_to(root): edge(candidate.relative_to(root).as_posix(), path)
''' + source[end:]
write(path, source)
apply('reference-scanner-and-node-import')
WRITES.clear()
spec = importlib.util.spec_from_file_location('mapping_generator', ROOT / path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
write('docs/migrations/structure_mapping.csv', module.reconcile())
apply('transition-mapping')
