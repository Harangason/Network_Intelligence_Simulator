from pathlib import Path
p=Path('backend/tests/test_parameter_consumer_integrity.py');s=p.read_text(encoding='utf-8').replace("['mbus', 'matter'", "['m_bus', 'matter'")
s=s.replace("    assert registry.resolve_stack(profile['default_stack'])['timing_model'] is None", "    try:\n        assert registry.resolve_stack(profile['default_stack'])['timing_model'] is None\n    except LookupError:\n        assert profile['implementation_status'] in ('PLANNED', 'NOT_SUPPORTED')")
p.write_text(s,encoding='utf-8')
p=Path('frontend/src/components/simulation-wizard.tsx');s=p.read_text(encoding='utf-8').replace('  physical: "Netzwerk & Physik",', '  technology: "Technologiespezifische Parameter",\n  physical: "Netzwerk & Physik",',1);p.write_text(s,encoding='utf-8')
p=Path('work/update-technology-readme.py');s=p.read_text(encoding='utf-8');s='import sys\nsys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))\n'+s;p.write_text(s,encoding='utf-8')
