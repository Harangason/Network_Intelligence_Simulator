from pathlib import Path
import logging
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
p=Path('work/rfid-primary')
for name,pages in [('gs1-gen2-301',[56,57,58,66,67,68,69,70,71,72,73]),('ti-hf-trf7970a',[11,12,17,40,41,42]),('ti-lf-mrd2',[72,73,74,75,76,77,78])]:
 rd=PdfReader(p/(name+'.pdf'));text='\n'.join('PDF_PAGE'+str(i)+'\n'+(rd.pages[i-1].extract_text()or'')for i in pages)
 (p/(name+'-selected.txt')).write_text(text,encoding='utf-8')
 print(name,text)
