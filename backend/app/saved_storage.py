"""Canonical project folders for server-side saves and simulation output."""
from pathlib import Path
import json
import os
import re
import tempfile
from .config import PROJECT_ROOT, RUNTIME_ROOT
from ..engineering.project_context import normalize_context_project_id

def saved_root() -> Path:
    configured = os.environ.get('SIMULATOR_SAVED_ROOT')
    if configured:
        return Path(configured).expanduser().resolve()
    if os.environ.get('SIMULATOR_RUNTIME_ROOT'):
        return (RUNTIME_ROOT / 'saved').resolve()
    return (PROJECT_ROOT / 'SAVED').resolve()

def project_folder(project_id: str) -> Path:
    key = normalize_context_project_id(project_id)
    if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9._-]{0,79}', key) or key in ('.', '..'):
        raise ValueError('Ungültige Projekt-ID für den Speicherordner.')
    root = saved_root()
    folder = (root / key).resolve()
    if folder.parent != root or (root / key).is_symlink():
        raise ValueError('Projektordner liegt außerhalb von SAVED.')
    return folder

def save_bundle(bundle: dict) -> Path:
    folder = project_folder(bundle['project_id'])
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / 'project.nis-project.json'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=folder, suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(bundle, handle, ensure_ascii=False, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return target
