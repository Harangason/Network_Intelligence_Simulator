"""Reuse the verified archival procedure for one explicitly identified old FAIL image."""
from pathlib import Path
here=Path(__file__).resolve().parent
source=here.parent/'multi-window-analysis-20261011/archive_failed_b9804dd2b416.py'
text=source.read_text(encoding='utf-8')
text=text.replace('backend/test-output/release-gates/delivery-a25a8a753c3a/b9804dd2b416/receipt.json','backend/test-output/release-gates/duration-intent-d7d049e2b8d6/860f9d4a7375/receipt.json')
text=text.replace('b9804dd2b416','b3017a762dc0')
text=text.replace('sha256:c4edab8e68f8d119c5239a7b1d873f1b9fcc8084cccacdad690bbe82a7cd706d','sha256:66df226713c920c8b4f26da98f3415b1c16482ee9f2883a024fb13222f69c90d')
text=text.replace('sha256:04d9a791b807799cbec822820db86f00ccd1554910f44cc1b01f3de5e59749c5','sha256:3c3562900fc255344f65bdcf5c4cb2791685bd2532e220ff647c9ad48af48854')
text=text.replace('The multi-window candidate failed the complete release gate and cannot be delivered with a FAIL receipt.','This older unused candidate has only FAIL receipts and cannot be delivered with them.')
target=here/'archive_failed_b3017a762dc0.py'
assert not target.exists()
target.write_text(text,encoding='utf-8')
print('EXACT_ARCHIVE_HELPER_PREPARED_NO_DELETION')
