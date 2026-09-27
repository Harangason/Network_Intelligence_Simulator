"""Read-only discovery of a configured project master; never imports or executes it."""
from pathlib import Path
import fnmatch
import os
from tool_check import read, file_hash

EIP_ROOT = Path('I:/engineering-intelligence-platform')
EIP_PATTERN = 'EIP_60_TESTS_3_RUN_ENGINEERING_ASSISTANT_MASTER*.md'
NIS_ROOT = Path('I:/PycharmProjects/My_first_Network_Simulator')
NIS_PATTERN = 'NETWORK_SIMULATOR_60_TESTS_3_RUN_ENGINEERING_ASSISTANT_MASTER_TECHNOLOGY_QUALITY_UPDATED*.md'

def policy_for(checker):
    project=Path(checker.cfg()['project']).resolve()
    config=project/'.tool-checker/config/project-cli.json'
    cfg=read(config) if config.is_file() else {}
    if 'source_discovery' in cfg:
        policy=cfg['source_discovery']
        if not isinstance(policy,dict): raise ValueError('source_discovery muss ein Objekt sein')
        return project,policy
    if project==EIP_ROOT.resolve():
        return project,{'directory':'documentation','pattern':EIP_PATTERN}
    if project==NIS_ROOT.resolve():
        return project,{'directory':'docs','pattern':NIS_PATTERN}
    return project,None

def discover(checker, *, filename=None):
    project,policy=policy_for(checker)
    if policy is None: return {'status':'NOT_CONFIGURED','candidates':[]}
    directory=policy.get('directory');pattern=filename if filename is not None else policy.get('pattern')
    if not isinstance(directory,str) or not directory or not isinstance(pattern,str) or not pattern or '/' in pattern or '\\' in pattern:
        raise ValueError('Quellensuche benötigt directory und ein Dateinamenmuster pattern')
    root=(project/directory).resolve()
    if not root.is_relative_to(project): raise ValueError('Quellensuchverzeichnis liegt außerhalb des Projekts')
    result={'status':'SOURCE_NOT_FOUND','directory':str(root),'pattern':pattern,'recursive':True,'candidates':[]}
    if not root.is_dir():return dict(result,reason='Quellensuchverzeichnis fehlt: '+str(root))
    def linked(path):
        return path.is_symlink() or bool(getattr(path.lstat(),'st_file_attributes',0)&1024)
    if any(linked(p) for p in [project/directory,*(project/directory).parents] if p!=project and p.is_relative_to(project)):
        return dict(result,status='SOURCE_SCAN_FAILED',reason='Verknüpftes Suchverzeichnis ist nicht zulässig')
    try:
        def fail(error):raise error
        matches=[]
        for folder,dirs,files in os.walk(root,followlinks=False,onerror=fail):
            dirs[:]=[d for d in dirs if not linked(Path(folder)/d)]
            for name in files:
                path=Path(folder)/name
                matches_name = name.casefold()==filename.casefold() if filename is not None else fnmatch.fnmatchcase(name.casefold(),pattern.casefold())
                if matches_name and not linked(path):matches.append(path)
        result['candidates']=[{'path':str(path),'sha256':file_hash(path)} for path in sorted(matches)]
    except OSError as error:
        return dict(result,status='SOURCE_SCAN_FAILED',reason=str(error))
    if len(result['candidates'])==1:
        return dict(result,status='FOUND',**result['candidates'][0])
    if len(result['candidates'])>1:
        return dict(result,status='SOURCE_AMBIGUOUS',reason='Mehrere Masterdateien gefunden; Quelle ausdrücklich auswählen')
    return dict(result,reason='Keine Masterdatei gefunden in '+str(root)+' ('+pattern+')')

def issues(result):
    if result['status'] in ('FOUND','NOT_CONFIGURED'):return []
    return [result['status']+': '+result.get('reason','Quellensuche prüfen')]

def display(result,output):
    if result['status']=='NOT_CONFIGURED':return
    output('Masterquellensuche: '+result['directory']+' (rekursiv)')
    if result['status']=='FOUND':output('Masterdatei: '+result['path'])
    else:
        for line in issues(result):output('BLOCKED: '+line)
        for candidate in result['candidates']:output('  '+candidate['path'])


def resolve_reference(checker, path):
    """Resolve moved references in this project's docs; caller still checks its pinned hash.

    Existing non-master references remain pinned. Master references outside the
    configured docs directory must use that directory, even if the old copy exists.
    No manifest, registry or historical run is rewritten.
    """
    original=Path(path)
    project,policy=policy_for(checker)
    if policy is None:return original
    # PureWindowsPath also recognizes historical Windows paths in portable tests.
    from pathlib import PureWindowsPath
    name=PureWindowsPath(str(path)).name
    directory=policy.get('directory')
    if not isinstance(directory,str) or not directory:raise ValueError('SOURCE_POLICY_INVALID: directory')
    root=(project/directory).resolve()
    if not root.is_relative_to(project):raise ValueError('Quellensuchverzeichnis liegt außerhalb des Projekts')
    master='_RUN_ENGINEERING_ASSISTANT_MASTER' in name.upper()
    if original.is_file() and (not master or original.resolve().is_relative_to(root)):
        return original
    result=discover(checker,filename=name)
    if result['status']=='FOUND':return Path(result['path'])
    raise ValueError(result['status']+': '+name+'; Suchverzeichnis: '+str(root))
