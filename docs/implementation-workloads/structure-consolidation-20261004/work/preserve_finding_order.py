from edit_utils import read, write, apply

path = 'backend/nis/communication/technologies/lin/assessment.py'
source = read(path).replace('def capacity_findings(network, sizing_policy, schedule):', 'def reserve_findings(network, sizing_policy, schedule):')
source = source.replace('    schedule = network.get("lin_schedule") or {}', '    return findings\n\n\ndef budget_findings(network):\n    findings = []\n    schedule = network.get("lin_schedule") or {}',1)
write(path,source)
path = 'backend/nis/engineering/capacity/service.py'
source = read(path).replace('import capacity_findings as lin_capacity_findings', 'import reserve_findings as lin_reserve_findings, budget_findings as lin_budget_findings')
source = source.replace('findings.extend(lin_capacity_findings(network, sizing_policy, schedule))', 'findings.extend(lin_reserve_findings(network, sizing_policy, schedule))')
source = source.replace('            if network["target_status"] == "EXCEEDED":', '            findings.extend(lin_budget_findings(network))\n            if network["target_status"] == "EXCEEDED":',1)
write(path,source)
apply('preserved-assessment-finding-order')
