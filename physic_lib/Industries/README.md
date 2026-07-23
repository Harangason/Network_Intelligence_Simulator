# Industries

Industry-specific project profiles live here.

## Core Rule

The simulator is industry neutral. Automotive is only a test and reference
profile for the function, not the architectural center of the project.

New domains must map their own concepts into the simulator's neutral model:

- `participant`
- `node`
- `service`
- `signal`
- `hardware`
- `bus`
- `port`
- `route`
- `channel`
- `interface`

If a project from another discipline cannot be represented cleanly through the
existing paths, add a dedicated domain path instead of forcing it into
Automotive terminology.

## Automotive

`Automotive/project_profiles.db` contains the restbus project profiles used by `nemotron.py`, for example:

- `adas`
- `powertrain`
- `body`

The database is created and seeded automatically from the built-in fallback profiles on first start. After that, `nemotron.py` loads project profiles from this library before building CLI choices or generating requests.

`Automotive/maneuver_profiles.db` contains typical maneuvers and Physical-AI workflow routing metadata that used to be represented by large in-code lists.

## Future Industries

Additional domains can follow the same pattern:

- `Generic/`
- `Aerospace/project_profiles.db`
- `RoboticsROS/project_profiles.db`
- `Rail/project_profiles.db`
- `Manufacturing/project_profiles.db`
- `IndustrialAutomation/project_profiles.db`

The expected table is `project_profiles` with topology metadata and `participants_json`.

## Current Domain Skeletons

- `Generic/`
- `Automotive/`
- `RoboticsROS/`
- `Aerospace/`
- `IndustrialAutomation/`
