"""Create a reviewable model from the same deterministic catalogs as the wizard."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import shutil
import subprocess

from . import model, proposal_service
from .. import proposals as proposal_store
from ..device_classification import DeviceClassificationRegistry


def extract_specification(prompt: str) -> dict:
    node = shutil.which('node')
    if not node:
        raise ValueError('Node.js wird für den vorhandenen Wizard-Generator benötigt.')
    script = Path(__file__).resolve().parents[3] / 'frontend' / 'scripts' / 'extract-wizard-specification.mjs'
    result = subprocess.run(
        [node, '--experimental-strip-types', str(script)],
        input=json.dumps({'prompt': prompt}), text=True, encoding='utf-8',
        capture_output=True, timeout=60, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
    )
    if result.returncode:
        raise ValueError('Die Wizard-Spezifikation konnte nicht abgeleitet werden: ' + result.stderr[-1000:])
    return json.loads(result.stdout)


def generate(arguments: dict) -> dict:
    fingerprint = hashlib.sha256(('class-aware-v2\n' + arguments['prompt']).encode('utf-8')).hexdigest()
    for row in proposal_store.list_proposals(limit=100):
        if (row['proposal_type'] == 'WIZARD_ENGINEERING_MODEL'
                and any(item.get('prompt_sha256') == fingerprint for item in row.get('evidence') or [])
                and (row.get('engineering_contract') or {}).get('status') in {'PROPOSED', 'VALIDATED'}):
            return proposal_service.envelope(row)
    spec = extract_specification(arguments['prompt'])
    changes, refs = [], {}
    kinds = ('HardwareNode', 'Function', 'HardwareNetworkInterface', 'Interface', 'Message', 'Signal')
    existing = {kind: model.objects(kind) for kind in kinds}

    def ensure(kind, name, data, parent=None):
        signature = (kind, name.casefold(), data.get(parent) if parent else None)
        if signature in refs:
            return refs[signature]
        matches = [row for row in existing[kind] if row['name'].casefold() == name.casefold()
                   and (not parent or str(row.get(parent)) == str(data[parent]))]
        if len(matches) > 1:
            raise ValueError(f'Mehrdeutige vorhandene Zuordnung: {kind} {name}')
        if matches:
            if kind == 'HardwareNode' and matches[0].get('device_type') != data['device_type']:
                raise ValueError(f'Gerätetyp des vorhandenen Systems {name} passt nicht zum Auftrag.')
            ref = str(matches[0]['id'])
        else:
            local_ref = f'object-{len(changes)}'
            changes.append({'object_type': kind, 'local_ref': local_ref, 'data': {'name': name, **data}})
            ref = '$' + local_ref
        refs[signature] = ref
        return ref

    for chain in spec['chains']:
        profile = DeviceClassificationRegistry().resolve_profile(
            name=chain['hardware_name'], device_type=chain['device_type'],
            device_class=chain.get('device_class'))
        hw = ensure('HardwareNode', chain['hardware_name'], {
            'device_type': chain['device_type'], 'device_class': profile.device_class,
            'description': chain['hardware_description']})
        fn = None
        if profile.requires_function_model:
            fn = ensure('Function', chain['function_name'], {
                'hardware_node_id': hw, 'domain': spec['domain'], 'description': chain['function_description']}, 'hardware_node_id')
        port = ensure('HardwareNetworkInterface', chain['interface_name'], {
            'hardware_node_id': hw, 'technology': chain['interface_type'], 'channel_index': 1}, 'hardware_node_id')
        interface = ensure('Interface', chain['interface_name'], {
            **({'function_id': fn} if fn else {'hardware_node_id': hw}),
            'interface_type': chain['interface_type']}, 'function_id' if fn else 'hardware_node_id')
        message = ensure('Message', chain['message_name'], {
            'interface_id': interface, 'hardware_interface_id': port,
            **{key: chain[key] for key in ('message_id_hex', 'direction', 'cycle_ms', 'dlc')}}, 'interface_id')
        ensure('Signal', chain['signal_name'], {
            'message_id': message,
            **{key: chain[key] for key in ('start_bit', 'length_bits', 'byte_order', 'data_type',
                'factor', 'offset_value', 'unit', 'min_value', 'max_value', 'configuration',
                'semantic', 'data', 'communication', 'quality') if key in chain}}, 'message_id')
    if not changes:
        raise ValueError('Die abgeleiteten Modellobjekte sind bereits vorhanden; vorhandenen Modellstand prüfen.')
    return proposal_service.create('WIZARD_ENGINEERING_MODEL', changes,
        f"Engineering-Modell aus bestätigten Wizard-Vorgaben: {len(changes)} vorgeschlagene Änderungen. "
        "Noch keine Änderungen am kanonischen Modell; Freigabe und Übernahme sind erforderlich.",
        assumptions=['Technische Defaults und ergänzte Geräte stammen aus den Wizard-Branchenkatalogen und müssen geprüft werden.',
                     'Dieses Paket umfasst das Engineering-Modell. Routing, Topologie und Simulation folgen nach der Modellfreigabe.'],
        evidence=[{'source': 'wizard-specification-generator', 'prompt_sha256': fingerprint, 'target_counts': spec['targetCounts'],
                   'communication_system_counts': spec['communicationSystemCounts']}])
