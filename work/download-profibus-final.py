from pathlib import Path
import json,hashlib,httpx
from pypdf import PdfReader
from html.parser import HTMLParser
p=Path('work/profibus-primary');m=json.loads((p/'manifest.json').read_text())
urls={'saia2019':'https://sbc-support.com/uploads/tx_srcproducts/26-860_ENG_Manual_ProfibusDP.pdf',
 'abb-physical':'https://help.plc.abb.com/PROFIBUS_connection.html',
 'pno1997':'https://www.newelec.co.za/wp-content/uploads/2017/05/ProfiBus-Specifications-v1_00.pdf'}
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,data):self.parts.append(data)
with httpx.Client(timeout=35,follow_redirects=True)as c:
 for name,url in urls.items():
  try:
   r=c.get(url);r.raise_for_status();suffix='.pdf'if r.content.startswith(b'%PDF')else'.html';target=p/(name+suffix);target.write_bytes(r.content)
   if suffix=='.pdf':
    rd=PdfReader(target);pages=range(len(rd.pages))if name!='pno1997'else list(range(117,138))+list(range(883,909))
    content='\n'.join('PAGE '+str(i+1)+'\n'+(rd.pages[i].extract_text()or'')for i in pages)
   else:
    parser=Text();parser.feed(r.text);content='\n'.join(parser.parts)
   (p/(name+'.txt')).write_text(content,encoding='utf-8');m.append(dict(url=url,path=str(target),sha256=hashlib.sha256(r.content).hexdigest(),kind=suffix));print(name,len(r.content))
  except Exception as e:print(name,type(e).__name__,str(e)[:120])
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
