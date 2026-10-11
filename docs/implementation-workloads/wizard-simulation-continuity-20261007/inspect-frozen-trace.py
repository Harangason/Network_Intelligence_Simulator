import json, zipfile
from pathlib import Path
out = Path(__file__).parent
archive_path = out/'performance-browser/wizard-new-small-wizard-tr-c83d1-rvives-reload-restart-small/trace.zip'
rows = []
with zipfile.ZipFile(archive_path) as archive:
    for name in archive.namelist():
        if not name.startswith('resources/'):
            continue
        try:
            value = json.loads(archive.read(name))
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(value,dict):
            continue
        parameters = value.get('parameters')
        if isinstance(parameters,dict) and 'simulation_parameter_assumptions' in parameters:
            rows.append({'saved_parameters':parameters})
        configuration = value.get('configuration')
        if isinstance(configuration,dict) and 'networks' in configuration:
            rows.append({'snapshot':configuration})
(out/'frozen-rate-trace-observation.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
for row in rows[-6:]:
    if 'snapshot' in row:
        cfg = row['snapshot']
        print(json.dumps({'snapshot_parameters':{key:cfg['parameters'].get(key) for key in ['technology','seed','data_bitrate','can_fd_data_prescaler']},
            'networks':[{key:item.get(key) for key in ['technology','arbitration_bitrate','data_bitrate','can_fd_data_prescaler']} for item in cfg['networks']]}))
    else:
        p = row['saved_parameters']
        print(json.dumps({'saved':{key:p.get(key) for key in ['technology','seed','data_bitrate','can_fd_data_prescaler']},'can_fd_group':p.get('technology_parameters',{}).get('can_fd')}))
