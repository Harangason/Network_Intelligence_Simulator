from pathlib import Path
src = Path('docs/implementation-workloads/studio-layout-capacity-search-20261011/archive_development_candidate.py').read_text()
changes = {
    'candidate-ece226f96628': 'candidate-a47ee30356bb',
    'sha256:7641cc2da36683e8625632dac8d566571c464102b26de72a552ab640696d2d58': 'sha256:98b2c881bebc4232bf97747376f16139dd49a095f1f7562e76955ff18b1667fb',
    'sha256:7c4fc26963c885da6be0230f8eef158234c22ddec07ab480ceeb2186088713c1': 'sha256:04d9a791b807799cbec822820db86f00ccd1554910f44cc1b01f3de5e59749c5',
    'backend/test-output/release-gates/blocked-recheck-targeted/ece226f96628/receipt.json': 'backend/test-output/release-gates/delivery-598d59124c0b/a47ee30356bb/receipt.json',
    "receipt['status'] == 'PREPARED' and receipt['development_only'] is True": "receipt['status'] == 'FAIL'",
    'development-candidate-ece226f96628.tar': 'failed-candidate-a47ee30356bb.tar',
    'development-candidate-receipt.json': 'failed-candidate-receipt.json',
    'development-candidate-storage-review.json': 'failed-candidate-storage-review.json',
    'Only this unused development-only candidate': 'Only this unused failed candidate',
    'PREPARED': 'FAIL',
}
for old, new in changes.items():
    src = src.replace(old, new)
src = src.replace("assert command('image', 'inspect', TAG, '--format', '{{.Id}}') == IMAGE", "assert command('image', 'inspect', TAG, '--format', '{{.Id}}') == IMAGE\nassert not any(json.loads(p.read_text()).get('status') == 'PASS' and json.loads(p.read_text()).get('image_id') == IMAGE for p in (ROOT / 'backend/test-output/release-gates').rglob('receipt.json'))")
Path('docs/implementation-workloads/multi-window-analysis-20261011/archive_failed_candidate.py').write_text(src)
