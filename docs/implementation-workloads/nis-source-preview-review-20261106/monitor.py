"""Read the active receipt and logs without starting any work."""
from pathlib import Path
import json
import re

folder = Path('backend/test-output/release-gates/delivery-6127991a9e47/4310b821dab9')
receipt = json.loads((folder / 'receipt.json').read_text(encoding='utf-8'))
backend = (folder / 'backend-tests.log').read_text(encoding='utf-8', errors='replace') if (folder / 'backend-tests.log').exists() else ''
browser = (folder / 'browser-e2e.log').read_text(encoding='utf-8', errors='replace') if (folder / 'browser-e2e.log').exists() else ''
progress = re.findall(r'([.FsEx]+)\s*(?:\[\s*(\d+)%\])?$', backend, re.M)
percent = re.findall(r'\[\s*(\d+)%\]', backend)
browser_ok = re.findall(r'\bok\s+(\d+)\b', browser)
print(json.dumps({'status': receipt['status'], 'checks': receipt['checks'],
    'backend_percent': percent[-1] if percent else None,
    'progress_markers': sum(len(row[0]) for row in progress),
    'failure_markers': sum(row[0].count('F') for row in progress),
    'backend_summary': re.findall(r'[^\n]*\d+ passed[^\n]*', backend)[-1:],
    'browser_last_ok': int(browser_ok[-1]) if browser_ok else 0,
    'image_id': receipt.get('image_id'), 'error': receipt.get('error')}))
