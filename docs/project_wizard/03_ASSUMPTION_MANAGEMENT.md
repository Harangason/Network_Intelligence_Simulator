# Assumption Management

Status: IMPLEMENTED

Verifikationsstand:
- Engine erzeugt explizite Annahmen mit `proposed_value`, `confidence`, `requires_confirmation`, `status`.
- Offene Annahmen werden in `open_decisions` überführt.
- Standardfälle wie `required_coverage`, `camera_operating_frame`, `frame_rate` sind enthalten.

Offene Restpunkte:
- Kritische vs. nicht-kritische Trennung kann noch präziser nach Kritikalität skaliert werden.

