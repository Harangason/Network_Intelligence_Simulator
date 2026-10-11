from pathlib import Path
import hashlib
import json
from backend.communication.technologies.sources import canonical_source_url

root=Path(__file__).resolve().parents[1]
path=root/'backend/communication/technologies/source_metadata.json'
data=json.loads(path.read_text(encoding='utf-8'))
data['rights_rules']['APACHE_2_FILE_NOTICE']={
 'publication':'CONDITIONAL','label':'Apache-2.0 · Bedingungen erhalten',
 'explanation':'Der Copyright-/Lizenzkopf dieser konkreten SDK-Datei nennt Apache License 2.0. Weitergabe und Änderungen unter deren Bedingungen, insbesondere Lizenzkopie, Änderungskennzeichnung sowie erforderlichen Copyright-/NOTICE-Angaben. Patent-/Markenrechte, Fremdteile und die separat geschützte Matter-Spezifikation sind dadurch nicht allgemein freigegeben.',
 'evidence_url':'https://www.apache.org/licenses/LICENSE-2.0',
 'review_status':'EXACT_PINNED_FILE_LICENSE_NOTICE_REVIEWED'}
manifest=json.loads((root/'work/matter-primary/sdk-manifest.json').read_text(encoding='utf-8'))
checked=0
for item in manifest:
 file=root/'work/matter-primary/sdk'/item['path']
 if not file.exists(): continue
 if hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']: raise ValueError('Cached file drift')
 notice=file.read_text(encoding='utf-8')[:2200]
 if 'Licensed under the Apache License, Version 2.0' not in notice: continue
 url=canonical_source_url(item['url'])
 meta=data['sources'].setdefault(url,{'publisher':'Project CHIP Authors'})
 meta['technology_ids']=sorted(set([*meta.get('technology_ids',[]),'matter']))
 meta.update(rights_rule='APACHE_2_FILE_NOTICE',
    file_notice_sha256=item['sha256'],name='Matter SDK – '+item['path'].rsplit('/',1)[-1])
 checked+=1
access=json.loads((root/'work/matter-primary/source-access.json').read_text(encoding='utf-8'))
data['sources'][canonical_source_url(access['download_url'])].update(
 accessed_at=access['recorded_at'][:10],access_date_basis='RECORDED_OFFICIAL_PDF_ACQUISITION',
 document_sha256=access['sha256'])
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'file_notices_checked':checked,'core_document_notice':'PDF page 5, original hash verified in acquisition record'}))
