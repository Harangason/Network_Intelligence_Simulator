"""Aerospace and avionics transport ownership."""

from ...core import TechnologySpecialization

MANIFEST = TechnologySpecialization("aerospace", (
    "arinc429", "afdx", "arinc825", "can_aerospace", "mil_std_1553", "spacewire", "tte",
), ("backend.communication.technologies.catalog", "backend.communication.technologies.core"))
__all__ = ["MANIFEST"]
