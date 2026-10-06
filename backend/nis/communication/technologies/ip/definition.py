"""Canonical ip profile: preserved verified parameters and capabilities."""
import json
from pathlib import Path
PROFILE = json.loads(Path(__file__).with_name('profile.json').read_text(encoding='utf-8'))
