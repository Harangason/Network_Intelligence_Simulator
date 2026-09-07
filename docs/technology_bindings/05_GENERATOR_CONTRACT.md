# Generator contract

Generators receive an approved `TechnologyBinding` and typed payload elements. They produce a technology-labelled `TransportUnit` with identifier, timing, QoS, status, and provenance.

The Wizard resolves generators through the registry. It contains no protocol `if/elif` generator switch.
