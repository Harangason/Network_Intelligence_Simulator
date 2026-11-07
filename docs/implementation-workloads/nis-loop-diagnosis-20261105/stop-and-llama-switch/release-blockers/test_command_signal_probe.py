import json
from pathlib import Path
from backend.tests.test_wizard_large_routing import test_full_captured_model_and_all_routing_validate_without_rewriting_inputs as full_case
from backend.nis.agent.tools import proposal_service

def test_missing_command_source(monkeypatch,tmp_path):
    original=proposal_service.validate
    def inspect(proposal_id):
        result=original(proposal_id)
        changes=result.get("changes",[])
        errors=[f for f in result["validation_result"].get("findings",[]) if f.get("severity")=="ERROR"]
        if errors:
            details=[]
            for finding in errors:
                i=finding.get("index")
                if isinstance(i,int) and i<len(changes):
                    bad=changes[i]; ref="$"+bad["local_ref"]
                    related=[c for c in changes if ref in json.dumps(c.get("data",{}))]
                    details.append({"finding":finding,"change":bad,"related":related[:12]})
            Path("docs/implementation-workloads/nis-loop-diagnosis-20261105/stop-and-llama-switch/release-blockers/command-signal-red.json").write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding="utf-8")
        return result
    monkeypatch.setattr(proposal_service,"validate",inspect)
    full_case(tmp_path)
