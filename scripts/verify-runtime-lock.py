"""Fail the image build when its installed runtime differs from the exact lock."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def parse_pins(text: str) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s;]+)', line)
        if not match:
            raise ValueError(f'Expected an exact package pin, received: {line}')
        name = re.sub(r'[-_.]+', '-', match[1]).lower()
        if name in pins:
            raise ValueError(f'Duplicate package pin: {name}')
        pins[name] = match[2]
    return pins


def differences(locked: dict[str, str], installed: dict[str, str]) -> list[str]:
    return [f'{name}: locked={locked.get(name, "MISSING")}, installed={installed.get(name, "MISSING")}'
            for name in sorted(locked.keys() | installed.keys()) if locked.get(name) != installed.get(name)]


def main() -> int:
    lock = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'backend/requirements.lock'
    installed = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    mismatch = differences(parse_pins(lock.read_text(encoding='utf-8')), parse_pins(installed))
    if mismatch:
        print('Runtime dependencies differ from requirements.lock:\n' + '\n'.join(mismatch), file=sys.stderr)
        return 1
    print('Every installed runtime dependency matches requirements.lock.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
