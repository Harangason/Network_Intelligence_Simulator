from pathlib import Path
import ast

path = Path(__file__).parent / 'staged/backend/nis/agent/orchestration/local_reasoner.py'
text = path.read_text(encoding='utf-8')
point = text.index("        fields = ('devices'", text.index('    async def plan_reference_design'))
text = text[:point] + '''        # Reuse the authoritative catalogs, but do not repeat source quotes
        # and long document-identity keys already carried by original_facts.
        # The unabridged source and references themselves are never truncated.
        catalog = deepcopy(prepared['catalog'])
        catalog['source_function_assignments'] = {key: catalog.get('source_function_assignments', {}).get(identity)
            for key, identity in prepared['fact_id_map'].items() if identity in catalog.get('source_function_assignments', {})}
        catalog['source_devices'] = [{key: row[key] for key in ('name', 'device_type') if key in row}
                                     for row in catalog.get('source_devices', [])]
        catalog.pop('name_aliases', None)  # server preservation guard still uses the complete catalog
        from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
        technology_schemas = {}
        for item in prepared['source_evidence'].get('technologies') or []:
            if item.get('kind') != 'TRANSPORT':
                continue
            technology = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(item['name'])
            try:
                definition = DEFAULT_TECHNOLOGY_REGISTRY.profile(technology)
            except (KeyError, ValueError):
                continue
            technology_schemas[technology] = {
                'rate_model': definition['rate_model'],
                'parameters': {key: {name: field[name] for name in ('type', 'required', 'unit', 'min', 'max', 'options', 'enum') if name in field}
                               for key, field in definition['parameter_schema'].items()},
                'parameter_roles': DEFAULT_TECHNOLOGY_REGISTRY.parameter_roles(technology),
                'parameter_aliases': definition.get('parameter_aliases') or {},
            }
        catalog['technology_parameters'] = technology_schemas
''' + text[point:]
text = text.replace("'registered_catalogs': prepared['catalog']", "'registered_catalogs': catalog", 1)
text = text.replace("                    body = response.json()\n                    raw =", "                    body = response.json()\n                    if body.get('done_reason') == 'length':\n                        raise ValueError('Die lokale Referenzantwort wurde an der Ausgabegrenze abgeschnitten. Es wurde kein unvollständiger Entwurf übernommen.')\n                    raw =", 1)
ast.parse(text)
path.write_text(text, encoding='utf-8', newline='\n')
