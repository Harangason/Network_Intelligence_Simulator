"""Aerospace and avionics transport ownership."""

from backend.nis.specializations.core import TechnologySpecialization

MANIFEST = TechnologySpecialization("aerospace", (
    "arinc429", "afdx", "arinc825", "can_aerospace", "mil_std_1553", "spacewire", "tte",
), ("backend.nis.communication.catalog", "backend.nis.communication.core"))
__all__ = ["MANIFEST"]
