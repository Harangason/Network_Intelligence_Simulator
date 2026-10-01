"""Atomic correction of known generated domains, with provenance and revalidation."""
from hashlib import sha256
import json

from . import db
from .pagination import all_pages
from .repository import list_objects, update_object
from .routing.repository import list_routes, save_validation, approve_routes
from .routing.validation import RoutingValidator
from .signal_integrity import VERSION, integrity_checks, legacy_numeric_repair
from .workflow.service import WorkflowStatusService


class SignalIntegrityService:
    def __init__(self, project_id):
        self.workflow = WorkflowStatusService(project_id)
        self.project_id = project_id

    def preview(self):
        state = self.workflow.get()
        signals = all_pages(list_objects, "Signal")
        changes = [{"id": str(s["id"]), "name": s["name"], "version": s["version"], "patch": patch}
                   for s in signals if (patch := legacy_numeric_repair(s)) is not None]
        token = sha256(json.dumps({"project": self.project_id, "versions": state["versions"], "changes": changes},
                                 sort_keys=True, default=str).encode()).hexdigest()
        remaining = [{"id": str(s["id"]), "checks": checks} for s in signals
                     if (checks := integrity_checks({**s, **(legacy_numeric_repair(s) or {})}))]
        return {"version": VERSION, "token": token, "changes": changes, "remaining": remaining}

    def apply(self, expected_token, *, approve_valid=False, actor="signal-integrity-audit"):
        own = db.RequestUnit(self.project_id) if db._request_unit.get() is None else None
        unit = own or db._request_unit.get()
        try:
            unit.acquire()
            plan = self.preview()
            if expected_token != plan["token"]:
                raise db.ConcurrentUpdateError("Signalmodell wurde geändert; Korrekturplan neu prüfen.")
            if not plan["changes"]:
                if own:
                    own.finish(True)
                return {"changed_signals": 0, "remaining": plan["remaining"], "version": VERSION}
            state = self.workflow.get()
            for change in plan["changes"]:
                update_object("Signal", change["id"], {**change["patch"], "expected_version": change["version"], "actor": actor})
            db.flush_model_changes(actor=actor, reason="Belegte Generatorfehler in Signaldomänen korrigiert; physische Kodierung erhalten.")
            validator = RoutingValidator()
            valid, invalid = [], []
            for route in all_pages(list_routes):
                if route.get("status") in {"REJECTED", "SUPERSEDED", "DEPRECATED", "OUTDATED"}:
                    continue
                validation = validator.validate(route, exclude_route_id=str(route["id"]))
                save_validation(str(route["id"]), validation, actor=actor)
                (valid if validation["valid"] else invalid).append(str(route["id"]))
            if approve_valid and valid:
                approve_routes(valid, actor=actor)
            if not invalid:
                self.workflow.mark_changed("routing", "Signaldomänen korrigiert und alle aktuellen Routen erneut geprüft.", actor=actor)
                self.workflow.save_topology(self.workflow.get()["topology"], actor=actor)
                self.workflow.mark_changed("network_editor", "Physische Verbindungen nach reiner Signaldomänen-Korrektur geprüft und bestätigt.", actor=actor)
                self.workflow.save_parameters(state["parameters"], actor=actor)
            receipt = {"version": VERSION, "source_token": expected_token,
                "changed_signals": len(plan["changes"]), "signal_ids": [c["id"] for c in plan["changes"]],
                "remaining": plan["remaining"], "valid_routes": len(valid), "invalid_routes": invalid}
            self.workflow.set_context({"signal_integrity_receipt": receipt})
            if own:
                own.finish(True)
            return receipt
        finally:
            if own:
                own.close()
