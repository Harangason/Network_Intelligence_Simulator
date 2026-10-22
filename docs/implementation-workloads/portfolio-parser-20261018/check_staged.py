"""Pure parser checks. No HTTP, database, inference or canonical model writes."""
import importlib.util
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
from backend.nis.agent.tools.inventory_quantities import VOCABULARY
VOCABULARY.update(json.loads((OUT / 'staged/backend/nis/domain/inventory-vocabulary.json').read_text(encoding='utf-8')))
spec = importlib.util.spec_from_file_location('staged_parser_checks', OUT / 'staged/backend/nis/agent/orchestration/project_intake.py')
intake = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = intake
spec.loader.exec_module(intake)


def units(text, prefix=''):
    return intake.document_component_sources(intake.document_source_references(text), scope_prefix=prefix)


def run():
    results = []

    def check(name, operation):
        try:
            operation()
            results.append({'case': name, 'status': 'PASSED'})
        except Exception as error:
            results.append({'case': name, 'status': 'FAILED', 'error': str(error)})

    def expect_equal(actual, expected):
        assert actual == expected, (actual, expected)

    for caption in ['Mechanische, elektrische und E/E-Architektur', 'Physical and logical Architecture',
                    'Kernfunktionen', 'Core functions', 'Regulatorische Anforderungen', 'Regulatory Requirements']:
        check('semantic chapter: ' + caption, lambda caption=caption:
              expect_equal(intake.document_system_scope(['Factory North', '8. ' + caption]), ['Factory North']))

    for system in ['Medical Controller', 'Robot Arm', 'Kernfunktionenrechner', 'Physical Inspection System']:
        check('named system preserved: ' + system, lambda system=system:
              expect_equal(intake.document_system_scope(['Portfolio', system, 'Architektur']), ['Portfolio', system]))

    for caption in ['Kernfunktionen', 'Core functions']:
        check('every functional bullet retained: ' + caption, lambda caption=caption:
              expect_equal([(u['text'], u['required'], u['policy']['kind']) for u in
                            units('# Warehouse\n## ' + caption + '\n- Material Flow\n- Recovery\n')],
                           [('- Material Flow', True, 'FUNCTION'), ('- Recovery', True, 'FUNCTION')]))

    instructions = 'Die Architektur wird mindestens in Träger, Sensoren, Steuergeräte zerlegt. Für jeden Pfad werden Quelle, Senke und Eigentümer geführt.'
    check('architecture instruction is one complete requirement', lambda:
          expect_equal([(u['text'], u['policy']['kind']) for u in units('# Facility\n## Architektur\n' + instructions)],
                       [(instructions, 'REQUIREMENT')]))
    check('function modeling instruction does not create a controller', lambda:
          expect_equal(intake.document_component_policy('Jede Funktion wird durch Sensor-/Aktuatormapping und HMI-Zustände beschrieben.'),
                       {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}))

    for caption in ['Regulatorische Anforderungen', 'Regulatory Requirements']:
        source = '# Device\n## 7. ' + caption + '\n### 7.2 ISO-Normen\nISO 24089 Software-Updates\n'
        check('standards remain normative: ' + caption, lambda source=source:
              expect_equal([(u['text'], u['policy']['kind'], u['required']) for u in units(source)],
                           [('ISO 24089 Software-Updates', 'REQUIREMENT', True)]))
        check('normative context survives section boundary: ' + caption, lambda caption=caption:
              expect_equal(units('ISO 24089 Software-Updates\n', '# Device\n## 7. ' + caption + '\n### 7.2 ISO-Normen\n')[0]['policy']['kind'], 'REQUIREMENT'))

    table = '# Facility\n## Capabilities\n| Function group | Description |\n|---|---|\n| Emergency Stop | Operator command and HMI feedback. |\n| Recovery | Sensors and actuators are reset. |\n'
    check('function table retains both complete source rows', lambda:
          expect_equal([(u['text'], u['required'], u['policy']['kind'], u['policy']['role']) for u in units(table)],
                       [('| Emergency Stop | Operator command and HMI feedback. |', True, 'FUNCTION', 'OTHER'),
                        ('| Recovery | Sensors and actuators are reset. |', True, 'FUNCTION', 'OTHER')]))
    check('normative table row stays a requirement', lambda:
          expect_equal(units('# Facility\n## Functions\n| Function | Description |\n|---|---|\n| Stop | Controller shall stop the actuators. |')[0]['policy']['kind'], 'REQUIREMENT'))

    for sentence in ['The architecture is composed of 2 controllers and 3 sensors',
                     'Die Architektur wird aus zwei Controllern und drei Sensoren gebildet']:
        check('descriptive quantities survive: ' + sentence, lambda sentence=sentence:
              expect_equal([(u['policy']['kind'], u['policy']['role'], u['policy']['quantity']) for u in units(sentence)],
                           [('INSTANCE', 'CONTROLLER', 2), ('INSTANCE', 'SENSOR', 3)]))

    for source in ['# Facility\n## Architektur\nController: SPS\n2 Sensoren\n',
                   '# Spacecraft\n## Architecture\nController: OBC\n2 sensors\n']:
        check('hardware and quantity preserved: ' + source.splitlines()[0], lambda source=source:
              expect_equal([(u['policy']['kind'], u['policy']['role'], u['policy']['quantity']) for u in units(source)],
                           [('CATEGORY', 'CONTROLLER', None), ('INSTANCE', 'SENSOR', 2)]))
    result = {'scope': 'Pure deterministic staged-parser checks, NOT native Qwen or simulation',
              'canonical_writes': False, 'inference_calls': 0, 'cases': results,
              'passed': sum(item['status'] == 'PASSED' for item in results),
              'failed': sum(item['status'] == 'FAILED' for item in results)}
    (OUT / 'staged-checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
    raise SystemExit(bool(result['failed']))


if __name__ == '__main__':
    run()
