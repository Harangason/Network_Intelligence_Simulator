from pathlib import Path
import re
s=Path('work/tcp-primary/source5.html').read_text()
print('\n'.join(re.findall(r'alttext="([^"]+)',s))[:3500])
s=Path('work/tcp-primary/source5.txt').read_text()
a=s.find('4.6.  Multiplicative Decrease',1000)
a=s.find('ssthresh',max(a,0))
print(s[a-200:a+1000])
