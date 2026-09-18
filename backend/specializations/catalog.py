"""Combined, navigable source catalog for industries and technologies."""

from .industries import ALL as INDUSTRY_SPECIALIZATIONS
from .technologies import ALL as TECHNOLOGY_SPECIALIZATIONS


def source_catalog() -> dict[str, list[dict[str, object]]]:
    """Return JSON-compatible specialization provenance."""

    return {
        "industries": [
            {"id": item.id, "label": item.label, "source_modules": list(item.source_modules)}
            for item in INDUSTRY_SPECIALIZATIONS
        ],
        "technologies": [
            {
                "id": item.id,
                "technology_ids": list(item.technology_ids),
                "source_modules": list(item.source_modules),
            }
            for item in TECHNOLOGY_SPECIALIZATIONS
        ],
    }


__all__ = ["INDUSTRY_SPECIALIZATIONS", "TECHNOLOGY_SPECIALIZATIONS", "source_catalog"]
