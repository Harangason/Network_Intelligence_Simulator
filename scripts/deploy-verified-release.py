"""Deploy only an immutable candidate with a complete successful gate receipt."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def verify_local_checkout(receipt, source, commit, verification):
    """Refuse a tested image assembled from a different local source or test set."""
    if source != receipt.get('initial_source_sha256'):
        raise SystemExit('Deployment refused: canonical application source differs from the tested image.')
    if verification != receipt.get('verification_sha256'):
        raise SystemExit('Deployment refused: canonical release tests differ from the PASS receipt.')
    if not commit or commit != receipt.get('initial_commit_id') or commit != receipt.get('release', {}).get('commit_id'):
        raise SystemExit('Deployment refused: canonical Git revision differs from the PASS receipt.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt', type=Path)
    parser.add_argument('--compose', action='append', default=[])
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
    required = {'typecheck','frontend-tests','backend-tests','browser-e2e','small-http','large-http'}
    checks = {item['name'] for item in receipt.get('checks',[]) if item['exit_code']==0}
    if receipt.get('status')!='PASS' or receipt.get('development_only') or not required <= checks:
        raise SystemExit('Deployment refused: a complete production release gate PASS is required.')
    if not receipt.get('verification_sha256') or not receipt.get('initial_source_sha256') or (
            receipt['initial_source_sha256'] != receipt.get('release', {}).get('source_sha256')):
        raise SystemExit('Deployment refused: tests and candidate must be bound to the initial source identity.')
    identity_spec = importlib.util.spec_from_file_location('delivery', ROOT / 'scripts/release-and-deploy.py')
    delivery = importlib.util.module_from_spec(identity_spec)
    identity_spec.loader.exec_module(delivery)
    verify_local_checkout(receipt, *delivery.current_identity())
    spec=importlib.util.spec_from_file_location('isolation',ROOT/'scripts/run-isolated-tests.py')
    isolation=importlib.util.module_from_spec(spec); spec.loader.exec_module(isolation)
    docker=isolation.docker_executable(); image=receipt['image_id']
    actual=subprocess.check_output([docker,'image','inspect',image,'--format','{{.Id}}'],text=True).strip()
    if image!=actual: raise SystemExit('Deployment refused: candidate image identity changed.')
    manifest=json.loads(subprocess.check_output([docker,'run','--rm','--entrypoint','cat',image,'/app/backend/app/build-info.json'],text=True))
    if manifest['source_sha256']!=receipt['release']['source_sha256']:
        raise SystemExit('Deployment refused: source identity differs from tested receipt.')
    env={**os.environ,'NETWORKIS_RELEASE_IMAGE':image}
    files=args.compose or [str(ROOT/'docker-compose.networkis.yml')]
    command=[docker,'compose']
    for path in files: command+=['-f',path]
    # This starts the exact tested image. It cannot rebuild modified sources.
    subprocess.run([*command,'up','-d','--no-build'],cwd=ROOT,env=env,check=True)
    approved=ROOT/'backend/runtime/verified-release.json'
    approved.parent.mkdir(parents=True,exist_ok=True)
    approved.write_text(json.dumps({'image_id':image,'receipt':str(args.receipt.resolve()),'release':manifest},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__': main()
