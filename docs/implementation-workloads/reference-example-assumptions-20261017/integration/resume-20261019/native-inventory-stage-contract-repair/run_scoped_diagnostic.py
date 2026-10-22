import json,subprocess
from pathlib import Path
p=Path(__file__).resolve().parent
command=json.loads((p/"second-diagnostic-review.json").read_text(encoding="utf8"))["command"]
subprocess.run(command,check=True)
