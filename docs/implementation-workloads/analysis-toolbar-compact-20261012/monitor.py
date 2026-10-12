import json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
folders=sorted((ROOT/'backend/test-output/release-gates').glob('delivery-*'),key=lambda p:p.stat().st_mtime,reverse=True)
receipt_paths=list(folders[0].glob('*/receipt.json'))
result={'latest_delivery':folders[0].name,'status':'STARTING'}
if receipt_paths:
    path=receipt_paths[0];receipt=json.loads(path.read_text(encoding='utf-8-sig'))
    result.update(receipt=str(path),status=receipt['status'],checks=receipt.get('checks',[]),image=receipt.get('image_id'),error=receipt.get('error'))
    logs=sorted(path.parent.glob('*.log'),key=lambda p:p.stat().st_mtime,reverse=True)
    if logs:
        latest=logs[0];result['latest_log']=latest.name;result['tail']=latest.read_text(encoding='utf-8',errors='replace')[-450:]
launcher=(HERE/'delivery.log').read_text(encoding='utf-8',errors='replace');errors=(HERE/'delivery-errors.log').read_text(encoding='utf-8',errors='replace')
result['launcher_tail']=launcher[-700:];result['launcher_errors']=errors[-700:]
print(json.dumps(result,ensure_ascii=True))
