"""Check the later read-only delivery probe only in the owned test container."""
from pathlib import Path
import ast
import json
import subprocess
OUT = Path(__file__).parent.resolve()
ROOT = OUT.parents[3]
runtime = json.loads((OUT / 'native-runtime-preparation.json').read_text(encoding='utf-8'))
docker = json.loads((ROOT / 'config/networkis.resources.json').read_text(encoding='utf-8'))['paths']['docker_cli']
app = json.loads(subprocess.check_output([docker, 'inspect', runtime['containers']['app']], text=True, encoding='utf-8'))[0]
assert app['Id'] == runtime['app_container_id'] and app['Image'] == runtime['image_id']
assert app['Config']['Labels']['networkis.test'] == 'disposable'
tree = ast.parse((OUT.parent / 'verify_production_function.py').read_text(encoding='utf-8'))
program = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'program' for target in node.targets))
result = subprocess.run([docker, 'exec', '-i', runtime['containers']['app'], 'python', '-'], input=program, text=True, encoding='utf-8', capture_output=True, check=True)
probe = json.loads(result.stdout)
probe['scope'] = 'Delivery-probe dry run only in the owned isolated native candidate; not production, Qwen, Wizard acceptance or a release gate.'
probe.update(image_id=app['Image'], container=runtime['containers']['app'], uses_product_database=False)
(OUT / 'delivery-probe-dry-run.json').write_text(json.dumps(probe, indent=2), encoding='utf-8')
print(json.dumps(probe))
