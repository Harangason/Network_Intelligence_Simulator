# API Projections

List endpoints should return projections:

- Identifiers
- Status
- Counts
- Timestamps
- Small overview values

They should not return full simulation results, full calculated metrics,
complete trace payloads or every nested project object. Detail endpoints may
return a complete object for an explicit id.

