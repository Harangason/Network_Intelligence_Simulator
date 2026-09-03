"""Kanonisches Engineering-Modell (Phase 1).

Stellt Persistenz, Versionierung und REST-Schnittstellen für die
Engineering-Objekte HardwareNode, Function, Interface, Message und Signal
sowie deren Relations bereit - ohne aktive Simulation, RAG oder Agenten.
"""

__all__ = ["engineering_api"]


def __getattr__(name: str):
    if name == "engineering_api":
        from .api import engineering_api

        return engineering_api
    raise AttributeError(name)
