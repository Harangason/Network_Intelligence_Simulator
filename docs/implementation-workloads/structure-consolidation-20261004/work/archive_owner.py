import json
from edit_utils import read, write, extract, apply

old = 'backend/nis/simulation/Archiv/generate_realistic_can_blf.py'
new = 'backend/nis/communication/technologies/can/formats/archived_example.py'
source = read(old)
# The archive has a different historical message API. Preserve it exactly;
# its identical CRC primitive is shared with the current encoding owner.
_, source = extract(source, {'crc8_autosar'})
source = source.replace('import can\n', 'import can\nfrom backend.nis.communication.technologies.can.encoding import crc8_autosar\n', 1)
write(new, source)
write(old, '''"""Published historical file entrypoint; CAN implementation has one owner."""
import sys
from pathlib import Path
sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if p.name == 'backend').parent))
from backend.nis.communication.technologies.can.formats.archived_example import *

if __name__ == '__main__':
    main()
''')
aliases = json.loads(read('backend/nis/compatibility.json'))
for key,value in list(aliases.items()):
    if value == old[:-3].replace('/', '.'):
        aliases[key] = new[:-3].replace('/', '.')
write('backend/nis/compatibility.json', json.dumps(aliases, indent=2, ensure_ascii=False) + '\n')
apply('archive-can-owner')
