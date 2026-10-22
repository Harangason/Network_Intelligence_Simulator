"""Verify the requested file bytes and the complete decoded upload text."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

OUT = Path(__file__).resolve().parent
source = Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/INDUSTRIEPORTFOLIO_100_KATEGORIENPAKET/D_INDUSTRIAL_ROBOTICS_054_063.md')
raw = source.read_bytes()
text = raw.decode('utf-8-sig')
digest = hashlib.sha256(raw).hexdigest()
text_digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
expected = '8fc201a55e8b0afeb7b708ac70abd0c72a7b25eb17d90fceca71d80a291f3cef'
assert digest == expected and text_digest == expected and len(text) == 63705
report = {'status': 'PASSED_COMPLETE_ORIGINAL_FILE_IDENTITY', 'at_utc': datetime.now(timezone.utc).isoformat(),
    'path': str(source), 'name': source.name, 'file_sha256': digest, 'upload_text_sha256': text_digest,
    'file_bytes': len(raw), 'text_chars': len(text), 'encoding': 'UTF-8',
    'scope': 'Complete original bytes and decoded upload text only; no source changes, Native inference, canonical model or simulation proof.'}
(OUT / 'original-robot-source-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
