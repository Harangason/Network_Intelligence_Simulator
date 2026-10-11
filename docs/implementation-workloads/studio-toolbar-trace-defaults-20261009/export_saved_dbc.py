"""Read an immutable saved run; export definitions without touching product storage."""
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import cantools
from backend.nis.simulation.hardware_profile import normalize_hardware_config
from backend.nis.traces.universal_trace import build_routes
from backend.nis.communication.technologies.can.formats.can_format_writers import write_project_can_artifacts

root = Path(__file__).resolve().parent
snapshot = json.loads((root / 'production-snapshot-before.json').read_text(encoding='utf-8-sig'))
config = snapshot['configuration']
routes = build_routes(config, normalize_hardware_config(config))
paths, summary = write_project_can_artifacts(root / 'offline-project-dbc', config, routes, [], ['dbc'])
definitions = [path for path in paths if path.suffix == '.dbc']
databases = [cantools.database.load_file(str(path), strict=True) for path in definitions]
summary.update(snapshot_id=snapshot['id'], project_id=snapshot['project_id'],
               verified_dbc_files=len(databases),
               verified_messages=sum(len(database.messages) for database in databases),
               verified_fd_messages=sum(message.is_fd for database in databases for message in database.messages),
               product_mutations=0, source='Frozen saved simulation configuration; no new simulation run')
(root / 'offline-project-dbc-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
with ZipFile(root / 'NIS_CAN_DBC.zip', 'w', ZIP_DEFLATED) as archive:
    for path in definitions:
        archive.write(path, path.name)
    archive.write(root / 'offline-project-dbc-summary.json', 'export-summary.json')
print(json.dumps(summary))
