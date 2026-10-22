from pathlib import Path
OUT = Path(__file__).parent
p = OUT / 'semantic-staged/frontend/src/features/agent/lib/engineering-specification.ts'
s = p.read_text(encoding='utf-8')
s = s.replace("const reviewedSourceLines = (item: { source_quote: string; source_context?: string[] }) =>", "const reviewedSourceLines = (item: { source_quote: string; source_context?: string[] }, fallbackName: string) =>")
s = s.replace("if (matches.length !== 1) return [item.source_quote];", "if (matches.length !== 1) return [fallbackName];")
s = s.replace('reviewedSourceLines(item)', 'reviewedSourceLines(item, name)')
p.write_text(s, encoding='utf-8')
p = OUT / 'semantic-staged/backend/tests/test_qwen_document_intake.py'
s = p.read_text(encoding='utf-8').replace("    assert len(functions) == 1 and functions[0]['required']\n    assert 'Mode Management' in functions[0]['text'] and 'Manuelle Steuerung des Arms' in functions[0]['text']", "    assert [unit['text'] for unit in functions] == ['Mode Management', 'FDIR', 'Manuelle Steuerung des Arms']\n    assert all(unit['required'] for unit in functions)\n    assert functions[0]['source_quote'] == functions[1]['source_quote'] == 'Mode Management, FDIR'")
p.write_text(s, encoding='utf-8')
