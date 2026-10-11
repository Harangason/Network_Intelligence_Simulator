from __future__ import annotations

from .state_machine import StateMachineEngine, StateMachineProfile, StateTransition, profile_from_states


OPERATING_STATES = ("OFF", "INIT", "READY", "STARTING", "RUNNING", "STOPPING", "STANDBY", "LIMITED")
OPERATING_CODES = {state: index for index, state in enumerate(OPERATING_STATES)}


def motor_profile() -> StateMachineProfile:
    return StateMachineProfile(
        name="motor_operating",
        initial_state="OFF",
        allowed_states=OPERATING_STATES,
        allowed_transitions={
            "OFF": ("INIT",),
            "INIT": ("READY",),
            "READY": ("STARTING", "STANDBY"),
            "STARTING": ("RUNNING",),
            "RUNNING": ("STOPPING", "LIMITED"),
            "LIMITED": ("RUNNING", "STOPPING"),
            "STOPPING": ("READY",),
            "STANDBY": ("READY",),
        },
        timeline=(
            StateTransition("OFF", "INIT", 0.5),
            StateTransition("INIT", "READY", 1.5),
            StateTransition("READY", "STARTING", 3.0),
            StateTransition("STARTING", "RUNNING", 5.0),
            StateTransition("RUNNING", "STOPPING", 55.0),
            StateTransition("STOPPING", "READY", 58.0),
        ),
        fault_transitions={"SAFE_STATE": "STOPPING", "EMERGENCY_STOP": "STOPPING"},
    )


def gateway_profile() -> StateMachineProfile:
    states = ("OFF", "INIT", "CONFIGURING", "READY", "ACTIVE", "STANDBY", "SHUTTING_DOWN")
    return StateMachineProfile(
        name="gateway_operating",
        initial_state="OFF",
        allowed_states=states,
        allowed_transitions={
            "OFF": ("INIT",),
            "INIT": ("CONFIGURING",),
            "CONFIGURING": ("READY",),
            "READY": ("ACTIVE", "STANDBY"),
            "ACTIVE": ("STANDBY", "SHUTTING_DOWN"),
            "STANDBY": ("READY", "SHUTTING_DOWN"),
            "SHUTTING_DOWN": ("OFF",),
        },
        timeline=(
            StateTransition("OFF", "INIT", 0.1),
            StateTransition("INIT", "CONFIGURING", 0.5),
            StateTransition("CONFIGURING", "READY", 1.2),
            StateTransition("READY", "ACTIVE", 1.5),
        ),
        fault_transitions={"BUS_OFF": "STANDBY", "LINK_LOSS": "STANDBY", "CRITICAL": "SHUTTING_DOWN"},
    )


def controller_profile() -> StateMachineProfile:
    states = ("OFF", "INIT", "SELF_TEST", "READY", "RUNNING", "DEGRADED", "ERROR", "SHUTDOWN")
    return StateMachineProfile(
        name="controller_operating",
        initial_state="OFF",
        allowed_states=states,
        allowed_transitions={
            "OFF": ("INIT",),
            "INIT": ("SELF_TEST",),
            "SELF_TEST": ("READY", "ERROR"),
            "READY": ("RUNNING", "SHUTDOWN"),
            "RUNNING": ("DEGRADED", "ERROR", "SHUTDOWN"),
            "DEGRADED": ("RUNNING", "ERROR", "SHUTDOWN"),
            "ERROR": ("SHUTDOWN",),
            "SHUTDOWN": ("OFF",),
        },
        timeline=(
            StateTransition("OFF", "INIT", 0.2),
            StateTransition("INIT", "SELF_TEST", 0.8),
            StateTransition("SELF_TEST", "READY", 1.4),
            StateTransition("READY", "RUNNING", 2.0),
        ),
        fault_transitions={"DEGRADED": "DEGRADED", "ERROR": "ERROR"},
    )


def function_profile() -> StateMachineProfile:
    return profile_from_states(
        "function_operating",
        ("INACTIVE", "INITIALIZING", "READY", "ACTIVE", "DEGRADED", "TERMINATING", "ERROR"),
        (0.2, 0.8, 1.4, 60.0, 62.0, 64.0),
    )


def operating_state(time_s: float) -> str:
    return StateMachineEngine(motor_profile()).state_at(time_s)
