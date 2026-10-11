"""Canonical project folders for server-side saves and simulation output."""
from pathlib import Path
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from uuid import uuid4
from backend.nis.infrastructure.paths import PROJECT_ROOT
from backend.nis.infrastructure.paths import RUNTIME_ROOT
from backend.nis.infrastructure.paths import DATA_ROOT
from backend.nis.engineering.projects.project_context import normalize_context_project_id

def saved_root() -> Path:
    configured = os.environ.get('SIMULATOR_SAVED_ROOT')
    if configured:
        return Path(configured).expanduser().resolve()
    if os.environ.get('SIMULATOR_RUNTIME_ROOT'):
        return (DATA_ROOT / 'saved').resolve()
    return (DATA_ROOT / 'projects').resolve()

def project_folder(project_id: str) -> Path:
    key = normalize_context_project_id(project_id)
    if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9._-]{0,79}', key) or key in ('.', '..'):
        raise ValueError('Ungültige Projekt-ID für den Speicherordner.')
    root = saved_root()
    folder = (root / key).resolve()
    if folder.parent != root or (root / key).is_symlink():
        raise ValueError('Projektordner liegt außerhalb von SAVED.')
    return folder

def _save_json(project_id: str, filename: str, document: dict) -> Path:
    folder = project_folder(project_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    if target.is_symlink() or target.resolve().parent != folder:
        raise ValueError('Projektdatei liegt außerhalb des Projektordners.')
    _replace_bytes(target, json.dumps(document, ensure_ascii=False, default=str).encode('utf-8'))
    return target


def _replace_bytes(target: Path, content: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=target.parent, suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def save_bundle(bundle: dict) -> Path:
    if isinstance(bundle.get('workflow'), dict):
        # Project export is also usable outside an engineering transaction.
        from backend.nis.infrastructure.persistence.db import get_connection
        with get_connection() as connection:
            stage_user_defined_values(bundle['project_id'], bundle['workflow'].get('parameters') or {}, connection)
    return _save_json(bundle['project_id'], 'project.nis-project.json', bundle)


def user_defined_values_path(project_id: str) -> Path:
    folder = project_folder(project_id)
    target = folder / 'user_defined_values.json'
    if target.is_symlink() or target.resolve().parent != folder:
        raise ValueError('Nutzerwert-Datei liegt außerhalb des Projektordners.')
    return target


def user_defined_values_document(project_id: str, parameters: dict) -> dict:
    """Project configuration, never a new TechnologyProfile or evidence claim."""
    if not isinstance(parameters, dict):
        raise ValueError('Projektparameter müssen ein Objekt sein.')
    return {'schema_version': 1, 'project_id': normalize_context_project_id(project_id),
            'value_origin': 'USER_DEFINED_VALUE',
            'revision': uuid4().hex,
            'updated_at': datetime.now(timezone.utc).isoformat(),
            # Catalog proposals are references supplied by TechnologyProfile;
            # they must not become project-owned default definitions.
            'parameters': {key: value for key, value in parameters.items()
                           if key not in {'technology_defaults', 'defaults_source'}}}


def save_user_defined_values(project_id: str, parameters: dict) -> Path:
    return _save_json(project_id, 'user_defined_values.json',
                      user_defined_values_document(project_id, parameters))


def load_user_defined_values(project_id: str) -> dict | None:
    target = user_defined_values_path(project_id)
    from backend.nis.infrastructure.persistence.db import transaction_resource
    pending = transaction_resource(str(target))
    if pending is not None:
        document = pending.document
        if document is None:
            return None
    else:
        if not target.exists():
            return None
        document = json.loads(target.read_text(encoding='utf-8'))
    if (not isinstance(document, dict) or document.get('schema_version') != 1
            or document.get('project_id') != normalize_context_project_id(project_id)
            or document.get('value_origin') != 'USER_DEFINED_VALUE'
            or not isinstance(document.get('parameters'), dict)):
        raise ValueError('Ungültige projektspezifische Nutzerwerte.')
    return document


class _ProjectValueWrite:
    """Atomic replacement with compensation if the SQL commit fails."""
    def __init__(self, project_id: str, document: dict | None):
        self.project_id = project_id
        self.document = document
        self.previous: bytes | None = None
        self.prepared = False

    def prepare(self) -> None:
        if self.prepared:
            return
        target = user_defined_values_path(self.project_id)
        self.previous = target.read_bytes() if target.exists() else None
        if self.document is None:
            target.unlink(missing_ok=True)
        else:
            _save_json(self.project_id, target.name, self.document)
        self.prepared = True

    def rollback(self) -> None:
        if not self.prepared:
            return
        target = user_defined_values_path(self.project_id)
        if self.previous is None:
            target.unlink(missing_ok=True)
        else:
            _replace_bytes(target, self.previous)
        self.prepared = False


def stage_user_defined_values(project_id: str, parameters: dict | None, connection) -> None:
    from backend.nis.infrastructure.persistence.db import enlist_transaction_resource
    document = user_defined_values_document(project_id, parameters) if parameters is not None else None
    # Freeze the submitted JSON so subsequent derived operations cannot alter it.
    if document is not None:
        document = json.loads(json.dumps(document, default=str))
    # Readers only use the file belonging to their committed SQL snapshot.
    # Publishing the file before COMMIT therefore cannot expose pending values.
    connection.execute(
        "UPDATE engineering_workflow_projects SET context = jsonb_set(COALESCE(context, '{}'::jsonb), "
        "'{_user_values_revision}', %s::jsonb) WHERE project_id = %s",
        (json.dumps(document['revision'] if document else None), normalize_context_project_id(project_id)),
    )
    enlist_transaction_resource(str(user_defined_values_path(project_id)),
                                _ProjectValueWrite(project_id, document))


def committed_user_defined_values(project_id: str, context: dict) -> dict | None:
    document = load_user_defined_values(project_id)
    if document is None or document.get('revision') != context.get('_user_values_revision'):
        return None
    return document


def project_parameter_values(project_id: str, legacy: dict, context: dict) -> dict:
    document = committed_user_defined_values(project_id, context)
    if document is None:
        return legacy
    return {**{key: legacy[key] for key in ('technology_defaults', 'defaults_source') if key in legacy},
            **document['parameters']}
