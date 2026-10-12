from pathlib import Path
p=Path('frontend/src/features/workflow/stage_08_results_analysis/runtime-chart-tools.tsx')
s=p.read_text(encoding='utf-8')
for label in ['Diagrammtyp','Y-Skala','Sender','Empfänger','Modellsicht']:
    old=f'<label>{label}<select'
    assert old in s
    s=s.replace(old,f'<label>{label}<select aria-label="{label}"')
s=s.replace('Gespeicherte Routenmetriken der gewählten Netze:', 'Gesamter Lauf, unabhängig vom Zoom-Zeitfenster. Gespeicherte Routenmetriken der gewählten Netze:')
p.write_text(s,encoding='utf-8')
p=Path('frontend/src/features/workflow/stage_08_results_analysis/runtime-chart-data.ts')
s=p.read_text(encoding='utf-8').replace('"#41751d"','"var(--accent)"')
p.write_text(s,encoding='utf-8')
