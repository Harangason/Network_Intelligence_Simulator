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
11. Reconnecting a physical route preserves functional communication, publishers, recipients, messages, signals and explicit timing/encodings. The repair agent starts on user action and previews the previous and proposed physical paths, including every affected current route. It offers **adopt the new routing** and, where the audited history supports it, **restore the previous routing**. Opening the agent never applies a strategy. The user's explicit choice updates physical/message bindings and the routing table atomically. A previous System/gateway connection moved inside a cluster or a different spatial/system scope requires a concrete explanation of that change. Missing paths stay unresolved; an ordinary ECU is not an implicit gateway. Apply against the current project revision, validate the result and invalidate prior routing release and downstream assessments. Never invent recipients or renumber explicit frame IDs to make a repair pass.
12. A proposed Ethernet forwarding task on an ECU must identify and explicitly confirm the exact directed pair of canonical ports and networks. It does not reclassify the whole device as a gateway or permit unrelated channels. Revoking the confirmation, moving a port to another network or removing a saved wire invalidates the affected signal paths. Restoring a previous System connection may require a new gateway channel when its original channel no longer exists; disclose and persist that additional hardware planning requirement. The choice confirms the intended communication design, not hardware implementation, capacity or functional timing acceptance.
13. Communication between supervising functions carries the explicitly needed function outputs, such as operating state or error information. Local measurements, actuator commands and feedback remain within their declared recipient boundary; physical reachability, a matching sender or a similar name never authorize forwarding them to another function. Direct use of a device without a supervising function remains possible through an explicit device-data contract. Store exceptions and function outputs in `Message.configuration.communication_contract.scope` (`LOCAL_IO`, `DEVICE_IO`, `FUNCTION_OUTPUT`) with canonical `consumer_refs`; do not guess scope from bus technology or display names. Existing wizard roles `MEASUREMENT`, `FEEDBACK`, `COMMAND` represent reviewed local ownership, including the local actuator-command generator. Preserve these boundaries during repair, proposals, routing, simulation and sizing. Reject unintended forwarding with a visible error and exclude that invalid transmission from calculated bus demand. Valid local I/O still loads its actual local bus. Selecting fewer signals from an existing frame does not shrink its DLC: a smaller function output requires its own explicit, validated message encoding and transmission contract. Never invent On/Off/Error raw values to satisfy a route.

## Executable transmission contract

Architecture repair additionally follows the user's clarification of 11.09.2026:
use the **current hardware architecture** to implement the **established communication
between functions**. Preserve function and logical interface identities independently
of ports, wires and buses. Resolve partners through their current canonical
function-to-hardware assignments; a forwarding ECU is not a replacement consumer.
Capture established partners before network-editor changes. Moving one function must
not move unrelated messages sharing its former channel. Basic sensor/actuator I/O
without a separate Function object remains explicit device I/O. Missing or ambiguous
function assignments and co-located functions requiring local transport remain open
design items. Restore old hardware paths only through the distinct restoration choice.

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
