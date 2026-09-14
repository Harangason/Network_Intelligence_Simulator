# Gateway paths and functional payload scope

User examples: Heckklappe → System → Fahrerassistenz and Klimatisierung → System → Fahrerassistenz, project `20260910042736034-d11591d0`.

The routing wizard and manual route editor now show the planned communication path before endpoint selection. Every leg shows current shared canonical buses. Physical gateway ports provide this evidence even if the gateway has no logical message interface on that channel. The preview describes the saved/planned gateway sequence; full route validation still checks forwarding permissions and transport compatibility.

Interface search combines name, technology and readable bus names. Space-separated terms, optionally joined with “und”, narrow results. Interfaces on the adjacent path node's bus rank ahead of protocol similarity. Search preserves the current selection. Changing the sender behind a gateway preserves the receive protocol. Recommendations and endpoint-port selection use the same adjacent-bus evidence; ambiguous physical channels remain explicit choices.

`routing/payload_scope.py` supplies the same recipient policy to the scoped message catalog, proposals, route validation, capacity calculation and executable configuration generation. It includes signal-only payloads by resolving their parent messages. In the example, “Klimatisierung LIN IO Befehl” has the canonical local actuator-command contract and two actuator recipients. It remains selectable for those actors, while ADAS receives the selected function output. Imported/direct device data and explicit function outputs remain possible. Missing required output messages must be designed in Engineering; the feature does not manufacture status encodings or infer supervision from a device name.

Forbidden local forwarding yields `LOCAL_IO_RECIPIENT_MISMATCH`. Capacity excludes that invalid transmission and reports an error rather than presenting it as valid system traffic. Local routes retain their bus demand. Capacity continues to serialize whole selected messages; signal checkboxes do not reduce the physical frame size.

## Verification

- TypeScript `tsc --noEmit`: passed.
- Frontend routing search, binding and communication regressions: 17 passed, including a gateway with physical ports but no logical interface, final-leg Ethernet ranking over local CAN, ambiguous channels, and local/direct payload scope.
- Separate database backend run: 93 passed, 2 failed. All seven new payload-scope tests passed, including actual validator, capacity and simulation-export integration.
- The two failures are pre-existing transport tests: transmission-latency equality (`6.458333` versus `3.333333…`) and configured nonzero jitter. An isolated repeat using the exact pre-change `config_builder.py` and capacity service sources reproduces both failures; evidence is in `backend/runtime/routing-scope-baseline.log`. No live project database is used for these tests.
- Chrome verification: passed with no page errors, including desktop and 800-pixel window. Script: `frontend/scripts/verify-routing-functional-scope.mjs`. Checks both example payload scopes, gateway path position, live physical-bus search, stable selection/protocol, an 800-pixel viewport and unchanged canonical routes/topology. Final browser result is recorded in `backend/runtime/routing-functional-scope-browser.json`.

The existing project routes are not automatically rewritten or approved by opening the wizard. The user reviews and saves the intended endpoint and payload changes. Ordinary ECUs do not acquire gateway permissions from a shared-bus preview.
