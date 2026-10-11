from pathlib import Path
p=Path('backend/communication/technologies/tcp.py')
s=p.read_text().replace("'min':","'minimum':").replace("'max':","'maximum':").replace("'integer_power':","'power':")
s=s.replace("else RTO if k=='sample_retransmitted'else BASE", "else RTO if k in('sample_retransmitted','rto_cap_enabled')else BASE")
p.write_text(s)
