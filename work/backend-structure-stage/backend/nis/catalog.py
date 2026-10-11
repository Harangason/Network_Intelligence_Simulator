"""One discoverable source map for the complete NIS backend."""

from backend.nis.specializations.catalog import source_catalog
from backend.nis.workflow.definition import WORKFLOW_STAGES

from backend.nis.automation import CAPABILITY as AUTOMATION
from backend.nis.domain import CAPABILITY as DOMAIN
from backend.nis.infrastructure import CAPABILITY as INFRASTRUCTURE
from backend.nis.intelligence import CAPABILITY as INTELLIGENCE
from backend.nis.interfaces import CAPABILITY as INTERFACES
from backend.nis.simulation import CAPABILITY as SIMULATION

CAPABILITIES = (DOMAIN, AUTOMATION, SIMULATION, INTELLIGENCE, INTERFACES, INFRASTRUCTURE)


def architecture_catalog() -> dict[str, object]:
    """Return workflow, specialization and platform provenance."""

    specializations = source_catalog()
    return {
        "workflow": [
            {
                "id": stage.id,
                "position": stage.position,
                "label": stage.label,
                "route": stage.route,
                "backend_sources": list(stage.backend_sources),
                "frontend_feature": stage.frontend_feature,
                "consumes": list(stage.consumes),
                "produces": list(stage.produces),
            }
            for stage in WORKFLOW_STAGES
        ],
        "industries": specializations["industries"],
        "technologies": specializations["technologies"],
        "capabilities": [
            {
                "id": item.id,
                "label": item.label,
                "source_modules": list(item.source_modules),
                "responsibility": item.responsibility,
            }
            for item in CAPABILITIES
        ],
    }


__all__ = ["CAPABILITIES", "architecture_catalog"]
