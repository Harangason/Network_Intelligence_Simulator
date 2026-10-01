"""Remove one receipt-bound disposable NIS test stack, never its image."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
    names = receipt['containers']
    token = names['app'].removeprefix('nis-e2e-app-')
    expected = {key: f'nis-e2e-{key}-{token}' for key in ('app', 'db', 'network', 'runtime')}
    if len(token) != 12 or any(names[key] != expected[key] for key in expected):
        raise ValueError('Receipt does not name one complete disposable test stack')
    docker = shutil.which('docker') or str(Path.home() / 'AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe')
    for kind, keys in [('container', ('app', 'db')), ('network', ('network',)), ('volume', ('runtime',))]:
        for key in keys:
            name = names[key]
            command = [docker, 'inspect', name] if kind == 'container' else [docker, kind, 'inspect', name]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                raise ValueError(f'{kind} missing: {name}')
            obj = json.loads(result.stdout)[0]
            labels = obj.get('Config', {}).get('Labels', {}) if kind == 'container' else obj.get('Labels', {})
            if labels.get('networkis.test') != 'disposable':
                raise ValueError(f'Non-disposable {kind}: {name}')
    for key in ('app', 'db'):
        subprocess.run([docker, 'rm', '-f', names[key]], check=True, capture_output=True)
    subprocess.run([docker, 'network', 'rm', names['network']], check=True, capture_output=True)
    subprocess.run([docker, 'volume', 'rm', names['runtime']], check=True, capture_output=True)
    print(json.dumps({'removed': names, 'image_preserved': receipt.get('image_id')}))


if __name__ == '__main__':
    main()
