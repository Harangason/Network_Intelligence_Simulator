# Requirement Intent Extraction

Status: IMPLEMENTED

Verifikationsstand:
- Erkennung von Domain-/Intent-Hinweisen in `_choose_domain` (Automotive, Industrial, Generic, Rail, Aerospace, Robotics, Energy).
- Keyword-Muster in `backend/engineering/workloads/models.py` erkennt Anforderungsanfragen (`anforderung`, `anfrage`, `benötige`, `bedarf`).
- Engine legt `interpretation` und `resolved_domain` in `provenance` ab.

Offene Restpunkte:
- Nutzung von Ontologie / Knowledge Graph / Alias-Datenbank noch nicht integriert.

