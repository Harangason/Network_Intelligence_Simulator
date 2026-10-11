from pathlib import Path
from html.parser import HTMLParser
class Links(HTMLParser):
 def handle_starttag(self,tag,attrs):
  if tag=='a':
   for k,v in attrs:
    if k=='href'and'.zip'in v:print(v)
for name in('source1.html','source2.html','source3.html'):
 print(name);Links().feed(Path('work/usb-primary',name).read_text(encoding='utf-8'))
