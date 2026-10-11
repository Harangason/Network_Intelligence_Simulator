"""Save the immediately preceding regular candidate's validation source."""
import hashlib
import json
import subprocess
from pathlib import Path

out = Path(__file__).parent
docker = 'C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
image = 'networkis:candidate-b38d800af059'
source = subprocess.check_output([docker, 'run', '--rm', '--label', 'networkis.test=disposable',
    '--entrypoint', 'cat', image, '/app/backend/nis/agent/tools/validation.py'])
(out / 'pre-full-request-validation.py').write_bytes(source)
print(json.dumps({'image': image, 'source_sha256': hashlib.sha256(source).hexdigest()}))
