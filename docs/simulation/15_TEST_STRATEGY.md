# Test Strategy

Aktive Tests decken ab:

- alle Behavior-Modelle deterministisch und bounded
- physikalische Temperatur mit Rate-Limit
- Counter-Wrap mit Modulus
- Preflight fuer ungueltige Formeln
- Preflight fuer Dependency-Zyklen
- Preflight fuer Encoding ausserhalb der Payload
- Fault Injection auf Golden Behavior
- Encoding/Decoding
- Trace-Metadaten fuer Semantic Type und Quality
- Golden/Actual-Werte je Signalpunkt
- Dependency-Reihenfolge vor Formula-Sampling
- Model-Trace-Decimation ueber die komplette Dauer
- Universal Trace bis zur konfigurierten Dauer, wenn das Event-Budget reicht
- separate Engine-Service-Contracts fuer Derived, State und Quality
- Golden/Fault-Artefakte
- vollstaendiger Motor-End-to-End-Fall mit Command, State, RPM, Torque, Current und Temperature
