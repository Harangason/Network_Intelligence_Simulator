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
            ProjectArtifactStore(bundle['project_id']).stage_snapshot(bundle)
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
    from backend.nis.infrastructure.persistence.db import mark_project_files_changed
    mark_project_files_changed()
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


class ProjectArtifactStore:
    """Revisioned file projections of the canonical DB and frozen run inputs."""
    def __init__(self, project_id):
        self.project_id = normalize_context_project_id(project_id)
        self.folder = project_folder(self.project_id)

    def path(self, relative):
        relative = Path(relative)
        if relative.is_absolute() or not relative.parts or any(p in {'.', '..'} for p in relative.parts):
            raise ValueError('Artifact path must be relative to its project.')
        target = self.folder / relative
        if not target.resolve().is_relative_to(self.folder):
            raise ValueError('Artifact path escapes the project folder.')
        current = target
        while current != self.folder:
            if current.is_symlink():
                raise ValueError('Project artifacts may not use symbolic links.')
            current = current.parent
        return target

    @staticmethod
    def encode(document):
        return json.dumps(document, sort_keys=True, ensure_ascii=False, default=str, allow_nan=False).encode('utf-8')

    @staticmethod
    def digest(content):
        from hashlib import sha256
        return sha256(content).hexdigest()

    @staticmethod
    def file_digest(path):
        from hashlib import sha256
        digest = sha256()
        with Path(path).open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    def write(self, relative, content, *, immutable=True):
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        if immutable and target.exists():
            if target.read_bytes() != content:
                raise ValueError('Historical artifact revision cannot be overwritten.')
        else:
            _replace_bytes(target, content)
        return {'path':str(target.relative_to(self.folder)), 'sha256':self.digest(content), 'bytes':len(content)}

    def stage(self, relative, content, *, immutable=True):
        from backend.nis.infrastructure.persistence.db import enlist_transaction_resource
        target = self.path(relative)
        enlist_transaction_resource(str(target), _ProjectArtifactWrite(self, relative, content, immutable))
        return {'path':str(target.relative_to(self.folder)), 'sha256':self.digest(content), 'bytes':len(content)}

    def stage_block(self, definition):
        source = definition['source_code'].encode('utf-8')
        revision = self.digest(source)
        if definition.get('source_sha256') != revision:
            raise ValueError('Code revision differs from reviewed source.')
        # Sources are project data; they are never imported as unrestricted Python.
        code = self.stage(f'logic/blocks/{revision}/source.py', source)
        encoded = self.encode(definition)
        metadata = self.stage(f'logic/blocks/{revision}/definitions/{self.digest(encoded)}.json', encoded)
        return {'source':code, 'definition':metadata}

    def stage_snapshot(self, bundle):
        from copy import deepcopy
        document = deepcopy(bundle)
        document.pop('generated_at', None)
        parameters = ((document.get('workflow') or {}).get('parameters') or {})
        defaults = {key:parameters.pop(key) for key in ('technology_defaults', 'defaults_source') if key in parameters}
        document['default_references'] = {'owner':'TechnologyProfile', 'definition_sha256':self.digest(self.encode(defaults)),
            'technology_ids':sorted((defaults.get('technology_defaults') or {}).keys())
                if isinstance(defaults.get('technology_defaults'), dict) else [],
            'storage':'Original NIS catalog; not copied into the project'}
        content = self.encode(document)
        revision = self.digest(content)
        ref = self.stage(f'revisions/{revision}/project.nis-project.json', content)
        blocks = []
        for behavior in (document.get('project_data') or {}).get('engineering_signal_behaviors') or []:
            definition = (behavior.get('parameters') or {}).get('function_block')
            if behavior.get('behavior_type') == 'FUNCTION_BLOCK' and definition:
                blocks.append(self.stage_block(definition))
        manifest = {'schema_version':1, 'project_id':self.project_id, 'revision':revision,
            'model_authority':'Canonical project database', 'project':ref, 'function_blocks':blocks,
            'directories':{'revisions':'revisions/', 'function_code':'logic/blocks/',
                'simulation_values_and_captures':'runs/', 'original_imported_traces':'trace-imports/'},
            'default_references':document['default_references']}
        self.stage(f'revisions/{revision}/manifest.json', self.encode(manifest))
        self.stage('manifest.json', self.encode(manifest), immutable=False)
        return manifest

    def begin_run(self, run_id, config):
        # Run IDs are directories, never arbitrary filesystem paths.
        if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9._-]{0,119}', str(run_id)):
            raise ValueError('Invalid simulation run identity.')
        from copy import deepcopy
        from backend.nis.app.build_info import build_info
        snapshot = deepcopy(config)
        defaults = {}
        for owner in (snapshot.get('parameters'), (snapshot.get('engineering_model') or {}).get('parameters')):
            if isinstance(owner, dict):
                for key in ('technology_defaults', 'defaults_source'):
                    if key in owner:
                        defaults[key] = owner.pop(key)
        snapshot.pop('output_dir', None)
        document = {'schema_version':1, 'project_id':self.project_id, 'configuration':snapshot,
            'nis_build':build_info(), 'default_reference_sha256':self.digest(self.encode(defaults)),
            'interpretation':'Frozen simulation design; transport is not physical detection or functional acceptance'}
        content = self.encode(document)
        revision = self.digest(content)
        base = f'runs/{run_id}'
        self.write(base + '/revision/inputs.json', content)
        self.write(base + '/revision/status.json', self.encode({'status':'RUNNING', 'input_revision':revision}), immutable=False)
        return {'run_id':str(run_id), 'base':base, 'input_revision':revision,
            'project_id':self.project_id, 'nis_build':document['nis_build']}

    def finish_run(self, run, output_dir, result=None, error=None):
        import shutil
        output = Path(output_dir).resolve()
        destination = self.path(run['base'])
        artifacts = []
        for source in sorted(output.rglob('*')):
            if source.is_symlink():
                raise ValueError('Simulation artifacts may not contain symbolic links.')
            if not source.is_file():
                continue
            relative = source.relative_to(output)
            # Own revision files are maintained below, outside trace inventory.
            if relative.parts[0] == 'revision':
                continue
            target = self.path(Path(run['base']) / relative)
            if source != target:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    if self.file_digest(target) != self.file_digest(source):
                        raise ValueError('Existing run artifact differs; use a new run ID.')
                else:
                    shutil.copyfile(source, target)
            digest = self.file_digest(target)
            artifacts.append({'path':str(target.relative_to(self.folder)), 'sha256':digest, 'bytes':target.stat().st_size})
        result_ref = self.write(run['base'] + '/revision/result.json', self.encode(result or {'error':str(error)}))
        manifest = {**run, 'schema_version':1, 'status':'FAILED' if error else (result or {}).get('status', 'COMPLETED'),
            'artifacts':artifacts, 'result':result_ref, 'error':str(error) if error else None,
            'comparison_policy':'Same frozen inputs/seed and independent expected outputs; no automatic training or shared-code promotion'}
        self.write(run['base'] + '/revision/manifest.json', self.encode(manifest))
        self.write(run['base'] + '/revision/status.json', self.encode({'status':manifest['status'], 'input_revision':run['input_revision']}), immutable=False)
        return manifest


class _ProjectArtifactWrite:
    """File projection enlisted in the existing DB transaction, with compensation."""
    def __init__(self, store, relative, content, immutable):
        self.store, self.relative, self.content, self.immutable = store, relative, content, immutable
        self.previous = None
        self.prepared = False

    def prepare(self):
        target = self.store.path(self.relative)
        self.previous = target.read_bytes() if target.exists() else None
        self.store.write(self.relative, self.content, immutable=self.immutable)
        self.prepared = True

    def rollback(self):
        if self.prepared:
            target = self.store.path(self.relative)
            if self.previous is None:
                target.unlink(missing_ok=True)
            elif target.read_bytes() != self.previous:
                _replace_bytes(target, self.previous)
            self.prepared = False
