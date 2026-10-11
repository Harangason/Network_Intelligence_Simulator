"""Finite legacy module aliases; no duplicate execution or registration.

Remove an alias after all supported CLI, persisted-module and external consumers
have migrated. Canonical internal code imports backend.nis directly.
"""
import importlib
import importlib.abc
import importlib.util
import json
import sys
from pathlib import Path

ALIASES = json.loads(Path(__file__).with_name('compatibility.json').read_text(encoding='utf-8'))

class AliasLoader(importlib.abc.Loader):
    def __init__(self, target):
        self.target = target
    def create_module(self, spec):
        return importlib.import_module(self.target)
    def get_code(self, fullname):
        spec = importlib.util.find_spec(self.target)
        return spec.loader.get_code(self.target)
    def exec_module(self, module):
        pass

class LegacyImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        canonical = ALIASES.get(fullname)
        if canonical is None:
            return None
        actual = importlib.util.find_spec(canonical)
        return importlib.util.spec_from_loader(fullname, AliasLoader(canonical),
                                              is_package=actual.submodule_search_locations is not None)

def install():
    if not any(isinstance(finder, LegacyImports) for finder in sys.meta_path):
        sys.meta_path.insert(0, LegacyImports())
