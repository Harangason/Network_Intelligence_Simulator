"""Published historical file entrypoint; CAN implementation has one owner."""
import sys
from pathlib import Path
sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if p.name == 'backend').parent))
from backend.nis.communication.technologies.can.formats.archived_example import *

if __name__ == '__main__':
    main()
