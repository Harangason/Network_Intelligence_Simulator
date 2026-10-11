"""Workspace identity, independent of process working directory and code location."""
from pathlib import Path

BACKEND_ROOT = next(parent for parent in Path(__file__).resolve().parents if parent.name == 'backend')
PROJECT_ROOT = BACKEND_ROOT.parent
