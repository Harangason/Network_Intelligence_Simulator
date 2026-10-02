from pathlib import Path
from html.parser import HTMLParser
class H(HTMLParser):
 def __init__(self):super().__init__();self.a=[]
 def handle_data(self,d):
  if d.strip():self.a.append(d.strip())
h=H();h.feed(Path('work/profibus-primary/abb-master.html').read_text());text='\n'.join(h.a);Path('work/profibus-primary/abb-master.txt').write_text(text,encoding='utf-8');start=text.find('The following parameters');print(text[start:start+10000])
for name,ranges in [('system2016',[(645,715),(1110,1230)]),('step7v13',[(1230,1320)])]:
 lines=Path('work/profibus-primary/'+name+'.txt').read_text(encoding='utf-8').splitlines()
 for low,high in ranges:print(name,low,high,'\n'+'\n'.join(lines[low:high]))
