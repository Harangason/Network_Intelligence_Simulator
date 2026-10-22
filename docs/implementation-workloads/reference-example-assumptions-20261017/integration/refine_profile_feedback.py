from pathlib import Path
import ast

path = Path(__file__).parent / 'staged/backend/nis/agent/orchestration/local_reasoner.py'
text = path.read_text(encoding='utf-8')
text = text.replace('from backend.nis.agent.orchestration.project_intake import reference_design_schema, ReferenceDesignProposal, validate_reference_design, document_response_json',
                    'from backend.nis.agent.orchestration.project_intake import reference_design_schema, ReferenceDesignProposal, validate_reference_design, validate_reference_design_profile, document_response_json', 1)
text = text.replace("        calls = []\n        for profile_index", "        calls = []\n        normalization_events = []\n        for profile_index", 1)
text = text.replace("'source_profile': list(profile), 'reference_sources'", "'source_profile': list(profile), 'reserved_project_device_names': [row['name'] for row in combined['devices']], 'reference_sources'", 1)
text = text.replace('            async def infer(stage, allowed, producer_ids=()):', '            async def infer(stage, allowed, producer_ids=(), feedback=None):', 1)
text = text.replace("                prompt = {**content, 'current_candidate': {field: value for field, value in current.items() if field != 'communication'}, 'planning_stage': stage,", "                prompt = {**content, 'current_candidate': {field: value for field, value in current.items() if field != 'communication'},\n                          'known_communication': current['communication'] if len(allowed) == len(fields) else [\n                              {key: row.get(key) for key in ('id', 'producer_device_id', 'consumer_device_ids', 'scope', 'source_port_id', 'consumer_port_ids', 'transmission_mode', 'request_source', 'request_communication_id', 'cycle_ms', 'min_interval_ms')}\n                              for row in current['communication']],\n                          'validation_feedback': feedback, 'planning_stage': stage,", 1)
needle = "            prefix = json.dumps(profile, ensure_ascii=False)"
text = text.replace(needle, '''            # Ask the same native planner to repair concrete semantic failures
            # in this complete original profile before aggregating other profiles.
            # The final project validator still rechecks the entire original.
            reserved_names = {row['name'].casefold() for row in combined['devices']}
            for repair_attempt in range(3):
                try:
                    checked_profile = validate_reference_design_profile(current, prepared, list(profile))
                    if any(row['name'].casefold() in reserved_names for row in current['devices']):
                        raise ValueError('Ein Teilnehmername gehört bereits zu einem anderen ursprünglichen Profil. Bestehende Quellnamen beibehalten und abgeleitete Instanzen eindeutig qualifizieren.')
                    findings = checked_profile['proposal']['unresolved']
                    if not findings or repair_attempt == 2:
                        current = deepcopy(checked_profile['proposal'])
                        break
                    feedback = {'findings': findings, 'instruction': 'Offene Beispieldaten als begründete Annahmen auslegen; fehlende echte Hardware-/Referenznachweise weiterhin offen kennzeichnen.'}
                except (ValueError, KeyError, TypeError) as error:
                    if repair_attempt == 2:
                        raise ValueError(f'Referenzprofil {profile}: {error}') from error
                    feedback = {'validation_error': str(error)}
                current = await infer('Konkrete fachliche Profilbefunde korrigieren', set(fields), feedback=feedback)
            prefix = json.dumps(profile, ensure_ascii=False)''', 1)
# Namespace only technical network identities and machine-derived participant
# labels. Primary instance identity is protected by the shared source validator.
text = text.replace("            devices = {item['id']: local_id('d', item['id']) for item in current['devices']}", '''            namespace = 'P' + hashlib.sha256(prefix.encode()).hexdigest()[:10]
            protected_names = {name.casefold() for field in ('commands', 'measurements', 'connections', 'owners')
                               for name in prepared['catalog'].get('confirmed_' + field, {})}
            for item in current['devices']:
                primary_instance = any(facts[key]['kind'] == 'INSTANCE' for key in item['source_fact_ids'])
                if profile and not primary_instance and item['name'].casefold() not in protected_names:
                    before = item['name']
                    label = ' / '.join(profile)
                    candidate = label + ' · ' + before
                    item['name'] = candidate if len(candidate) <= 120 else candidate[:99] + ' [' + hashlib.sha256(candidate.encode()).hexdigest()[:16] + ']'
                    normalization_events.append({'field': 'device_name', 'profile': list(profile), 'before': before, 'after': item['name'], 'source': 'NIS_PROFILE_IDENTITY'})
            for item in current['ports']:
                before = item['network_scope']
                if profile:
                    candidate = namespace + ':' + before
                    item['network_scope'] = candidate if len(candidate) <= 120 else namespace + ':' + hashlib.sha256(before.encode()).hexdigest()
                    normalization_events.append({'field': 'network_scope', 'profile': list(profile), 'before': before, 'after': item['network_scope'], 'source': 'NIS_PROFILE_IDENTITY'})
            devices = {item['id']: local_id('d', item['id']) for item in current['devices']}''', 1)
text = text.replace("            for item in current['communication']:\n                item['id'] = local_id('c', item['id'])", "            communications = {item['id']: local_id('c', item['id']) for item in current['communication']}\n            for item in current['communication']:\n                item['id'] = communications[item['id']]\n                if item.get('request_communication_id'):\n                    item['request_communication_id'] = communications.get(item['request_communication_id'], item['request_communication_id'])", 1)
text = text.replace("model_parameter_count=info['model_info']['general.parameter_count'], model_calls=deepcopy(calls))", "model_parameter_count=info['model_info']['general.parameter_count'], model_calls=deepcopy(calls),\n                      normalization_events=normalization_events)", 1)
text = text.replace("            'Benötigte konkrete Instanzen mit unterschiedlichen Anschlüssen oder Ausführern einzeln benennen. '", "            'Benötigte konkrete Instanzen mit unterschiedlichen Anschlüssen oder Ausführern einzeln mit quantity=1 benennen. '\n            'Für Quelleninstanzen die vorhandenen kanonischen source_devices-Namen mit Quellenkontext verwenden; abgeleitete Teilnehmer müssen eindeutige Namen im source_profile besitzen. '\n            'Bereits reservierte Teilnehmernamen gehören zu unabhängigen anderen Profilen und dürfen nicht wiederverwendet werden. '\n            'Kommunikation trägt ausdrücklich die role MEASUREMENT, COMMAND, FEEDBACK, STATUS oder FUNCTION_OUTPUT. Bei Busantworten nur existierende Anfrage-IDs verwenden; bekannte Kommunikationssignaturen sind beigefügt. '", 1)
ast.parse(text)
path.write_text(text, encoding='utf-8', newline='\n')
