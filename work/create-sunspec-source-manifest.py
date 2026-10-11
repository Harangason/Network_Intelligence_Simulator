import hashlib,json
from pathlib import Path
folder=Path('work/sunspec_modbus-primary')
path=folder/'web-reader.txt'
urls=['https://sunspec.org/wp-content/uploads/2025/01/SunSpec-Device-Information-Model-Specificiation-V1-1-final.pdf','https://sunspec.org/wp-content/uploads/2009/03/Secure-SunSpec-Modbus-Specification_final.pdf']
items=[dict(url=url,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),kind='PRIMARY_WEB_EXTRACT',note='Publisher direct GET403. Actual selected web-reader extracts; no original PDF byte/hash claim.')for url in urls]
app=Path('work/modbus-primary/application.pdf')
items.append(dict(url='https://www.modbus.org/file/secure/modbusprotocolspecification.pdf',path=str(app),sha256=hashlib.sha256(app.read_bytes()).hexdigest(),kind='ORIGINAL_PRIMARY'))
(folder/'manifest.json').write_text(json.dumps(items,indent=2)+'\n')
