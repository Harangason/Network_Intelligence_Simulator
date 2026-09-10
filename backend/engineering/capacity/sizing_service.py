"""Version-checked, atomic adoption of communication sizing into the model."""
from copy import deepcopy
from hashlib import sha256
import json
from datetime import datetime, timezone

from .. import db
from ..models import EngineeringValidationError
from ..pagination import all_pages
from ..repository import list_objects, update_object
from ..routing.repository import list_routes, update_route, save_validation, approve_routes
from ..routing.validation import RoutingValidator
from ..workflow.service import WorkflowStatusService
from .service import CapacityTimingService
from .dimensioning import VERSION, dimension_communications, policy_for


class CommunicationSizingService:
    def __init__(self, project_id):
        self.project_id = project_id
        self.workflow = WorkflowStatusService(project_id)

    def preview(self, policy=None):
        state = self.workflow.get()
        parameters = dict(state.get("parameters") or {})
        if policy is not None:
            parameters["communication_sizing"] = policy
        resolved_policy = policy_for(parameters)
        capacity = CapacityTimingService(self.project_id).calculate(overrides=parameters, persist=False, include_drafts=True)
        history = (state.get("context") or {}).get("communication_sizing_history") or []
        plan = dimension_communications(capacity["results"].get("transmissions", []), parameters, history)
        inputs = {"versions": state["versions"], "policy": resolved_policy,
                  "transmissions": capacity["results"].get("transmissions", [])}
        plan["source_token"] = sha256(json.dumps(inputs, sort_keys=True, default=str).encode()).hexdigest()
        plan["source_versions"] = state["versions"]
        plan["project_id"] = self.project_id
        return plan

    def apply(self, expected_token, policy=None, *, actor="communication-sizing", approve_valid=False):
        # API calls already have a RequestUnit; wizard continuations use the same
        # transaction discipline, including rollback of every dependent write.
        existing = db._request_unit.get()
        own = db.RequestUnit(self.project_id) if existing is None else None
        unit = own or existing
        try:
            unit.acquire()
            plan = self.preview(policy)
            if not expected_token or plan["source_token"] != expected_token:
                raise db.ConcurrentUpdateError("Die Grundlage des Dimensionierungsplans wurde geändert. Bitte neu berechnen.")
            state = self.workflow.get()
            changes = {item["message_id"]: item for item in plan["changes"]}
            messages = all_pages(list_objects, "Message")
            signals = all_pages(list_objects, "Signal")
            routes = all_pages(list_routes)
            now = datetime.now(timezone.utc).isoformat()
            for message in messages:
                change = changes.get(str(message["id"]))
                if not change:
                    continue
                configuration = deepcopy(message.get("configuration") or {})
                contract = configuration.setdefault("communication_contract", {})
                previous = contract.get("transmission") or {}
                contract["transmission"] = {**previous, "version": 1, "mode": previous.get("mode", "CYCLIC"),
                    "period_ms": change["after_ms"], "minimum_interval_ms": plan["policy"]["minimum_interval_ms"],
                    "source": "automatic_dimensioning", "calculation_version": VERSION,
                    "source_token": plan["source_token"], "requires_functional_review": True}
                contract["transmission"]["timing_evaluation"] = change.get("evaluation", "FEASIBLE_UNDER_ASSUMPTIONS")
                # Keep existing explicit deadlines; only synchronize period copies.
                for key in ("cycle_time", "cycle_time_ms"):
                    if key in configuration:
                        configuration[key] = change["after_ms"]
                transport = configuration.get("transport_unit")
                if isinstance(transport, dict):
                    transport.setdefault("timing", {})["cycle_ms"] = change["after_ms"]
                update_object("Message", str(message["id"]), {"configuration": configuration, "cycle_ms": change["after_ms"],
                    "expected_version": message["version"], "actor": actor})
            for signal in signals:
                change = changes.get(str(signal.get("message_id")))
                if not change:
                    continue
                communication = deepcopy(signal.get("communication") or {})
                communication["cycle_time_ms"] = change["after_ms"]
                if "cycle_time" in communication:
                    communication["cycle_time"] = change["after_ms"]
                communication["timing_source"] = "canonical_message_transmission"
                update_object("Signal", str(signal["id"]), {"communication": communication,
                    "expected_version": signal["version"], "actor": actor})
            changed_routes = []
            for route in routes:
                if route.get("status") in {"REJECTED", "SUPERSEDED", "DEPRECATED", "OUTDATED"}:
                    continue
                payload = route.get("payload") or {}
                ids = set(map(str, payload.get("message_ids") or [])) | {str(payload.get("message_id") or "")}
                selected = [change for key, change in changes.items() if key in ids]
                if not selected:
                    continue
                timing = deepcopy(route.get("timing") or {})
                timing["message_periods_ms"] = {key: changes[key]["after_ms"] for key in ids if key in changes}
                timing["cycle_time_ms"] = min(timing["message_periods_ms"].values())
                if "cycle_time" in timing:
                    timing["cycle_time"] = timing["cycle_time_ms"]
                timing.setdefault("provenance", {})["cycle_time_ms"] = {"source": "communication-sizing", "version": VERSION}
                updated = update_route(str(route["id"]), {"timing": timing, "expected_revision": route["revision"], "actor": actor})
                changed_routes.append(updated)
            parameters = {**(state.get("parameters") or {}), "communication_sizing": plan["policy"]}
            parameters["communication_schedule"] = {"version": VERSION, "source_token": plan["source_token"],
                "networks": [{"network_id": item["network_id"], **item["schedule"]} for item in plan["networks"]
                             if item["status"] == "FEASIBLE_UNDER_ASSUMPTIONS"]}
            self.workflow.save_parameters(parameters, actor=actor)
            if changes:
                db.flush_model_changes(actor=actor, reason="Nachrichten, Signale und Routen gemeinsam dimensioniert.")
                self.workflow.mark_changed("routing", "Dimensionierte Zyklen müssen auf dem aktuellen Modell geprüft werden.", actor=actor)
            valid, invalid = [], []
            validator = RoutingValidator()
            for route in changed_routes:
                validation = validator.validate(route, exclude_route_id=str(route["id"]))
                save_validation(str(route["id"]), validation, actor=actor)
                (valid if validation.get("valid") else invalid).append(str(route["id"]))
            if approve_valid and valid:
                approve_routes(valid, actor=actor)
            # A period edit invalidates downstream stages. Recheck the unchanged
            # physical topology before confirming its current model reference.
            if changes and not invalid:
                self.workflow.save_topology(self.workflow.get()["topology"], actor=actor)
                self.workflow.save_parameters(parameters, actor=actor)
            receipt_id = sha256((plan["source_token"] + now).encode()).hexdigest()[:20]
            history = list((state.get("context") or {}).get("communication_sizing_history") or [])
            for network in plan["networks"]:
                if network["status"] == "FEASIBLE_UNDER_ASSUMPTIONS":
                    history.append({key: network[key] for key in ("fingerprint", "status", "selected_floor_ms", "network_name")}
                                   | {"snapshot_id": receipt_id, "created_at": now})
            self.workflow.set_context({"communication_sizing_history": history[-500:],
                "communication_sizing_receipt": {"id": receipt_id, "source_versions": plan["source_versions"],
                    "changes": plan["changes"], "status": plan["status"], "created_at": now,
                    "valid_route_ids": valid, "invalid_route_ids": invalid, "approved": bool(approve_valid)}})
            result = {"applied": True, "plan": plan, "receipt_id": receipt_id, "changed_messages": len(changes),
                      "changed_routes": len(changed_routes), "valid_routes": len(valid), "invalid_routes": invalid,
                      "approved": bool(approve_valid)}
            if own:
                own.finish(True)
            return result
        finally:
            if own:
                own.close()
