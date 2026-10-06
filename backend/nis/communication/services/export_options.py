"""Read existing technology-owned example CLI choices, never project defaults."""
import json
from pathlib import Path

def example_bitrate_choices(technology_id):
    """Project preserved demonstration choices without registering parameters."""
    path = Path(__file__).parents[1] / 'technologies' / technology_id / 'export-options.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['project_defaults'] is False
    return dict(data['choices'])
