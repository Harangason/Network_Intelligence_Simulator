# Domain function coverage — 2026-09-14

- HMI candidates now include controllers from all clusters. Source/target pairs and signals are deduplicated; physical sensors and actuators are not broadcast as HMI sources.
- Per-signal/per-display switches remain disabled by default and preserve explicit exclusions.
- Automotive examples add 20 scalar outputs to existing hosts: BodyControl (interior occupancy and intrusion monitoring), Klimatisierung (temperature, air quality, humidity, airflow), Infotainment (FM/DAB, media, controls, navigation), Telematik (GNSS/GPS positioning), Konnektivitaet (Internet, WLAN, Bluetooth), Soundsystem (audio output).
- These are editable model examples, not real radio/network services or validated control algorithms. Their physical input allocation and functional acceptance remain project decisions. No additional hardware or installation positions are inferred.
- Hardware extraction and confirmed hardware counts retain distinct device identities. Additional functions are expanded for cluster review and the executable wizard adapter, after ordinary payload packing. Each additional output has a separate message and explicit scalar encoding; existing signals are preserved.
- The controller review shows its hosted functions. Canonical controller identity determines the cluster; output names cannot move its hardware into a different domain.

Verification: 60 specification/cluster tests passed; production build and browser checks passed. Browser checks cover HMI choices in chassis/body/infotainment, default-off, target isolation, navigation persistence, and 390-pixel layout. No live project generation was submitted by the browser test.

Backend verification: 15 generator tests passed in the grouped run. The combined model/simulation test intermittently reported simulation WARNING instead of COMPLETE (also observed before this change); the diagnostic rerun passed in 63 seconds. The assertion now includes the workflow state on failure. This remains a test-stability limitation.
