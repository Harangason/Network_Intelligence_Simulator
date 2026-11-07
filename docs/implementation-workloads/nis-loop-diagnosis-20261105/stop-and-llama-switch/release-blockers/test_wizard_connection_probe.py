import json
from backend.tests.test_wizard_actual_audit import test_actual_wizard_model_is_valid as captured_original
from backend.nis.agent.tools import wizard_generation

def test_captured_connection_identity(monkeypatch):
    original=wizard_generation._topology_bus
    def inspect(value):
        try:return original(value)
        except ValueError as error:
            print(json.dumps({"actual_unresolved_connection":value,"error":str(error)},ensure_ascii=True),flush=True)
            raise
    monkeypatch.setattr(wizard_generation,"_topology_bus",inspect)
    captured_original()
