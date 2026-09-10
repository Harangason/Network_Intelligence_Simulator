# Communication design and assessment

Applies to generation, AI proposals, sizing, simulation, analysis and later exports.
User basis: LIN reference/brake audit of 2026-09-10 and its implementation approval.

1. A measurement, a commanded value, execution feedback and device health are different meanings. A name containing `Status` does not override a physical unit, range or scaling. Companion signals get their own domains and encodings.
2. Explicit raw codes determine required width. Do not renumber sparse codes, invent an error code from maximum + resolution, or expand state tables while displaying them. Valid, reserved and invalid raw codes must be disjoint. A negative physical range can use unsigned raw values and an offset.
3. A physical frame has one publisher. Only compatible signals from that publisher may be packed together. Multicast observations do not cause multiple physical transmissions. Physical technology comes from canonical ports/network data, not a historical identifier suffix.
4. Transmission mode is explicit: CYCLIC, EVENT, ON_REQUEST or MIXED. Noncyclic traffic needs a minimum interval and a trigger/request source. Missing rates or triggers remain open; do not silently simulate periodic responses. Event demand bounds are not observed average rates. Existing periodic communication is not automatically changed because its signal is named Status.
5. ON_REQUEST with `request_source: external_application` describes an explicit scenario input outside the modeled transport. Bus requests require their own modeled request/response traffic; this external-input option does not prove that traffic or its capacity. No request timestamps means no responses.
6. LIN reserves serial master poll slots, including checksum and timing margin. Events may miss a poll slot. CAN needs arbitration/interference analysis. A slot or frame response bound is not an arbitrary event-to-actuation bound.
7. Keep payload validity, nominal/bounded capacity demand, schedule feasibility, stress target and functional timing acceptance separate. Functional acceptance requires a confirmed function requirement and sampling/actuation delays. A periodic 20 or 50 ms design value is not a universal brake-function approval. Do not relax a confirmed deadline to make a bus fit.
8. Spatial grouping follows SPATIAL_ARCHITECTURE_CONTRACT.md. Split local links by physical zone; preserve unknown positions explicitly. An electrically valid bus does not establish functional or spatial suitability.
9. Reference traces retain file identity/hash, channel, diagnostic/operational context and observation duration. Measured history suggests candidates, never silently supplies safety requirements. The supplied Audi OBD CAN traces contain no LIN evidence.
10. DBC/ARXML/LDF outputs must use the validated canonical encoding. LIN scalar export needs unsigned raw encoding or an explicit, checked adaptation. LDF also needs the master schedule. A generated file or independent decoder roundtrip proves syntax/encoding, not functional suitability.

## Executable transmission contract

Stored at Message.configuration.communication_contract.transmission.

```json
{
  "mode": "EVENT",
  "trigger": "on_change",
  "minimum_interval_ms": 20,
  "send_initial": true
}
```

EVENT can instead use `trigger: explicit` and `release_times_ms` for a scenario.
MIXED additionally has `period_ms` for a heartbeat. ON_REQUEST uses explicit
`request_times_ms` and `request_source: external_application`. Scenario timestamps
are relative milliseconds and must respect the minimum interval. Empty event or
request lists produce no application transmissions. Physical serialization and
LIN polling still apply. On-change decisions compare encoded signal payloads;
they require modeled signals.

Optional `functional_requirements` contains `confirmed`,
`maximum_event_to_response_ms`, `sampling_delay_ms`, and `actuation_delay_ms`.
The current separated functional evaluator conservatively includes one release
interval; multiple-bus functional proofs remain UNVERIFIED. It does not issue a
safety certification.
