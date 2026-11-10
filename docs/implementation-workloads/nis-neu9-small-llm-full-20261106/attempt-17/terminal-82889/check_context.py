"""Read-only token admission of the saved complete terminal context; no generation."""
import ast
import asyncio
import hashlib
import json
from pathlib import Path
import sys

import httpx

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration import local_reasoner as r
from backend.nis.agent.orchestration.reference_token_budget import ReferenceTokenBudget
from backend.nis.engineering.communication.device_communication import FUNCTIONAL_DEVICE_REASONING_RULES
from backend.nis.engineering.structure.spatial_architecture import REASONING_RULES

OUT = Path(__file__).resolve().parent


async def main():
    source = OUT / 'complete-context.json'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == 'bd47fa3b6cd6dd97770475518cc37857d36cdd2b38801a146602da0667ad6182'
    context = json.loads(source.read_text(encoding='utf8'))
    tree = ast.parse((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_text(encoding='utf8'))
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == 'plan_reference_design')
    expression = next(n.value for n in ast.walk(method) if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'system' for t in n.targets))
    system = eval(compile(ast.Expression(expression), '<actual-product-system>', 'eval'), globals())
    messages, _, _ = r._reference_context_messages([], None, context, system, 131072,
        capacity_check=lambda messages, maximum: maximum)
    # The lambda captures the existing pure serializer only. Admission below
    # still uses the unchanged product guard and verified native token count.
    (OUT / 'reconstructed-messages.json').write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding='utf8')
    async with httpx.AsyncClient(timeout=40, trust_env=False) as client:
        health = await client.get('http://127.0.0.1:13503/health')
        health.raise_for_status()
        budget = ReferenceTokenBudget(client, 'http://127.0.0.1:11434/api/chat', 'qwen3.5:9b', 131072,
                                      bridge_url='http://127.0.0.1:13503/tokenize-chat')
        proof = await budget._measure(messages)
        result = {'context_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                  'scope': 'Complete saved context reserialized by unchanged product builder; original lost wire ordering/history not asserted',
                  'generation_requests': 0, 'original_acceptance': False,
                  'input_utf8_bytes': sum(len(m['content'].encode('utf8')) for m in messages),
                  'maximum': 131072, 'output_reserve': 8192, 'framing_reserve': 2048,
                  'host_health': health.json(), 'proof': proof}
        if proof:
            result['required_with_reserves'] = proof['input_tokens'] + 8192 + 2048
            result['fits'] = result['required_with_reserves'] <= 131072
            result['admitted_context'] = await budget.admit(messages)
        (OUT / 'restored-token-admission.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps({k: result.get(k) for k in ('input_utf8_bytes', 'required_with_reserves', 'fits', 'admitted_context')}))
        assert proof and result['fits'], 'No verified admission'


if __name__ == '__main__':
    asyncio.run(main())
