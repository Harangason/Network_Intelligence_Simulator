"""REST-Schnittstellen für das kanonische Engineering-Modell.

Dieses Blueprint stellt ausschließlich CRUD- und Versionierungs-Endpunkte für
Engineering-Objekte (HardwareNode, Function, Interface, Message, Signal) und
deren Relations bereit. Es ist bewusst unabhängig von der aktiven Simulation
(``backend/app`` bzw. ``backend/simulator``) - es findet hier keine
Simulation, kein RAG und kein Agent statt, nur Persistenz und Governance.
"""

from __future__ import annotations

import psycopg
from flask import Blueprint, jsonify, request

from .models import DEVICE_TYPES, EngineeringValidationError, INTERFACE_TYPES, MESSAGE_DIRECTIONS
from .relations import create_relation, delete_relation, get_relation, list_relations
from .repository import (
    ENTITY_SPECS,
    NotFoundError,
    create_object,
    delete_object,
    get_object,
    list_objects,
    list_versions,
    update_object,
)

engineering_api = Blueprint("engineering_api", __name__)

# URL-Segment (Plural, kebab-case) -> kanonischer Objekttyp
RESOURCES: dict[str, str] = {
    "hardware-nodes": "HardwareNode",
    "functions": "Function",
    "interfaces": "Interface",
    "messages": "Message",
    "signals": "Signal",
}

FILTERABLE_QUERY_PARAMS = (
    "domain",
    "lifecycle_state",
    "review_state",
    "approval_state",
    "hardware_node_id",
    "interface_id",
    "message_id",
    "device_type",
    "interface_type",
)


def _resource_object_type(resource: str) -> str:
    object_type = RESOURCES.get(resource)
    if object_type is None:
        raise EngineeringValidationError(f"Unbekannte Ressource: {resource!r}")
    return object_type


def _pagination_args() -> tuple[int, int]:
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 500)
        offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        raise EngineeringValidationError("'limit' und 'offset' müssen ganze Zahlen sein.")
    return limit, offset


@engineering_api.errorhandler(EngineeringValidationError)
def _handle_validation_error(error: EngineeringValidationError):
    return jsonify({"error": str(error)}), 400


@engineering_api.errorhandler(NotFoundError)
def _handle_not_found(error: NotFoundError):
    return jsonify({"error": str(error)}), 404


@engineering_api.errorhandler(psycopg.errors.CheckViolation)
@engineering_api.errorhandler(psycopg.errors.ForeignKeyViolation)
@engineering_api.errorhandler(psycopg.errors.NotNullViolation)
def _handle_constraint_violation(error: psycopg.Error):
    return jsonify({"error": "Datenbank-Constraint verletzt.", "detail": str(error).strip()}), 400


@engineering_api.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "engineering-model"})


@engineering_api.route("/schema", methods=["GET"])
def schema():
    """Metadaten für Frontend-Formulare: Vokabulare und Ressourcen-Layout."""
    return jsonify(
        {
            "resources": list(RESOURCES.keys()),
            "device_types": list(DEVICE_TYPES),
            "interface_types": list(INTERFACE_TYPES),
            "message_directions": list(MESSAGE_DIRECTIONS),
        }
    )


@engineering_api.route("/<resource>", methods=["GET"])
def list_resource(resource: str):
    object_type = _resource_object_type(resource)
    limit, offset = _pagination_args()
    filters = {key: request.args.get(key) for key in FILTERABLE_QUERY_PARAMS if request.args.get(key)}
    items = list_objects(object_type, filters=filters, limit=limit, offset=offset)
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/<resource>", methods=["POST"])
def create_resource(resource: str):
    object_type = _resource_object_type(resource)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    item = create_object(object_type, payload)
    return jsonify(item), 201


@engineering_api.route("/<resource>/<object_id>", methods=["GET"])
def get_resource(resource: str, object_id: str):
    object_type = _resource_object_type(resource)
    return jsonify(get_object(object_type, object_id))


@engineering_api.route("/<resource>/<object_id>", methods=["PATCH"])
def update_resource(resource: str, object_id: str):
    object_type = _resource_object_type(resource)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    item = update_object(object_type, object_id, payload)
    return jsonify(item)


@engineering_api.route("/<resource>/<object_id>", methods=["DELETE"])
def delete_resource(resource: str, object_id: str):
    object_type = _resource_object_type(resource)
    delete_object(object_type, object_id)
    return "", 204


@engineering_api.route("/<resource>/<object_id>/versions", methods=["GET"])
def resource_versions(resource: str, object_id: str):
    object_type = _resource_object_type(resource)
    return jsonify({"items": list_versions(object_type, object_id)})


# ---------------------------------------------------------------------------
# Relations (Kanten des zukünftigen Knowledge Graphs)
# ---------------------------------------------------------------------------


@engineering_api.route("/relations", methods=["GET"])
def list_relations_route():
    limit, offset = _pagination_args()
    items = list_relations(
        object_type=request.args.get("object_type"),
        object_id=request.args.get("object_id"),
        relation_type=request.args.get("relation_type"),
        limit=limit,
        offset=offset,
    )
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/relations", methods=["POST"])
def create_relation_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    item = create_relation(payload)
    return jsonify(item), 201


@engineering_api.route("/relations/<relation_id>", methods=["GET"])
def get_relation_route(relation_id: str):
    return jsonify(get_relation(relation_id))


@engineering_api.route("/relations/<relation_id>", methods=["DELETE"])
def delete_relation_route(relation_id: str):
    delete_relation(relation_id)
    return "", 204


# Sicherstellen, dass alle registrierten Ressourcen tatsächlich Specs haben
# (fällt zur Importzeit auf, falls ein neuer Eintrag in RESOURCES vergessen
# wurde, in ENTITY_SPECS nachzuziehen).
assert set(RESOURCES.values()) <= set(ENTITY_SPECS), "RESOURCES referenziert unbekannten Objekttyp"
