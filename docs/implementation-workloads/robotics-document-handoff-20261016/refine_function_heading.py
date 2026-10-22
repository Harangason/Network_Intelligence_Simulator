from pathlib import Path
p = Path(__file__).parent / 'semantic-staged/backend/nis/agent/orchestration/project_intake.py'
s = p.read_text(encoding='utf-8')
old = "        # Markdown headings and two-column numbered index rows navigate the"
new = "        if function_header:\n            continue  # A structural function caption is not an executable duty.\n        # Markdown headings and two-column numbered index rows navigate the"
assert old in s
p.write_text(s.replace(old, new), encoding='utf-8')
