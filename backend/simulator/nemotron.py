import os
import sys
import json
import argparse
import base64
import copy
import re
import shutil
import sqlite3
import subprocess
import urllib.error
import urllib.request
import time
from pathlib import Path
from typing import Union, Dict, List
from openai import OpenAI
from hardware_profile import normalize_hardware_config
from industry_knowledge import IndustryContext, IndustryKnowledgeService
from trace_realism import contains_external_signal_records, external_signal_records

SCHEMA = "communication-simulator.simulation-config.v1"
PROFILE_IMPORT_SCHEMA = "communication-simulator.profile-import.v1"
LIB_ROOT = Path("physic_lib")
TRACE_ROOT = Path("traces")
CONFIG_DB_PATH = LIB_ROOT / "Config" / "simulation_config.db"
INDUSTRY_PROFILE_ROOT = LIB_ROOT / "Industries"
DEFAULT_PROJECT_INDUSTRY = "Automotive"
PROJECT_PROFILE_DB_NAME = "project_profiles.db"
MANEUVER_DB_PATH = INDUSTRY_PROFILE_ROOT / DEFAULT_PROJECT_INDUSTRY / "maneuver_profiles.db"
PACKAGE_MODES = {
    "can": {
        "description": "CAN/CAN-FD/CAN-XL trace package",
        "formats": "blf,dbc,json,csv",
        "eth_bitrates": None,
        "eth_messages": None,
    },
    "ethernet": {
        "description": "Ethernet PCAP/PCAPNG trace package",
        "formats": "pcap,pcapng",
        "eth_bitrates": "1000000000",
        "eth_messages": 4,
    },
    "mixed": {
        "description": "Mixed trace package with CAN and Ethernet artifacts",
        "formats": "can-all,pcap,pcapng",
        "eth_bitrates": "1000000000",
        "eth_messages": 4,
    },
}
CAN_OUTPUT_FORMATS = {
    "blf", "dbc", "asc", "trc", "csv", "json", "log", "txt", "xml", "yaml", "yml", "arxml", "fibex", "mdf", "mf4",
}
ETH_OUTPUT_FORMATS = {"pcap", "pcapng"}
SIGNAL_VALUE_STRATEGIES = {
    "calculated": "Deterministic physical-looking signal values from timestamp, frame id, cycle, counter, mux, CRC, gateway and fault model.",
    "raw": "Raw payload-oriented values with minimal semantic interpretation.",
    "random": "Seeded random values inside signal ranges.",
    "hybrid": "Calculated baseline plus seeded noise and fault injection.",
}
PHYSICAL_AI_SKILL_NAMES = [
    "physical-ai-neural-reconstruction",
    "physical-ai-datasets",
    "ncore",
    "nre",
    "asset-harvester",
    "nurec-fixer",
]
DEFAULT_PACKAGE_MODES = copy.deepcopy(PACKAGE_MODES)
DEFAULT_CAN_OUTPUT_FORMATS = set(CAN_OUTPUT_FORMATS)
DEFAULT_ETH_OUTPUT_FORMATS = set(ETH_OUTPUT_FORMATS)
DEFAULT_SIGNAL_VALUE_STRATEGIES = copy.deepcopy(SIGNAL_VALUE_STRATEGIES)
DEFAULT_PHYSICAL_AI_SKILL_NAMES = list(PHYSICAL_AI_SKILL_NAMES)

def load_env_file(path=".env"):
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

load_env_file()

# NVIDIA Nemotron-3 Configuration
client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = os.getenv("NVIDIA_API_KEY")
)
LOCAL_AI_BASE_URL = os.getenv("LOCAL_AI_BASE_URL", "http://localhost:11434/v1")
LOCAL_AI_MODEL = os.getenv("LOCAL_AI_MODEL", "llama3.1:8b")
LOCAL_AI_API_KEY = os.getenv("LOCAL_AI_API_KEY", "local")

PROJECT_PROFILES = {
    "adas": {
        "description": "ADAS/autonomous driving restbus with perception, fusion, planning, braking, steering, and gateway traffic.",
        "bus_type": "fd",
        "channels": 4,
        "duration_s": 20.0,
        "messages": 24,
        "participants": [
            {
                "name": "ADAS_DOMAIN",
                "role": "domain_controller",
                "channel": 0,
                "cycle_ms": 10,
                "provided_services": ["OBJECT_FUSION", "TRAJECTORY_PLAN", "MOTION_REQUEST", "AEB_DECISION"],
                "consumed_services": ["OBJECT_LIST", "LANE_MODEL", "VEHICLE_DYNAMICS", "BRAKE_STATUS", "STEERING_STATUS"],
                "gateway_to_channel": 2,
                "health": "nominal",
            },
            {
                "name": "LIDAR_FRONT",
                "role": "lidar_sensor",
                "channel": 1,
                "cycle_ms": 20,
                "provided_services": ["OBJECT_LIST", "LIDAR_HEALTH"],
                "consumed_services": ["SYNC_TIME"],
                "health": "nominal",
            },
            {
                "name": "CAMERA_FRONT_WIDE",
                "role": "camera_sensor",
                "channel": 1,
                "cycle_ms": 33,
                "provided_services": ["LANE_MODEL", "OBJECT_LIST", "TRAFFIC_SIGN"],
                "consumed_services": ["SYNC_TIME"],
                "health": "nominal",
            },
            {
                "name": "RADAR_FRONT_LONG_RANGE",
                "role": "radar_sensor",
                "channel": 0,
                "cycle_ms": 20,
                "provided_services": ["OBJECT_LIST", "RANGE_RATE"],
                "consumed_services": ["SYNC_TIME"],
                "health": "nominal",
            },
            {
                "name": "RADAR_REAR_CORNER_LEFT",
                "role": "radar_sensor",
                "channel": 1,
                "cycle_ms": 50,
                "provided_services": ["BLIND_SPOT_OBJECTS"],
                "consumed_services": ["SYNC_TIME"],
                "health": "nominal",
            },
            {
                "name": "IMU_YAW_RATE_SENSOR",
                "role": "imu_sensor",
                "channel": 0,
                "cycle_ms": 10,
                "provided_services": ["VEHICLE_DYNAMICS"],
                "consumed_services": ["SYNC_TIME"],
                "health": "nominal",
            },
            {
                "name": "BRAKE_CONTROLLER",
                "role": "actuator_controller",
                "channel": 2,
                "cycle_ms": 10,
                "provided_services": ["BRAKE_STATUS", "ESC_STATUS"],
                "consumed_services": ["MOTION_REQUEST", "EMERGENCY_BRAKE_REQUEST"],
                "health": "nominal",
            },
            {
                "name": "STEERING_CONTROLLER",
                "role": "actuator_controller",
                "channel": 2,
                "cycle_ms": 10,
                "provided_services": ["STEERING_STATUS"],
                "consumed_services": ["TRAJECTORY_PLAN", "STEERING_TORQUE_REQUEST"],
                "health": "nominal",
            },
            {
                "name": "AMBIENT_TEMP_SENSOR",
                "role": "temperature_sensor",
                "channel": 3,
                "cycle_ms": 100,
                "provided_services": ["AMBIENT_TEMPERATURE"],
                "consumed_services": ["SYNC_TIME"],
                "health": "nominal",
            },
            {
                "name": "ADAS_ECU_TEMP_SENSOR",
                "role": "temperature_sensor",
                "channel": 3,
                "cycle_ms": 100,
                "provided_services": ["ECU_TEMPERATURE"],
                "consumed_services": ["SYNC_TIME"],
                "health": "nominal",
            },
            {
                "name": "CENTRAL_GATEWAY",
                "role": "gateway",
                "channel": 0,
                "cycle_ms": 50,
                "provided_services": ["ROUTING_STATUS", "SYNC_TIME", "AMBIENT_TEMPERATURE", "ECU_TEMPERATURE"],
                "consumed_services": ["DIAGNOSTIC_REQUEST", "AMBIENT_TEMPERATURE", "ECU_TEMPERATURE"],
                "gateway_to_channel": 3,
                "health": "nominal",
            },
            {
                "name": "DIAG_TESTER",
                "role": "tester",
                "channel": 3,
                "cycle_ms": 100,
                "provided_services": ["DIAGNOSTIC_REQUEST"],
                "consumed_services": ["ROUTING_STATUS", "BRAKE_STATUS", "STEERING_STATUS"],
                "health": "nominal",
            },
        ],
    },
    "powertrain": {
        "description": "Powertrain restbus with combustion engine, transmission, hybrid/EV high-voltage system, charging, thermal, brake and gateway ECUs.",
        "bus_type": "fd",
        "channels": 5,
        "duration_s": 20.0,
        "messages": 120,
        "participants": [
            {"name": "POWERTRAIN_DOMAIN", "role": "domain_controller", "channel": 0, "cycle_ms": 10, "provided_services": ["TORQUE_COORDINATION", "DRIVE_STATE", "DRIVELINE_LIMITS", "REGEN_REQUEST"], "consumed_services": ["PEDAL_POSITION", "WHEEL_SPEED", "BRAKE_STATUS", "GEAR_STATE", "ENGINE_STATUS", "FUEL_SYSTEM_STATUS", "EXHAUST_AFTERTREATMENT_STATUS", "HV_BATTERY_LIMITS", "HV_INTERLOCK_STATUS", "INVERTER_STATUS", "E_MOTOR_STATUS", "CHARGE_STATUS", "THERMAL_LIMITS"], "gateway_to_channel": 4, "health": "nominal"},
            {"name": "ENGINE_ECU", "role": "engine_controller", "channel": 0, "cycle_ms": 10, "provided_services": ["ENGINE_STATUS", "ENGINE_SPEED", "ENGINE_TORQUE_ACTUAL", "COMBUSTION_DIAGNOSTICS"], "consumed_services": ["TORQUE_REQUEST", "AIR_PATH_STATUS", "FUEL_PRESSURE", "COOLANT_TEMPERATURE"], "health": "nominal"},
            {"name": "TRANSMISSION_ECU", "role": "transmission_controller", "channel": 1, "cycle_ms": 20, "provided_services": ["GEAR_STATE", "CLUTCH_STATUS", "TRANSMISSION_TEMPERATURE"], "consumed_services": ["TORQUE_COORDINATION", "DRIVE_STATE"], "health": "nominal"},
            {"name": "ACCELERATOR_PEDAL_SENSOR", "role": "sensor", "channel": 0, "cycle_ms": 10, "provided_services": ["PEDAL_POSITION"], "consumed_services": ["SYNC_TIME"], "health": "nominal"},
            {"name": "FUEL_PUMP_CONTROL_MODULE", "role": "actuator_controller", "channel": 0, "cycle_ms": 20, "provided_services": ["FUEL_PRESSURE", "FUEL_SYSTEM_STATUS"], "consumed_services": ["ENGINE_STATUS", "TORQUE_REQUEST"], "health": "nominal"},
            {"name": "AIR_PATH_CONTROLLER", "role": "actuator_controller", "channel": 0, "cycle_ms": 20, "provided_services": ["AIR_PATH_STATUS", "BOOST_PRESSURE", "THROTTLE_STATUS"], "consumed_services": ["TORQUE_REQUEST", "ENGINE_STATUS"], "health": "nominal"},
            {"name": "EXHAUST_AFTERTREATMENT_ECU", "role": "emissions_controller", "channel": 0, "cycle_ms": 100, "provided_services": ["EXHAUST_AFTERTREATMENT_STATUS", "NOX_SENSOR_STATUS", "DPF_STATUS"], "consumed_services": ["ENGINE_STATUS", "EXHAUST_TEMPERATURE"], "health": "nominal"},
            {"name": "LAMBDA_SENSOR_BANK1", "role": "sensor", "channel": 0, "cycle_ms": 20, "provided_services": ["LAMBDA_VALUE"], "consumed_services": ["SYNC_TIME"], "health": "nominal"},
            {"name": "EXHAUST_TEMP_SENSOR", "role": "temperature_sensor", "channel": 0, "cycle_ms": 100, "provided_services": ["EXHAUST_TEMPERATURE"], "consumed_services": ["SYNC_TIME"], "health": "nominal"},
            {"name": "BATTERY_MANAGEMENT_SYSTEM", "role": "hv_battery_controller", "channel": 2, "cycle_ms": 20, "provided_services": ["HV_BATTERY_LIMITS", "SOC_STATUS", "SOH_STATUS", "CELL_VOLTAGE_STATUS", "CELL_TEMPERATURE_STATUS", "HV_INTERLOCK_STATUS", "INSULATION_STATUS"], "consumed_services": ["THERMAL_LIMITS", "CHARGE_REQUEST", "REGEN_REQUEST"], "health": "nominal"},
            {"name": "CELL_MONITORING_UNIT_FRONT", "role": "hv_sensor", "channel": 2, "cycle_ms": 50, "provided_services": ["CELL_VOLTAGE_STATUS", "CELL_TEMPERATURE_STATUS"], "consumed_services": ["SYNC_TIME"], "health": "nominal"},
            {"name": "CELL_MONITORING_UNIT_REAR", "role": "hv_sensor", "channel": 2, "cycle_ms": 50, "provided_services": ["CELL_VOLTAGE_STATUS", "CELL_TEMPERATURE_STATUS"], "consumed_services": ["SYNC_TIME"], "health": "nominal"},
            {"name": "HV_CONTACTOR_BOX", "role": "hv_actuator_controller", "channel": 2, "cycle_ms": 10, "provided_services": ["CONTACTOR_STATUS", "PRECHARGE_STATUS", "HV_INTERLOCK_STATUS"], "consumed_services": ["HV_ENABLE_COMMAND", "CHARGE_REQUEST", "INSULATION_STATUS"], "health": "nominal"},
            {"name": "INVERTER_FRONT", "role": "inverter_controller", "channel": 2, "cycle_ms": 5, "provided_services": ["INVERTER_STATUS", "PHASE_CURRENT_STATUS"], "consumed_services": ["TORQUE_COORDINATION", "HV_BATTERY_LIMITS", "THERMAL_LIMITS"], "health": "nominal"},
            {"name": "E_MOTOR_FRONT", "role": "motor_controller", "channel": 2, "cycle_ms": 5, "provided_services": ["E_MOTOR_STATUS", "ROTOR_POSITION", "MOTOR_TEMPERATURE"], "consumed_services": ["INVERTER_STATUS", "TORQUE_COORDINATION"], "health": "nominal"},
            {"name": "DC_DC_CONVERTER", "role": "power_electronics_controller", "channel": 2, "cycle_ms": 20, "provided_services": ["LV_POWER_STATUS", "DC_DC_STATUS"], "consumed_services": ["HV_BATTERY_LIMITS", "HV_ENABLE_COMMAND"], "health": "nominal"},
            {"name": "ONBOARD_CHARGER", "role": "charging_controller", "channel": 3, "cycle_ms": 50, "provided_services": ["CHARGE_STATUS", "AC_CHARGER_STATUS"], "consumed_services": ["CHARGE_REQUEST", "HV_BATTERY_LIMITS", "THERMAL_LIMITS"], "health": "nominal"},
            {"name": "DC_FAST_CHARGE_CONTROLLER", "role": "charging_controller", "channel": 3, "cycle_ms": 20, "provided_services": ["DC_CHARGE_STATUS", "CHARGE_SESSION_STATUS"], "consumed_services": ["CHARGE_REQUEST", "HV_BATTERY_LIMITS", "CONTACTOR_STATUS"], "health": "nominal"},
            {"name": "CHARGE_PORT_MODULE", "role": "actuator_controller", "channel": 3, "cycle_ms": 100, "provided_services": ["CHARGE_PORT_STATUS", "PLUG_LOCK_STATUS", "CHARGE_REQUEST"], "consumed_services": ["LOCK_COMMAND", "SYNC_TIME"], "health": "nominal"},
            {"name": "THERMAL_CONTROLLER", "role": "thermal_controller", "channel": 3, "cycle_ms": 50, "provided_services": ["THERMAL_LIMITS", "COOLANT_TEMPERATURE", "BATTERY_COOLING_STATUS"], "consumed_services": ["DRIVE_STATE", "CELL_TEMPERATURE_STATUS", "MOTOR_TEMPERATURE", "INVERTER_STATUS", "CHARGE_STATUS"], "health": "nominal"},
            {"name": "COOLANT_PUMP_CONTROLLER", "role": "actuator_controller", "channel": 3, "cycle_ms": 50, "provided_services": ["COOLANT_FLOW_STATUS"], "consumed_services": ["THERMAL_LIMITS", "BATTERY_COOLING_STATUS"], "health": "nominal"},
            {"name": "BRAKE_CONTROLLER", "role": "actuator_controller", "channel": 4, "cycle_ms": 10, "provided_services": ["WHEEL_SPEED", "BRAKE_STATUS", "REGEN_BRAKE_LIMIT"], "consumed_services": ["TORQUE_COORDINATION", "REGEN_REQUEST"], "health": "nominal"},
            {"name": "CENTRAL_GATEWAY", "role": "gateway", "channel": 0, "cycle_ms": 50, "provided_services": ["ROUTING_STATUS", "SYNC_TIME", "LOCK_COMMAND", "HV_ENABLE_COMMAND", "TORQUE_REQUEST", "CHARGE_REQUEST"], "consumed_services": ["DIAGNOSTIC_REQUEST", "DRIVE_STATE", "HV_BATTERY_LIMITS", "SOC_STATUS", "CHARGE_STATUS", "DC_CHARGE_STATUS", "LV_POWER_STATUS", "ENGINE_STATUS", "EXHAUST_AFTERTREATMENT_STATUS"], "gateway_to_channel": 4, "health": "nominal"},
            {"name": "DIAG_TESTER", "role": "tester", "channel": 4, "cycle_ms": 100, "provided_services": ["DIAGNOSTIC_REQUEST"], "consumed_services": ["ROUTING_STATUS", "ENGINE_STATUS", "HV_BATTERY_LIMITS", "INVERTER_STATUS", "CHARGE_STATUS", "INSULATION_STATUS"], "health": "nominal"},
        ],
    },
    "body": {
        "description": "Body, access, infotainment, connectivity, OTA and safety restbus with BCM, KESSY, doors, lights, HVAC, seats, cluster, HUD, radio, infotainment, GNSS/GPS, telematics, V2X, OTA, airbag, parking and diagnostics.",
        "bus_type": "fd",
        "channels": 5,
        "duration_s": 30.0,
        "messages": 160,
        "participants": [
            {"name": "BODY_CONTROL_MODULE", "role": "domain_controller", "channel": 0, "cycle_ms": 50, "provided_services": ["BODY_STATE", "LIGHT_COMMAND", "LOCK_COMMAND", "WINDOW_COMMAND", "WIPER_COMMAND", "INTERIOR_LIGHT_COMMAND", "IGNITION_STATE"], "consumed_services": ["DOOR_STATUS", "LOCK_STATUS", "WINDOW_STATUS", "RAIN_LIGHT_STATUS", "HVAC_STATUS", "SEAT_STATUS", "KESSY_AUTH_STATUS", "AIRBAG_STATUS", "CRASH_EVENT", "PARK_DISTANCE"], "gateway_to_channel": 4, "health": "nominal"},
            {"name": "KESSY_KEYLESS_ACCESS", "role": "access_ecu", "channel": 0, "cycle_ms": 50, "provided_services": ["KESSY_AUTH_STATUS", "PEPS_STATUS", "IMMOBILIZER_RELEASE"], "consumed_services": ["BODY_STATE", "LOCK_COMMAND", "DIAGNOSTIC_REQUEST"], "health": "nominal"},
            {"name": "DOOR_MODULE_FL", "role": "actuator_controller", "channel": 0, "cycle_ms": 100, "provided_services": ["DOOR_STATUS", "WINDOW_STATUS", "LOCK_STATUS"], "consumed_services": ["LOCK_COMMAND", "WINDOW_COMMAND"], "health": "nominal"},
            {"name": "DOOR_MODULE_FR", "role": "actuator_controller", "channel": 0, "cycle_ms": 100, "provided_services": ["DOOR_STATUS", "WINDOW_STATUS", "LOCK_STATUS"], "consumed_services": ["LOCK_COMMAND", "WINDOW_COMMAND"], "health": "nominal"},
            {"name": "DOOR_MODULE_RL", "role": "actuator_controller", "channel": 0, "cycle_ms": 100, "provided_services": ["DOOR_STATUS", "WINDOW_STATUS", "LOCK_STATUS"], "consumed_services": ["LOCK_COMMAND", "WINDOW_COMMAND"], "health": "nominal"},
            {"name": "DOOR_MODULE_RR", "role": "actuator_controller", "channel": 0, "cycle_ms": 100, "provided_services": ["DOOR_STATUS", "WINDOW_STATUS", "LOCK_STATUS"], "consumed_services": ["LOCK_COMMAND", "WINDOW_COMMAND"], "health": "nominal"},
            {"name": "TAILGATE_MODULE", "role": "actuator_controller", "channel": 0, "cycle_ms": 100, "provided_services": ["TAILGATE_STATUS"], "consumed_services": ["LOCK_COMMAND", "BODY_STATE"], "health": "nominal"},
            {"name": "LIGHT_CONTROL_MODULE", "role": "actuator_controller", "channel": 1, "cycle_ms": 50, "provided_services": ["LIGHT_STATUS", "EXTERIOR_LIGHT_STATUS"], "consumed_services": ["LIGHT_COMMAND", "RAIN_LIGHT_STATUS"], "health": "nominal"},
            {"name": "RAIN_LIGHT_SENSOR", "role": "sensor", "channel": 1, "cycle_ms": 100, "provided_services": ["RAIN_LIGHT_STATUS"], "consumed_services": ["SYNC_TIME"], "health": "nominal"},
            {"name": "WIPER_CONTROLLER", "role": "actuator_controller", "channel": 1, "cycle_ms": 50, "provided_services": ["WIPER_STATUS"], "consumed_services": ["WIPER_COMMAND", "RAIN_LIGHT_STATUS"], "health": "nominal"},
            {"name": "HVAC_CONTROLLER", "role": "actuator_controller", "channel": 1, "cycle_ms": 100, "provided_services": ["HVAC_STATUS", "CABIN_TEMPERATURE"], "consumed_services": ["BODY_STATE", "HMI_COMMAND"], "health": "nominal"},
            {"name": "SUNROOF_CONTROLLER", "role": "actuator_controller", "channel": 1, "cycle_ms": 100, "provided_services": ["ROOF_STATUS"], "consumed_services": ["BODY_STATE", "WINDOW_COMMAND"], "health": "nominal"},
            {"name": "SEAT_CONTROLLER_DRIVER", "role": "actuator_controller", "channel": 2, "cycle_ms": 100, "provided_services": ["SEAT_STATUS", "OCCUPANT_STATUS"], "consumed_services": ["BODY_STATE", "SEAT_MEMORY_COMMAND"], "health": "nominal"},
            {"name": "SEAT_CONTROLLER_PASSENGER", "role": "actuator_controller", "channel": 2, "cycle_ms": 100, "provided_services": ["SEAT_STATUS", "OCCUPANT_STATUS"], "consumed_services": ["BODY_STATE", "SEAT_MEMORY_COMMAND"], "health": "nominal"},
            {"name": "AIRBAG_CONTROL_UNIT", "role": "safety_controller", "channel": 2, "cycle_ms": 10, "provided_services": ["AIRBAG_STATUS", "CRASH_EVENT", "RESTRAINT_STATUS"], "consumed_services": ["OCCUPANT_STATUS", "VEHICLE_SPEED", "IGNITION_STATE", "DIAGNOSTIC_REQUEST"], "health": "nominal"},
            {"name": "PARK_DISTANCE_CONTROL", "role": "parking_controller", "channel": 2, "cycle_ms": 40, "provided_services": ["PARK_DISTANCE", "PARK_WARNING"], "consumed_services": ["BODY_STATE", "VEHICLE_SPEED"], "health": "nominal"},
            {"name": "REAR_VIEW_CAMERA", "role": "camera_sensor", "channel": 2, "cycle_ms": 33, "provided_services": ["CAMERA_REAR_VIEW"], "consumed_services": ["BODY_STATE"], "health": "nominal"},
            {"name": "INSTRUMENT_CLUSTER_KOMBI", "role": "display_controller", "channel": 3, "cycle_ms": 20, "provided_services": ["CLUSTER_STATUS", "DRIVER_WARNING_ACK"], "consumed_services": ["VEHICLE_SPEED", "IGNITION_STATE", "BODY_STATE", "DOOR_STATUS", "LIGHT_STATUS", "AIRBAG_STATUS", "CRASH_EVENT", "PARK_WARNING", "MEDIA_INFO", "NAV_GUIDANCE"], "health": "nominal"},
            {"name": "HUD_CONTROLLER", "role": "display_controller", "channel": 3, "cycle_ms": 20, "provided_services": ["HUD_STATUS"], "consumed_services": ["VEHICLE_SPEED", "ADAS_DISPLAY_OBJECTS", "NAV_GUIDANCE", "DRIVER_WARNING"], "health": "nominal"},
            {"name": "INFOTAINMENT_HEAD_UNIT", "role": "infotainment_controller", "channel": 3, "cycle_ms": 50, "provided_services": ["INFOTAINMENT_STATUS", "HMI_COMMAND", "MEDIA_INFO", "NAV_GUIDANCE", "PHONE_STATUS", "DRIVER_WARNING"], "consumed_services": ["IGNITION_STATE", "VEHICLE_SPEED", "HVAC_STATUS", "AUDIO_STATUS", "PARK_DISTANCE", "CAMERA_REAR_VIEW"], "health": "nominal"},
            {"name": "RADIO_TUNER", "role": "infotainment_ecu", "channel": 3, "cycle_ms": 100, "provided_services": ["AUDIO_STATUS", "TUNER_STATUS"], "consumed_services": ["HMI_COMMAND", "INFOTAINMENT_STATUS"], "health": "nominal"},
            {"name": "AMPLIFIER_DSP", "role": "infotainment_ecu", "channel": 3, "cycle_ms": 50, "provided_services": ["AMPLIFIER_STATUS"], "consumed_services": ["MEDIA_INFO", "AUDIO_STATUS"], "health": "nominal"},
            {"name": "TELEMATICS_CONTROL_UNIT", "role": "connectivity_ecu", "channel": 3, "cycle_ms": 100, "provided_services": ["GNSS_POSITION", "ECALL_STATUS", "CONNECTIVITY_STATUS"], "consumed_services": ["CRASH_EVENT", "IGNITION_STATE", "DIAGNOSTIC_REQUEST"], "health": "nominal"},
            {"name": "GNSS_RECEIVER", "role": "positioning_sensor", "channel": 3, "cycle_ms": 100, "provided_services": ["GNSS_POSITION", "GNSS_TIME", "POSITION_ACCURACY"], "consumed_services": ["SYNC_TIME"], "health": "nominal"},
            {"name": "OTA_UPDATE_MANAGER", "role": "software_update_controller", "channel": 3, "cycle_ms": 200, "provided_services": ["OTA_STATUS", "UPDATE_CAMPAIGN_STATUS", "SOFTWARE_VERSION_INVENTORY"], "consumed_services": ["CONNECTIVITY_STATUS", "CYBERSECURITY_STATUS", "IGNITION_STATE", "BATTERY_SOC", "DIAGNOSTIC_REQUEST"], "health": "nominal"},
            {"name": "CYBERSECURITY_GATEWAY", "role": "security_controller", "channel": 3, "cycle_ms": 50, "provided_services": ["CYBERSECURITY_STATUS", "FIREWALL_STATUS", "CERTIFICATE_STATUS"], "consumed_services": ["CONNECTIVITY_STATUS", "OTA_STATUS", "DIAGNOSTIC_REQUEST"], "health": "nominal"},
            {"name": "V2X_CONTROL_UNIT", "role": "connectivity_ecu", "channel": 3, "cycle_ms": 100, "provided_services": ["V2X_STATUS", "ROAD_HAZARD_WARNING", "SPAT_MAP_DATA"], "consumed_services": ["GNSS_POSITION", "GNSS_TIME", "VEHICLE_SPEED", "CYBERSECURITY_STATUS"], "health": "nominal"},
            {"name": "CELLULAR_MODEM_5G", "role": "connectivity_ecu", "channel": 3, "cycle_ms": 100, "provided_services": ["CELLULAR_LINK_STATUS", "CLOUD_CONNECTION_STATUS", "ESIM_STATUS"], "consumed_services": ["OTA_STATUS", "ECALL_STATUS", "DIAGNOSTIC_REQUEST"], "health": "nominal"},
            {"name": "WIFI_BLUETOOTH_MODULE", "role": "connectivity_ecu", "channel": 3, "cycle_ms": 100, "provided_services": ["WIFI_STATUS", "BLUETOOTH_STATUS", "DEVICE_PAIRING_STATUS"], "consumed_services": ["HMI_COMMAND", "INFOTAINMENT_STATUS", "CYBERSECURITY_STATUS"], "health": "nominal"},
            {"name": "DATA_LOGGER_RECORDER", "role": "logging_ecu", "channel": 3, "cycle_ms": 100, "provided_services": ["LOGGING_STATUS", "EVENT_SNAPSHOT_STATUS"], "consumed_services": ["CRASH_EVENT", "DIAGNOSTIC_REQUEST", "OTA_STATUS", "GNSS_POSITION", "BODY_STATE"], "health": "nominal"},
            {"name": "TPMS_RECEIVER", "role": "sensor", "channel": 4, "cycle_ms": 500, "provided_services": ["TIRE_PRESSURE_STATUS"], "consumed_services": ["SYNC_TIME"], "health": "nominal"},
            {"name": "STEERING_COLUMN_MODULE", "role": "input_controller", "channel": 4, "cycle_ms": 20, "provided_services": ["STALK_SWITCH_STATUS", "STEERING_WHEEL_BUTTONS"], "consumed_services": ["SYNC_TIME"], "health": "nominal"},
            {"name": "CENTRAL_GATEWAY", "role": "gateway", "channel": 0, "cycle_ms": 50, "provided_services": ["ROUTING_STATUS", "SYNC_TIME", "VEHICLE_SPEED", "BATTERY_SOC", "ADAS_DISPLAY_OBJECTS"], "consumed_services": ["DIAGNOSTIC_REQUEST", "BODY_STATE", "AIRBAG_STATUS", "CRASH_EVENT", "INFOTAINMENT_STATUS", "CLUSTER_STATUS", "ECALL_STATUS", "TIRE_PRESSURE_STATUS", "OTA_STATUS", "CYBERSECURITY_STATUS", "V2X_STATUS", "GNSS_POSITION", "CLOUD_CONNECTION_STATUS"], "gateway_to_channel": 4, "health": "nominal"},
            {"name": "DIAG_TESTER", "role": "tester", "channel": 4, "cycle_ms": 100, "provided_services": ["DIAGNOSTIC_REQUEST"], "consumed_services": ["ROUTING_STATUS", "BODY_STATE", "KESSY_AUTH_STATUS", "AIRBAG_STATUS", "INFOTAINMENT_STATUS", "CLUSTER_STATUS", "OTA_STATUS", "SOFTWARE_VERSION_INVENTORY", "CYBERSECURITY_STATUS"], "health": "nominal"},
        ],
    },
}
DEFAULT_PROJECT_PROFILES = copy.deepcopy(PROJECT_PROFILES)

MANEUVER_PROFILES = {}
PHYSICAL_AI_WORKFLOWS = {}

DEFAULT_MANEUVER_ROWS = [
    {
        "key": "emergency_brake",
        "domain": "automotive",
        "description": "AEB/full braking: high-frequency perception and dynamics, emergency brake request, brake/ESC feedback.",
        "duration_s": 12.0,
        "keywords": ["notbrems", "emergency brake", "aeb", "vollbrems", "bremsmanoever", "bremsmanöver"],
        "service_links": [
            ("RADAR_FRONT_LONG_RANGE", "OBJECT_LIST", "ADAS_DOMAIN"),
            ("CAMERA_FRONT_WIDE", "LANE_MODEL", "ADAS_DOMAIN"),
            ("IMU_YAW_RATE_SENSOR", "VEHICLE_DYNAMICS", "ADAS_DOMAIN"),
            ("ADAS_DOMAIN", "EMERGENCY_BRAKE_REQUEST", "BRAKE_CONTROLLER"),
            ("BRAKE_CONTROLLER", "BRAKE_STATUS", "ADAS_DOMAIN"),
            ("BRAKE_CONTROLLER", "ESC_STATUS", "ADAS_DOMAIN"),
        ],
        "cycle_overrides": [("ADAS_DOMAIN", 10), ("RADAR_FRONT_LONG_RANGE", 10), ("IMU_YAW_RATE_SENSOR", 5), ("BRAKE_CONTROLLER", 5)],
    },
    {
        "key": "lane_change",
        "domain": "automotive",
        "description": "Lane change: lane model, blind spot, trajectory planning, steering request and steering feedback.",
        "duration_s": 18.0,
        "keywords": ["spurwechsel", "lane change", "ueberholen", "überholen", "einscheren"],
        "service_links": [
            ("CAMERA_FRONT_WIDE", "LANE_MODEL", "ADAS_DOMAIN"),
            ("RADAR_REAR_CORNER_LEFT", "BLIND_SPOT_OBJECTS", "ADAS_DOMAIN"),
            ("ADAS_DOMAIN", "TRAJECTORY_PLAN", "STEERING_CONTROLLER"),
            ("ADAS_DOMAIN", "STEERING_TORQUE_REQUEST", "STEERING_CONTROLLER"),
            ("STEERING_CONTROLLER", "STEERING_STATUS", "ADAS_DOMAIN"),
        ],
        "cycle_overrides": [("ADAS_DOMAIN", 10), ("CAMERA_FRONT_WIDE", 20), ("STEERING_CONTROLLER", 10)],
    },
    {
        "key": "parking",
        "domain": "automotive",
        "description": "Parking maneuver: ultrasonic sensors, park assist, low-speed braking and steering.",
        "duration_s": 25.0,
        "keywords": ["parken", "parking", "einparken", "rangieren"],
        "required_participants": [
            ("PARK_ASSIST", "domain_controller", 1, 40, "PARK_TRAJECTORY,LOW_SPEED_MOTION_REQUEST", "ULTRASONIC_DISTANCE,VEHICLE_DYNAMICS,BRAKE_STATUS,STEERING_STATUS", 2, "nominal"),
            ("ULTRASONIC_FRONT_CLUSTER", "ultrasonic_sensor", 1, 40, "ULTRASONIC_DISTANCE", "SYNC_TIME", None, "nominal"),
            ("ULTRASONIC_REAR_CLUSTER", "ultrasonic_sensor", 1, 40, "ULTRASONIC_DISTANCE", "SYNC_TIME", None, "nominal"),
        ],
        "service_links": [
            ("ULTRASONIC_FRONT_CLUSTER", "ULTRASONIC_DISTANCE", "PARK_ASSIST"),
            ("ULTRASONIC_REAR_CLUSTER", "ULTRASONIC_DISTANCE", "PARK_ASSIST"),
            ("PARK_ASSIST", "PARK_TRAJECTORY", "STEERING_CONTROLLER"),
            ("PARK_ASSIST", "LOW_SPEED_MOTION_REQUEST", "BRAKE_CONTROLLER"),
        ],
    },
    {
        "key": "acc",
        "domain": "automotive",
        "description": "Adaptive cruise control: front radar, speed, torque and brake coordination.",
        "duration_s": 30.0,
        "keywords": ["acc", "adaptive cruise", "abstandsregel", "tempomat", "kolonnenfahrt"],
        "service_links": [
            ("RADAR_FRONT_LONG_RANGE", "OBJECT_LIST", "ADAS_DOMAIN"),
            ("IMU_YAW_RATE_SENSOR", "VEHICLE_DYNAMICS", "ADAS_DOMAIN"),
            ("ADAS_DOMAIN", "MOTION_REQUEST", "BRAKE_CONTROLLER"),
            ("ADAS_DOMAIN", "TORQUE_REQUEST", "POWERTRAIN_DOMAIN"),
            ("BRAKE_CONTROLLER", "BRAKE_STATUS", "ADAS_DOMAIN"),
        ],
    },
    {
        "key": "cut_in",
        "domain": "automotive",
        "description": "Cut-in vehicle ahead: object fusion, collision prediction, brake and trajectory response.",
        "duration_s": 15.0,
        "keywords": ["cut in", "cut-in", "einscherer", "einscheren vor fahrzeug"],
        "service_links": [
            ("RADAR_FRONT_LONG_RANGE", "OBJECT_LIST", "ADAS_DOMAIN"),
            ("CAMERA_FRONT_WIDE", "OBJECT_LIST", "ADAS_DOMAIN"),
            ("ADAS_DOMAIN", "TRAJECTORY_PLAN", "STEERING_CONTROLLER"),
            ("ADAS_DOMAIN", "MOTION_REQUEST", "BRAKE_CONTROLLER"),
            ("BRAKE_CONTROLLER", "BRAKE_STATUS", "ADAS_DOMAIN"),
        ],
        "cycle_overrides": [("ADAS_DOMAIN", 10), ("RADAR_FRONT_LONG_RANGE", 10), ("BRAKE_CONTROLLER", 10)],
    },
    {
        "key": "cut_out",
        "domain": "automotive",
        "description": "Lead vehicle cut-out: radar reacquisition, free-road acceleration and torque coordination.",
        "duration_s": 18.0,
        "keywords": ["cut out", "cut-out", "ausscheren", "vorausfahrender wechselt"],
        "service_links": [
            ("RADAR_FRONT_LONG_RANGE", "OBJECT_LIST", "ADAS_DOMAIN"),
            ("CAMERA_FRONT_WIDE", "LANE_MODEL", "ADAS_DOMAIN"),
            ("ADAS_DOMAIN", "TORQUE_REQUEST", "POWERTRAIN_DOMAIN"),
            ("ADAS_DOMAIN", "MOTION_REQUEST", "BRAKE_CONTROLLER"),
        ],
    },
    {
        "key": "stop_and_go",
        "domain": "automotive",
        "description": "Stop-and-go traffic: repeated brake/torque requests, vehicle dynamics and lead-object tracking.",
        "duration_s": 45.0,
        "keywords": ["stop and go", "stop-and-go", "stau", "staufolgefahrt"],
        "service_links": [
            ("RADAR_FRONT_LONG_RANGE", "OBJECT_LIST", "ADAS_DOMAIN"),
            ("IMU_YAW_RATE_SENSOR", "VEHICLE_DYNAMICS", "ADAS_DOMAIN"),
            ("ADAS_DOMAIN", "MOTION_REQUEST", "BRAKE_CONTROLLER"),
            ("ADAS_DOMAIN", "TORQUE_REQUEST", "POWERTRAIN_DOMAIN"),
            ("BRAKE_CONTROLLER", "BRAKE_STATUS", "ADAS_DOMAIN"),
        ],
    },
    {
        "key": "highway_merge",
        "domain": "automotive",
        "description": "Highway merge: lane model, blind spot objects, acceleration request and steering plan.",
        "duration_s": 25.0,
        "keywords": ["autobahn auffahrt", "highway merge", "einfädeln", "einfaedeln"],
        "service_links": [
            ("CAMERA_FRONT_WIDE", "LANE_MODEL", "ADAS_DOMAIN"),
            ("RADAR_REAR_CORNER_LEFT", "BLIND_SPOT_OBJECTS", "ADAS_DOMAIN"),
            ("ADAS_DOMAIN", "TRAJECTORY_PLAN", "STEERING_CONTROLLER"),
            ("ADAS_DOMAIN", "TORQUE_REQUEST", "POWERTRAIN_DOMAIN"),
        ],
    },
    {
        "key": "evasive_steering",
        "domain": "automotive",
        "description": "Evasive steering: obstacle detection, emergency trajectory, steering torque and brake stabilization.",
        "duration_s": 10.0,
        "keywords": ["ausweich", "evasive", "hindernis", "ausweichmanöver", "ausweichmanoever"],
        "service_links": [
            ("RADAR_FRONT_LONG_RANGE", "OBJECT_LIST", "ADAS_DOMAIN"),
            ("CAMERA_FRONT_WIDE", "OBJECT_LIST", "ADAS_DOMAIN"),
            ("ADAS_DOMAIN", "STEERING_TORQUE_REQUEST", "STEERING_CONTROLLER"),
            ("ADAS_DOMAIN", "MOTION_REQUEST", "BRAKE_CONTROLLER"),
            ("STEERING_CONTROLLER", "STEERING_STATUS", "ADAS_DOMAIN"),
        ],
        "cycle_overrides": [("ADAS_DOMAIN", 5), ("STEERING_CONTROLLER", 5), ("BRAKE_CONTROLLER", 5)],
    },
    {
        "key": "pedestrian_crossing",
        "domain": "automotive",
        "description": "Pedestrian crossing: camera/radar object classification, AEB decision and brake request.",
        "duration_s": 12.0,
        "keywords": ["fussgaenger", "fußgänger", "pedestrian", "zebrastreifen"],
        "service_links": [
            ("CAMERA_FRONT_WIDE", "OBJECT_LIST", "ADAS_DOMAIN"),
            ("RADAR_FRONT_LONG_RANGE", "OBJECT_LIST", "ADAS_DOMAIN"),
            ("ADAS_DOMAIN", "EMERGENCY_BRAKE_REQUEST", "BRAKE_CONTROLLER"),
            ("BRAKE_CONTROLLER", "BRAKE_STATUS", "ADAS_DOMAIN"),
        ],
        "cycle_overrides": [("ADAS_DOMAIN", 5), ("CAMERA_FRONT_WIDE", 20), ("BRAKE_CONTROLLER", 5)],
    },
    {
        "key": "intersection_turn",
        "domain": "automotive",
        "description": "Intersection turn assist: lane/path model, object fusion, steering and low-speed brake coordination.",
        "duration_s": 22.0,
        "keywords": ["kreuzung", "abbiegen", "intersection", "turn assist"],
        "service_links": [
            ("CAMERA_FRONT_WIDE", "LANE_MODEL", "ADAS_DOMAIN"),
            ("RADAR_FRONT_LONG_RANGE", "OBJECT_LIST", "ADAS_DOMAIN"),
            ("ADAS_DOMAIN", "TRAJECTORY_PLAN", "STEERING_CONTROLLER"),
            ("ADAS_DOMAIN", "MOTION_REQUEST", "BRAKE_CONTROLLER"),
        ],
    },
    {
        "key": "hill_start",
        "domain": "automotive",
        "description": "Hill start: brake hold, torque buildup, vehicle dynamics and rollback prevention.",
        "duration_s": 14.0,
        "keywords": ["berg anfahren", "hill start", "anfahrassistent", "rollback"],
        "service_links": [
            ("IMU_YAW_RATE_SENSOR", "VEHICLE_DYNAMICS", "POWERTRAIN_DOMAIN"),
            ("BRAKE_CONTROLLER", "BRAKE_STATUS", "POWERTRAIN_DOMAIN"),
            ("POWERTRAIN_DOMAIN", "TORQUE_REQUEST", "ENGINE_ECU"),
            ("POWERTRAIN_DOMAIN", "TORQUE_COORDINATION", "BRAKE_CONTROLLER"),
        ],
        "cycle_overrides": [("POWERTRAIN_DOMAIN", 10), ("BRAKE_CONTROLLER", 10), ("ENGINE_ECU", 10)],
    },
    {
        "key": "kickdown",
        "domain": "automotive",
        "description": "Kickdown acceleration: pedal jump, torque request, gear shift and engine response.",
        "duration_s": 12.0,
        "keywords": ["kickdown", "vollgas", "beschleunigung", "acceleration"],
        "service_links": [
            ("ACCELERATOR_PEDAL_SENSOR", "PEDAL_POSITION", "POWERTRAIN_DOMAIN"),
            ("POWERTRAIN_DOMAIN", "TORQUE_REQUEST", "ENGINE_ECU"),
            ("POWERTRAIN_DOMAIN", "TORQUE_COORDINATION", "TRANSMISSION_ECU"),
            ("TRANSMISSION_ECU", "GEAR_STATE", "POWERTRAIN_DOMAIN"),
        ],
    },
    {
        "key": "regenerative_braking",
        "domain": "automotive",
        "description": "Regenerative braking: brake blending, battery limits, torque recuperation and brake status.",
        "duration_s": 20.0,
        "keywords": ["rekkuperation", "rekuperation", "regen braking", "regenerative braking"],
        "service_links": [
            ("BATTERY_MANAGEMENT_SYSTEM", "BATTERY_LIMITS", "POWERTRAIN_DOMAIN"),
            ("BRAKE_CONTROLLER", "BRAKE_STATUS", "POWERTRAIN_DOMAIN"),
            ("POWERTRAIN_DOMAIN", "TORQUE_REQUEST", "ENGINE_ECU"),
            ("POWERTRAIN_DOMAIN", "TORQUE_COORDINATION", "BRAKE_CONTROLLER"),
        ],
    },
]

DEFAULT_PHYSICAL_AI_WORKFLOWS = [
    {
        "key": "own_recording_to_usdz",
        "description": "Make a NuRec USDZ scene from your own camera, LiDAR, radar, depth, stereo, ROS, COLMAP, or dataset recording.",
        "keywords": ["own recording", "eigene aufnahme", "sensor log", "ros bag", "colmap", "ncore", "train", "training", "usdz erstellen", "neural reconstruction"],
        "steps": [
            ("ncore", "Convert the source recording to NCore V4."),
            ("nre", "Generate auxiliary inputs, train the reconstruction, validate, and export USDZ."),
        ],
    },
    {
        "key": "download_and_render_scene",
        "description": "Use an NVIDIA-published NuRec scene and render views without training.",
        "keywords": ["download", "dataset", "physicalai-autonomous-vehicles-nurec", "existing scene", "render scene", "demo scene"],
        "steps": [
            ("physical-ai-datasets", "Download one accepted, gated NuRec scene from Hugging Face."),
            ("nre", "Render RGB, LiDAR, or shifted camera views from the USDZ."),
        ],
    },
    {
        "key": "edit_scene_objects",
        "description": "Add, remove, or replace 3D actors in a NuRec driving scene.",
        "keywords": ["add object", "remove object", "replace object", "actor", "asset harvester", "insert car", "pedestrian insert"],
        "steps": [
            ("ncore", "Ensure the original NCore clip is available for object cropping."),
            ("asset-harvester", "Extract target actors as 3D Gaussian assets with metadata."),
            ("nre", "Package assets and render edited scenes through actor editing."),
        ],
    },
    {
        "key": "cleanup_rendered_frames",
        "description": "Clean NuRec rendered frames with inline DiFix or standalone DiffusionHarmonizer.",
        "keywords": ["cleanup", "clean up", "ghosting", "floaters", "flicker", "difix", "harmonizer", "diffusionharmonizer", "nurec fixer"],
        "steps": [
            ("nre", "Prefer inline cleanup via NRE when rendering through NRE."),
            ("nurec-fixer", "Use standalone DiffusionHarmonizer for already-rendered frames or paired evaluation."),
        ],
    },
    {
        "key": "benchmark_quality",
        "description": "Benchmark reconstruction or rendering quality with PhysicalAI-NuRec-PPISP.",
        "keywords": ["benchmark", "quality", "psnr", "ssim", "lpips", "ppisp", "eval", "metrics"],
        "steps": [
            ("physical-ai-datasets", "Download the benchmark dataset after accepting gated licenses."),
            ("nre", "Train or render and run evaluation metrics against ground truth."),
        ],
    },
    {
        "key": "simulator_grpc",
        "description": "Connect a NuRec USDZ scene to CARLA, Isaac Sim, AlpaSim, or a custom simulator over gRPC.",
        "keywords": ["grpc", "serve-grpc", "render-grpc", "carla", "isaac", "alpasim", "simulator", "sensor sim", "warm server"],
        "steps": [
            ("physical-ai-datasets", "Pick or download a USDZ scene if none is available."),
            ("nre", "Start a warm serve-grpc server and render frames or LiDAR sweeps from simulator poses."),
        ],
    },
]

SYSTEM_PROMPT = """You are an expert in standalone communication and bus simulation.
Your task is to generate a JSON simulation configuration for the `communication-simulator` tool.

The configuration must follow this schema: `communication-simulator.simulation-config.v1`.

### JSON Structure:
{
  "schema": "communication-simulator.simulation-config.v1",
  "simulation_mode": "restbus",
  "output_dir": "string (name of the scenario)",
  "formats": "blf,dbc,json,csv",
  "package_mode": "can" | "ethernet" | "mixed",
  "signal_value_strategy": "calculated" | "raw" | "random" | "hybrid",
  "filter_system": {
    "enabled": boolean,
    "algorithm": "kalman" | "none",
    "domain": "generic | automotive | industrial | energy | aerospace | ...",
    "profile": "maneuver/process profile name"
  },
  "duration_s": float (default 10.0),
  "bus_type": "fd" | "classic" | "xl",
  "channels": integer (1 to 16),
  "nominal_bitrate": 500000,
  "data_bitrate": 2000000,
  "seed": 42,
  "participants": [
    {
      "name": "STRING (e.g. ADAS_DOMAIN, ENGINE_ECU, GATEWAY)",
      "role": "STRING (e.g. domain_controller, sensor, actuator)",
      "channel": integer (0 to channels-1),
      "cycle_ms": integer (e.g. 10, 20, 50, 100),
      "provided_services": ["SERVICE_NAME_A", ...],
      "consumed_services": ["SERVICE_NAME_B", ...],
      "gateway_to_channel": integer (optional, for gateways),
      "health": "nominal" | "degraded" | "faulty" | "offline"
    }
  ]
}

### Guidelines:
- FIRST resolve the simulation setup: package_mode and signal_value_strategy. All topology and message choices must follow this setup.
- `package_mode=mixed` means CAN artifacts plus Ethernet PCAP/PCAPNG artifacts. Use CAN participants/services for restbus routing and Ethernet parameters for parallel network traffic.
- `signal_value_strategy=calculated` means messages are filled with calculated values: time-dependent signals, alive counters, mux state, CRC, ACK/NACK diagnostics, gateway status and optional fault injection.
- Use `filter_system` for physical time-series smoothing. Keep it domain-neutral: Automotive can use Kalman filters for speed, yaw, distance, lane/object signals; other domains can use the same structure with their own profiles.
- Participants with matching services (one provides, another consumes) will be automatically routed by the simulator.
- For gateways, use `gateway_to_channel` to indicate cross-bus routing.
- If the user describes a vehicle system, translate it into realistic nodes and services.
- Treat the supplied project profile as the baseline topology unless the user explicitly asks for another architecture.
- Treat the supplied maneuver profile as behavioral intent: add the required service links, make safety-critical nodes faster, and mark requested failures via `health`.
- Manöver examples: emergency braking needs radar/camera/IMU -> ADAS -> brake/ESC; lane change needs lane model/blind spot -> ADAS -> steering; parking needs ultrasonic -> park assist -> steering/brake.
- Keep service names consistent between providers and consumers so the simulator can derive routes.
- ALWAYS output the JSON inside a triple backtick code block: ```json ... ```.
- Use your thinking process to ensure the network topology and service discovery make sense for the described scenario.
- Ensure `output_dir` is a valid folder name.
"""

def extract_json(text):
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    return None

def query_openai_compatible(
    api_client,
    model,
    prompt,
    profile_context,
    *,
    provider_label,
    max_retries=0,
    timeout_s=60,
    reasoning=True,
):
    last_error = None
    if reasoning:
        budgets = [
            {"max_tokens": 4096, "reasoning_budget": 2048, "temperature": 0.4},
            {"max_tokens": 4096, "reasoning_budget": 1024, "temperature": 0.2},
            {"max_tokens": 2048, "reasoning_budget": 512, "temperature": 0.2},
        ]
    else:
        budgets = [
            {"max_tokens": 2048, "reasoning_budget": None, "temperature": 0.2},
            {"max_tokens": 1536, "reasoning_budget": None, "temperature": 0.1},
        ]
    attempts = max(1, min(max_retries + 1, len(budgets)))
    for attempt in range(attempts):
        budget = budgets[attempt]
        try:
            detail = f", reasoning_budget={budget['reasoning_budget']}" if budget["reasoning_budget"] is not None else ""
            print(
                f"{provider_label} attempt {attempt + 1}/{attempts}: waiting for first response chunk "
                f"(timeout {timeout_s}s{detail})...",
                flush=True,
            )
            kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{prompt}\n\nUse this project and maneuver context as constraints for the JSON request:\n{profile_context}"}
                ],
                "temperature": budget["temperature"],
                "top_p": 0.9,
                "max_tokens": budget["max_tokens"],
                "stream": True,
                "timeout": timeout_s,
            }
            if reasoning:
                kwargs["extra_body"] = {
                    "chat_template_kwargs": {"enable_thinking": True},
                    "reasoning_budget": budget["reasoning_budget"],
                }
            completion = api_client.chat.completions.create(**kwargs)

            full_content = ""
            print("Connected. Thinking/Reasoning:" if reasoning else "Connected. Response:")
            for chunk in completion:
                if not chunk.choices:
                    continue

                reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
                if reasoning:
                    print(reasoning, end="", flush=True)

                content = chunk.choices[0].delta.content
                if content is not None:
                    if not full_content:
                        print("\n\nResponse:")
                    print(content, end="", flush=True)
                    full_content += content
            print()
            return full_content
        except Exception as exc:
            last_error = exc
            status_code = getattr(exc, "status_code", None)
            if status_code is None and hasattr(exc, "response"):
                status_code = getattr(exc.response, "status_code", None)
            retryable = status_code in {408, 429, 500, 502, 503, 504} or status_code is None
            if attempt < attempts - 1 and retryable:
                wait_s = 2 + attempt * 3
                print(f"\n{provider_label} request failed ({exc}). Retry in {wait_s}s with smaller budget.")
                time.sleep(wait_s)
                continue
            raise last_error

def query_nemotron(prompt, profile_context, max_retries=2, timeout_s=60):
    return query_openai_compatible(
        client,
        "nvidia/nemotron-3-ultra-550b-a55b",
        prompt,
        profile_context,
        provider_label="Nemotron",
        max_retries=max_retries,
        timeout_s=timeout_s,
        reasoning=True,
    )

def query_local_ai(prompt, profile_context, max_retries=0, timeout_s=30):
    local_client = OpenAI(base_url=LOCAL_AI_BASE_URL, api_key=LOCAL_AI_API_KEY)
    return query_openai_compatible(
        local_client,
        LOCAL_AI_MODEL,
        prompt,
        profile_context,
        provider_label=f"Local AI ({LOCAL_AI_MODEL})",
        max_retries=max_retries,
        timeout_s=timeout_s,
        reasoning=False,
    )

class StatusBar:
    def __init__(self, enabled=True, width=32):
        self.enabled = enabled
        self.width = width
        self.last_len = 0

    def update(self, percent, message):
        if not self.enabled:
            return
        percent = max(0, min(100, int(percent)))
        filled = round(self.width * percent / 100)
        bar = "#" * filled + "-" * (self.width - filled)
        text = f"\r[{bar}] {message} {percent}%"
        padding = " " * max(0, self.last_len - len(text))
        print(text + padding, end="", flush=True)
        self.last_len = len(text)
        if percent >= 100:
            print()
            self.last_len = 0

    def line(self):
        if self.enabled and self.last_len:
            print()
            self.last_len = 0

def split_services(value):
    if value is None:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]

def ensure_simulation_config_library(path=CONFIG_DB_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS package_modes (
                key TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                formats TEXT NOT NULL,
                eth_bitrates TEXT,
                eth_messages INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signal_value_strategies (
                key TEXT PRIMARY KEY,
                description TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS output_formats (
                kind TEXT NOT NULL,
                format TEXT NOT NULL,
                PRIMARY KEY (kind, format)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS physical_ai_skill_names (
                name TEXT PRIMARY KEY
            )
        """)
        for key, value in DEFAULT_PACKAGE_MODES.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO package_modes
                (key, description, formats, eth_bitrates, eth_messages)
                VALUES (?, ?, ?, ?, ?)
                """,
                (key, value["description"], value["formats"], value.get("eth_bitrates"), value.get("eth_messages")),
            )
        for key, description in DEFAULT_SIGNAL_VALUE_STRATEGIES.items():
            conn.execute(
                "INSERT OR IGNORE INTO signal_value_strategies (key, description) VALUES (?, ?)",
                (key, description),
            )
        for kind, formats in {"can": DEFAULT_CAN_OUTPUT_FORMATS, "ethernet": DEFAULT_ETH_OUTPUT_FORMATS}.items():
            for fmt in formats:
                conn.execute(
                    "INSERT OR IGNORE INTO output_formats (kind, format) VALUES (?, ?)",
                    (kind, fmt),
                )
        for skill_name in DEFAULT_PHYSICAL_AI_SKILL_NAMES:
            conn.execute(
                "INSERT OR IGNORE INTO physical_ai_skill_names (name) VALUES (?)",
                (skill_name,),
            )
    return path

def load_simulation_config_from_library(path=CONFIG_DB_PATH):
    path = Path(path)
    if not path.exists():
        return (
            copy.deepcopy(DEFAULT_PACKAGE_MODES),
            set(DEFAULT_CAN_OUTPUT_FORMATS),
            set(DEFAULT_ETH_OUTPUT_FORMATS),
            copy.deepcopy(DEFAULT_SIGNAL_VALUE_STRATEGIES),
            list(DEFAULT_PHYSICAL_AI_SKILL_NAMES),
        )
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        package_modes = {
            row["key"]: {
                "description": row["description"],
                "formats": row["formats"],
                "eth_bitrates": row["eth_bitrates"],
                "eth_messages": row["eth_messages"],
            }
            for row in conn.execute(
                "SELECT key, description, formats, eth_bitrates, eth_messages FROM package_modes ORDER BY key"
            )
        }
        signal_value_strategies = {
            row["key"]: row["description"]
            for row in conn.execute("SELECT key, description FROM signal_value_strategies ORDER BY key")
        }
        can_formats = {
            row["format"]
            for row in conn.execute("SELECT format FROM output_formats WHERE kind = 'can' ORDER BY format")
        }
        eth_formats = {
            row["format"]
            for row in conn.execute("SELECT format FROM output_formats WHERE kind = 'ethernet' ORDER BY format")
        }
        physical_ai_skill_names = [
            row["name"]
            for row in conn.execute("SELECT name FROM physical_ai_skill_names ORDER BY name")
        ]
    return (
        package_modes or copy.deepcopy(DEFAULT_PACKAGE_MODES),
        can_formats or set(DEFAULT_CAN_OUTPUT_FORMATS),
        eth_formats or set(DEFAULT_ETH_OUTPUT_FORMATS),
        signal_value_strategies or copy.deepcopy(DEFAULT_SIGNAL_VALUE_STRATEGIES),
        physical_ai_skill_names or list(DEFAULT_PHYSICAL_AI_SKILL_NAMES),
    )

def load_runtime_config_from_library():
    global PACKAGE_MODES, CAN_OUTPUT_FORMATS, ETH_OUTPUT_FORMATS, SIGNAL_VALUE_STRATEGIES, PHYSICAL_AI_SKILL_NAMES
    ensure_simulation_config_library()
    (
        PACKAGE_MODES,
        CAN_OUTPUT_FORMATS,
        ETH_OUTPUT_FORMATS,
        SIGNAL_VALUE_STRATEGIES,
        PHYSICAL_AI_SKILL_NAMES,
    ) = load_simulation_config_from_library()

def project_profile_db_path(industry=DEFAULT_PROJECT_INDUSTRY):
    return INDUSTRY_PROFILE_ROOT / sanitize_folder_name(industry) / PROJECT_PROFILE_DB_NAME

def ensure_project_profile_library(industry=DEFAULT_PROJECT_INDUSTRY):
    db_path = project_profile_db_path(industry)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_profiles (
                key TEXT PRIMARY KEY,
                industry TEXT NOT NULL,
                description TEXT NOT NULL,
                bus_type TEXT NOT NULL,
                channels INTEGER NOT NULL,
                duration_s REAL NOT NULL,
                messages INTEGER,
                participants_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for key, profile in DEFAULT_PROJECT_PROFILES.items():
            conn.execute(
                """
                INSERT INTO project_profiles
                (key, industry, description, bus_type, channels, duration_s, messages, participants_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    industry=excluded.industry,
                    description=excluded.description,
                    bus_type=excluded.bus_type,
                    channels=excluded.channels,
                    duration_s=excluded.duration_s,
                    messages=excluded.messages,
                    participants_json=excluded.participants_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    key,
                    industry.lower(),
                    profile["description"],
                    profile["bus_type"],
                    int(profile["channels"]),
                    float(profile["duration_s"]),
                    int(profile["messages"]) if profile.get("messages") is not None else None,
                    json.dumps(profile["participants"], ensure_ascii=False),
                ),
            )
    return db_path

def load_project_profiles_from_library(industry=DEFAULT_PROJECT_INDUSTRY):
    db_path = project_profile_db_path(industry)
    if not db_path.exists():
        return copy.deepcopy(DEFAULT_PROJECT_PROFILES)
    profiles = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT key, description, bus_type, channels, duration_s, messages, participants_json
            FROM project_profiles
            ORDER BY key
            """
        ).fetchall()
        for row in rows:
            try:
                participants = json.loads(row["participants_json"])
            except json.JSONDecodeError:
                participants = []
            profiles[row["key"]] = {
                "description": row["description"],
                "bus_type": row["bus_type"],
                "channels": int(row["channels"]),
                "duration_s": float(row["duration_s"]),
                "messages": int(row["messages"]) if row["messages"] is not None else None,
                "participants": participants,
                "industry": industry,
                "source": str(db_path),
            }
    return profiles or copy.deepcopy(DEFAULT_PROJECT_PROFILES)

def ensure_maneuver_database(path: Union[str, Path] = MANEUVER_DB_PATH) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maneuvers (
                key TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                description TEXT NOT NULL,
                duration_s REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maneuver_keywords (
                maneuver_key TEXT NOT NULL,
                keyword TEXT NOT NULL,
                PRIMARY KEY (maneuver_key, keyword),
                FOREIGN KEY (maneuver_key) REFERENCES maneuvers(key)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maneuver_service_links (
                maneuver_key TEXT NOT NULL,
                sender TEXT NOT NULL,
                service TEXT NOT NULL,
                receiver TEXT NOT NULL,
                PRIMARY KEY (maneuver_key, sender, service, receiver),
                FOREIGN KEY (maneuver_key) REFERENCES maneuvers(key)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maneuver_cycle_overrides (
                maneuver_key TEXT NOT NULL,
                participant TEXT NOT NULL,
                cycle_ms INTEGER NOT NULL,
                PRIMARY KEY (maneuver_key, participant),
                FOREIGN KEY (maneuver_key) REFERENCES maneuvers(key)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maneuver_required_participants (
                maneuver_key TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                channel INTEGER NOT NULL,
                cycle_ms INTEGER NOT NULL,
                provided_services TEXT NOT NULL DEFAULT '',
                consumed_services TEXT NOT NULL DEFAULT '',
                gateway_to_channel INTEGER,
                health TEXT NOT NULL DEFAULT 'nominal',
                PRIMARY KEY (maneuver_key, name),
                FOREIGN KEY (maneuver_key) REFERENCES maneuvers(key)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS physical_ai_workflows (
                key TEXT PRIMARY KEY,
                description TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS physical_ai_workflow_keywords (
                workflow_key TEXT NOT NULL,
                keyword TEXT NOT NULL,
                PRIMARY KEY (workflow_key, keyword),
                FOREIGN KEY (workflow_key) REFERENCES physical_ai_workflows(key)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS physical_ai_workflow_steps (
                workflow_key TEXT NOT NULL,
                step_order INTEGER NOT NULL,
                skill_name TEXT NOT NULL,
                summary TEXT NOT NULL,
                PRIMARY KEY (workflow_key, step_order),
                FOREIGN KEY (workflow_key) REFERENCES physical_ai_workflows(key)
            )
        """)

        for row in DEFAULT_MANEUVER_ROWS:
            conn.execute(
                "INSERT OR IGNORE INTO maneuvers (key, domain, description, duration_s) VALUES (?, ?, ?, ?)",
                (row["key"], row["domain"], row["description"], row["duration_s"]),
            )
            for keyword in row.get("keywords", []):
                conn.execute(
                    "INSERT OR IGNORE INTO maneuver_keywords (maneuver_key, keyword) VALUES (?, ?)",
                    (row["key"], keyword.lower()),
                )
            for sender, service, receiver in row.get("service_links", []):
                conn.execute(
                    "INSERT OR IGNORE INTO maneuver_service_links (maneuver_key, sender, service, receiver) VALUES (?, ?, ?, ?)",
                    (row["key"], sender, service, receiver),
                )
            for participant, cycle_ms in row.get("cycle_overrides", []):
                conn.execute(
                    "INSERT OR IGNORE INTO maneuver_cycle_overrides (maneuver_key, participant, cycle_ms) VALUES (?, ?, ?)",
                    (row["key"], participant, cycle_ms),
                )
            for participant in row.get("required_participants", []):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO maneuver_required_participants
                    (maneuver_key, name, role, channel, cycle_ms, provided_services, consumed_services, gateway_to_channel, health)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (row["key"], *participant),
                )
        for row in DEFAULT_PHYSICAL_AI_WORKFLOWS:
            conn.execute(
                "INSERT OR IGNORE INTO physical_ai_workflows (key, description) VALUES (?, ?)",
                (row["key"], row["description"]),
            )
            for keyword in row.get("keywords", []):
                conn.execute(
                    "INSERT OR IGNORE INTO physical_ai_workflow_keywords (workflow_key, keyword) VALUES (?, ?)",
                    (row["key"], keyword.lower()),
                )
            for step_order, (skill_name, summary) in enumerate(row.get("steps", []), start=1):
                conn.execute(
                    "INSERT OR IGNORE INTO physical_ai_workflow_steps (workflow_key, step_order, skill_name, summary) VALUES (?, ?, ?, ?)",
                    (row["key"], step_order, skill_name, summary),
                )


def load_maneuver_profiles(path: Union[str, Path] = MANEUVER_DB_PATH, domain: str = "automotive") -> Dict[
    str, Dict[str, Union[str, float, Dict, List[Dict]]]]:
    profiles = {}
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        maneuvers = conn.execute(
            "SELECT key, domain, description, duration_s FROM maneuvers WHERE domain = ? ORDER BY key",
            (domain,),
        ).fetchall()
        for row in maneuvers:
            key = row["key"]
            profiles[key] = {
                "domain": row["domain"],
                "description": row["description"],
                "duration_s": row["duration_s"],
                "keywords": [
                    item["keyword"]
                    for item in conn.execute(
                        "SELECT keyword FROM maneuver_keywords WHERE maneuver_key = ? ORDER BY keyword",
                        (key,),
                    )
                ],
                "service_links": [
                    (item["sender"], item["service"], item["receiver"])
                    for item in conn.execute(
                        "SELECT sender, service, receiver FROM maneuver_service_links WHERE maneuver_key = ? ORDER BY rowid",
                        (key,),
                    )
                ],
                "cycle_overrides": {
                    item["participant"]: item["cycle_ms"]
                    for item in conn.execute(
                        "SELECT participant, cycle_ms FROM maneuver_cycle_overrides WHERE maneuver_key = ?",
                        (key,),
                    )
                },
                "required_participants": [
                    {
                        "name": item["name"],
                        "role": item["role"],
                        "channel": item["channel"],
                        "cycle_ms": item["cycle_ms"],
                        "provided_services": split_services(item["provided_services"]),
                        "consumed_services": split_services(item["consumed_services"]),
                        "gateway_to_channel": item["gateway_to_channel"],
                        "health": item["health"],
                    }
                    for item in conn.execute(
                        """
                        SELECT name, role, channel, cycle_ms, provided_services, consumed_services, gateway_to_channel, health
                        FROM maneuver_required_participants
                        WHERE maneuver_key = ?
                        ORDER BY rowid
                        """,
                        (key,),
                    )
                ],
            }
    return profiles

def load_physical_ai_workflows(path=MANEUVER_DB_PATH):
    workflows = {}
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT key, description FROM physical_ai_workflows ORDER BY key").fetchall()
        for row in rows:
            key = row["key"]
            workflows[key] = {
                "description": row["description"],
                "keywords": [
                    item["keyword"]
                    for item in conn.execute(
                        "SELECT keyword FROM physical_ai_workflow_keywords WHERE workflow_key = ? ORDER BY keyword",
                        (key,),
                    )
                ],
                "steps": [
                    {"skill": item["skill_name"], "summary": item["summary"]}
                    for item in conn.execute(
                        "SELECT skill_name, summary FROM physical_ai_workflow_steps WHERE workflow_key = ? ORDER BY step_order",
                        (key,),
                    )
                ],
            }
    return workflows

def ensure_profile_cache():
    global PROJECT_PROFILES, MANEUVER_PROFILES, PHYSICAL_AI_WORKFLOWS
    load_runtime_config_from_library()
    if not PROJECT_PROFILES:
        ensure_project_profile_library()
        PROJECT_PROFILES = load_project_profiles_from_library()
    if not MANEUVER_PROFILES or not PHYSICAL_AI_WORKFLOWS:
        ensure_maneuver_database()
    if not MANEUVER_PROFILES:
        MANEUVER_PROFILES = load_maneuver_profiles()
    if not PHYSICAL_AI_WORKFLOWS:
        PHYSICAL_AI_WORKFLOWS = load_physical_ai_workflows()

def skill_search_roots():
    home = Path.home()
    upstream_root = Path(
        os.getenv("NUREC_SKILLS_UPSTREAM_ROOT")
        or os.getenv("PHYSICAL_AI_SKILL_HUB_UPSTREAM_ROOT")
        or home / ".physical-ai-skill-hub" / "upstreams" / "nurec-skills"
    )
    return [
        Path(".agents/skills"),
        Path(".claude/skills"),
        Path(".cursor/skills"),
        home / ".agents" / "skills",
        home / ".cursor" / "skills",
        upstream_root / ".agents" / "skills",
        upstream_root / "skills",
    ]

def discover_skill_paths(skill_names=PHYSICAL_AI_SKILL_NAMES):
    found = {}
    for root in skill_search_roots():
        for skill_name in skill_names:
            skill_path = root / skill_name / "SKILL.md"
            if skill_path.exists():
                found[skill_name] = str(skill_path.resolve())
    return found

def http_json(url, headers=None, timeout=20):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def check_huggingface_access(check_dataset=True):
    token = os.getenv("HF_TOKEN")
    if not token:
        return {
            "token": "missing",
            "account": None,
            "physical_ai_dataset": "not_checked",
        }
    result = {
        "token": "set",
        "account": "not_checked",
        "physical_ai_dataset": "not_checked",
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        account = http_json("https://huggingface.co/api/whoami-v2", headers=headers)
        result["account"] = "valid"
        result["account_name"] = account.get("name") or account.get("fullname") or "detected"
    except urllib.error.HTTPError as exc:
        result["account"] = f"denied_http_{exc.code}"
    except Exception as exc:
        result["account"] = f"check_failed_{type(exc).__name__}"

    if check_dataset:
        try:
            dataset = http_json(
                "https://huggingface.co/api/datasets/nvidia/PhysicalAI-Autonomous-Vehicles-NuRec",
                headers=headers,
            )
            result["physical_ai_dataset"] = "accessible"
            result["physical_ai_dataset_id"] = dataset.get("id", "nvidia/PhysicalAI-Autonomous-Vehicles-NuRec")
        except urllib.error.HTTPError as exc:
            result["physical_ai_dataset"] = f"denied_http_{exc.code}"
        except Exception as exc:
            result["physical_ai_dataset"] = f"check_failed_{type(exc).__name__}"
    return result

def check_docker():
    docker_path = shutil.which("docker")
    if not docker_path:
        return {"available": False, "path": None, "version": None}
    try:
        completed = subprocess.run(
            ["docker", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        version = completed.stdout.strip() or completed.stderr.strip()
    except Exception as exc:
        version = f"check_failed_{type(exc).__name__}"
    return {"available": True, "path": docker_path, "version": version}

def check_ngc_access(login_ngc=False):
    token = os.getenv("NGC_API_KEY")
    result = {
        "token": "set" if token else "missing",
        "docker_login": "not_checked",
    }
    if not token:
        return result
    if not login_ngc:
        result["docker_login"] = "not_checked_use_--login-ngc"
        return result
    if not shutil.which("docker"):
        result["docker_login"] = "docker_missing"
        return result
    try:
        completed = subprocess.run(
            ["docker", "login", "nvcr.io", "-u", "$oauthtoken", "--password-stdin"],
            input=token,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if completed.returncode == 0:
            result["docker_login"] = "succeeded"
        else:
            output = f"{completed.stdout}\n{completed.stderr}".lower()
            if "unauthorized" in output or "denied" in output:
                result["docker_login"] = "denied"
            else:
                result["docker_login"] = f"failed_exit_{completed.returncode}"
    except Exception as exc:
        result["docker_login"] = f"check_failed_{type(exc).__name__}"
    return result

def physical_ai_readiness(check_network=False, login_ngc=False, status=None):
    if status:
        status.update(35, "Pruefe Physical-AI Skill-Bodies")
    skill_paths = discover_skill_paths()
    missing_skills = [skill for skill in PHYSICAL_AI_SKILL_NAMES if skill not in skill_paths]
    if status:
        status.update(45, "Pruefe Secrets")
    environment = {
        "NGC_API_KEY": "set" if os.getenv("NGC_API_KEY") else "missing",
        "HF_TOKEN": "set" if os.getenv("HF_TOKEN") else "missing",
    }
    if status:
        status.update(55, "Pruefe Docker")
    docker = check_docker()
    if status and check_network:
        status.update(68, "Pruefe Hugging Face Konto")
    huggingface = check_huggingface_access(check_dataset=True) if check_network else "not_checked"
    if status and check_network:
        status.update(78, "Pruefe PhysicalAI Dataset")
    if status and login_ngc:
        status.update(88, "Pruefe NGC Docker Login")
    ngc = check_ngc_access(login_ngc=login_ngc) if (check_network or login_ngc) else "not_checked"
    if status:
        status.update(96, "Bewerte Physical-AI Bereitschaft")
    readiness = {
        "skills": {
            "found": skill_paths,
            "missing": missing_skills,
        },
        "environment": environment,
        "docker": docker,
        "huggingface": huggingface,
        "ngc": ngc,
    }
    readiness["ready_for_router_workflows"] = (
        not missing_skills
        and environment["NGC_API_KEY"] == "set"
        and environment["HF_TOKEN"] == "set"
        and readiness["docker"]["available"]
    )
    return readiness

def print_physical_ai_readiness(readiness):
    print("Physical AI / NuRec readiness:")
    print(f"  Skill bodies: {'ok' if not readiness['skills']['missing'] else 'missing'}")
    if readiness["skills"]["missing"]:
        print(f"  Missing skills: {', '.join(readiness['skills']['missing'])}")
    print(f"  NGC_API_KEY: {readiness['environment']['NGC_API_KEY']}")
    print(f"  HF_TOKEN: {readiness['environment']['HF_TOKEN']}")
    print(f"  Docker: {'available' if readiness['docker']['available'] else 'missing'}")
    if readiness["docker"]["version"]:
        print(f"  Docker version: {readiness['docker']['version']}")
    if isinstance(readiness["huggingface"], dict):
        print(f"  Hugging Face account: {readiness['huggingface']['account']}")
        print(f"  PhysicalAI dataset: {readiness['huggingface']['physical_ai_dataset']}")
    else:
        print("  Hugging Face account: not_checked")
    if isinstance(readiness["ngc"], dict):
        print(f"  NGC Docker login: {readiness['ngc']['docker_login']}")
    else:
        print("  NGC Docker login: not_checked")
    print(f"  Ready for router workflows: {readiness['ready_for_router_workflows']}")

def infer_domain(prompt, selected):
    if selected and selected != "auto":
        return selected
    text = prompt.lower()
    physical_keywords = [
        "nurec", "neural reconstruction", "nre", "ncore", "usdz", "3dgut", "3dgrt",
        "sensor sim", "serve-grpc", "render-grpc", "physicalai", "physical ai",
        "novel view", "diffusionharmonizer", "asset harvester",
    ]
    if any(keyword in text for keyword in physical_keywords):
        return "physical_ai"
    return "automotive"

def infer_physical_ai_workflow(prompt, selected):
    ensure_profile_cache()
    if selected and selected != "auto":
        return selected
    text = prompt.lower()
    for key, workflow in PHYSICAL_AI_WORKFLOWS.items():
        if any(keyword in text for keyword in workflow.get("keywords", [])):
            return key
    return "own_recording_to_usdz"

def infer_package_mode(prompt, selected):
    if selected and selected != "auto":
        return selected
    text = prompt.lower()
    if any(word in text for word in ["mixed", "gemischt", "can + ethernet", "can und ethernet", "ethernet und can"]):
        return "mixed"
    if any(word in text for word in ["ethernet", "pcap", "pcapng", "some/ip", "someip"]):
        return "ethernet"
    return "can"

def infer_signal_value_strategy(prompt, selected):
    if selected and selected != "auto":
        return selected
    text = prompt.lower()
    if any(word in text for word in ["raw", "roh", "payload roh"]):
        return "raw"
    if any(word in text for word in ["random", "zufall", "zufällig", "randomisiert"]):
        return "random"
    if any(word in text for word in ["hybrid", "rauschen", "noise", "störung", "stoerung"]):
        return "hybrid"
    return "calculated"

def choose_interactive_option(title, options, default_key):
    print(title)
    for key, label in options.items():
        suffix = " (Default)" if key == default_key else ""
        print(f"{key}. {label}{suffix}")
    allowed = "/".join(options)
    while True:
        selected = input(f"Auswahl [{allowed}, Enter = {default_key}]: ").strip().lower()
        if not selected:
            return default_key
        if selected in options:
            return selected
        print(f"Ungueltige Eingabe. Erlaubt: {allowed}")

def choose_interactive_int(title, default_value, minimum, maximum):
    while True:
        selected = input(f"{title} [{minimum}-{maximum}, Enter = {default_value}]: ").strip()
        if not selected:
            return default_value
        if selected.isdigit() and minimum <= int(selected) <= maximum:
            return int(selected)
        print(f"Ungueltige Eingabe. Bitte Zahl von {minimum} bis {maximum} eingeben.")

def choose_interactive_bool(title, default_value=True):
    default_text = "J" if default_value else "N"
    while True:
        selected = input(f"{title} [J/N, Enter = {default_text}]: ").strip().lower()
        if not selected:
            return default_value
        if selected in {"j", "ja", "y", "yes"}:
            return True
        if selected in {"n", "nein", "no"}:
            return False
        print("Ungueltige Eingabe. Bitte J oder N eingeben.")

def ask_interactive_simulation_setup(args):
    print("Simulationsumfang zuerst festlegen:")
    if args.package_mode == "auto":
        selected = choose_interactive_option(
            "Welche Bus-/Trace-Umgebung soll erzeugt werden?",
            {
                "1": "CAN/CAN-FD/CAN-XL",
                "2": "Ethernet PCAP/PCAPNG",
                "3": "Mixed: CAN + Ethernet",
            },
            "1",
        )
        args.package_mode = {"1": "can", "2": "ethernet", "3": "mixed"}[selected]
    if args.signal_values == "auto":
        selected = choose_interactive_option(
            "Wie sollen Botschaftswerte befuellt werden?",
            {
                "1": "Berechnete Werte mit Counter, CRC, Zeitverlauf und Fehlerlogik",
                "2": "Rohdatenorientiert",
                "3": "Seeded Random innerhalb der Signalgrenzen",
                "4": "Hybrid: berechnet plus Rauschen/Stoerungen",
            },
            "1",
        )
        args.signal_values = {"1": "calculated", "2": "raw", "3": "random", "4": "hybrid"}[selected]
    if args.channels is None and args.package_mode in {"can", "mixed"}:
        args.channels = choose_interactive_int("Wie viele CAN-Kanaele?", 4, 1, 16)
    if args.eth_messages is None and args.package_mode in {"ethernet", "mixed"}:
        args.eth_messages = choose_interactive_int("Wie viele Ethernet-Kommunikationsstroeme?", 4, 1, 500)

def apply_setup_overrides(request_data, args):
    if getattr(args, "channels", None) is not None:
        request_data["channels"] = int(args.channels)
    if getattr(args, "eth_messages", None) is not None:
        request_data["eth_messages"] = int(args.eth_messages)
    return request_data

def parse_format_tokens(value):
    if isinstance(value, (list, tuple, set)):
        raw_tokens = value
    else:
        raw_tokens = str(value or "").split(",")
    tokens = []
    for token in raw_tokens:
        normalized = str(token).strip().lower()
        if normalized and normalized not in tokens:
            tokens.append(normalized)
    return tokens

def expand_format_tokens(tokens):
    expanded = set()
    for token in tokens:
        if token == "can-all":
            expanded.update(CAN_OUTPUT_FORMATS)
        elif token == "eth-all":
            expanded.update(ETH_OUTPUT_FORMATS)
        elif token == "all":
            expanded.update(CAN_OUTPUT_FORMATS)
            expanded.update(ETH_OUTPUT_FORMATS)
        else:
            expanded.add(token)
    return expanded

def validate_request_consistency(request_data):
    errors = []
    warnings = []
    package_mode = request_data.get("package_mode")
    if package_mode not in PACKAGE_MODES:
        errors.append(f"unknown package_mode: {package_mode}")

    format_tokens = parse_format_tokens(request_data.get("formats"))
    expanded_formats = expand_format_tokens(format_tokens)
    has_can = bool(expanded_formats & CAN_OUTPUT_FORMATS)
    has_eth = bool(expanded_formats & ETH_OUTPUT_FORMATS)

    if package_mode == "can" and has_eth:
        errors.append("package_mode=can must not contain Ethernet formats")
    elif package_mode == "can" and not has_can:
        errors.append("package_mode=can requires at least one CAN format")
    elif package_mode == "ethernet" and has_can:
        errors.append("package_mode=ethernet must not contain CAN formats")
    elif package_mode == "ethernet" and not has_eth:
        errors.append("package_mode=ethernet requires pcap or pcapng")
    elif package_mode == "mixed" and not (has_can and has_eth):
        errors.append("package_mode=mixed requires CAN and Ethernet formats")

    if package_mode in {"can", "mixed"}:
        try:
            channels = int(request_data.get("channels"))
            if channels < 1 or channels > 16:
                errors.append("channels must be between 1 and 16")
        except (TypeError, ValueError):
            errors.append("channels must be an integer between 1 and 16")

    if package_mode in {"ethernet", "mixed"}:
        try:
            eth_messages = int(request_data.get("eth_messages"))
            if eth_messages < 1:
                errors.append("eth_messages must be at least 1")
        except (TypeError, ValueError):
            errors.append("eth_messages must be an integer")
        if not request_data.get("eth_bitrate") and not request_data.get("eth_bitrates"):
            errors.append("ethernet package modes require eth_bitrate or eth_bitrates")

    strategy = request_data.get("signal_value_strategy")
    if strategy not in SIGNAL_VALUE_STRATEGIES:
        errors.append(f"unknown signal_value_strategy: {strategy}")
    if strategy == "calculated":
        policy = request_data.get("message_value_policy")
        if not isinstance(policy, dict):
            errors.append("calculated signal values require message_value_policy")
        else:
            for key in ["counter", "crc", "time", "faults"]:
                if key not in policy:
                    errors.append(f"message_value_policy missing {key}")

    participants = request_data.get("participants")
    if package_mode in {"can", "mixed"} and not isinstance(participants, list):
        errors.append("CAN package modes require a participants list")
    elif isinstance(participants, list):
        service_providers = set()
        service_consumers = set()
        for participant in participants:
            service_providers.update(participant.get("provided_services") or [])
            service_consumers.update(participant.get("consumed_services") or [])
        unresolved = sorted(service_consumers - service_providers)
        if unresolved:
            warnings.append(f"consumed services without provider: {', '.join(unresolved[:8])}")

    request_data["consistency"] = {
        "status": "error" if errors else "ok",
        "package_mode": package_mode,
        "formats": format_tokens,
        "can_enabled": has_can,
        "ethernet_enabled": has_eth,
        "errors": errors,
        "warnings": warnings,
    }
    if errors:
        raise ValueError("Request consistency failed: " + "; ".join(errors))
    return request_data

def request_library_destination(request_data, source_path):
    source_path = Path(source_path)
    schema = request_data.get("schema")
    if schema == "can-simulator.physical-ai-workflow-request.v1":
        workflow = sanitize_folder_name(request_data.get("workflow") or "generic")
        kind = "Checks" if re.search(r"check|readiness|install|token|preinstall|final", source_path.name, re.IGNORECASE) else "Workflows"
        return LIB_ROOT / "PhysicalAI" / kind / workflow / source_path.name
    if schema == SCHEMA:
        scenario = request_data.get("scenario") if isinstance(request_data.get("scenario"), dict) else {}
        project = sanitize_folder_name(scenario.get("project_profile") or "generic_project")
        maneuver = sanitize_folder_name(scenario.get("maneuver_profile") or "generic")
        mode = sanitize_folder_name(request_data.get("package_mode") or "legacy")
        domain = sanitize_folder_name(scenario.get("domain") or DEFAULT_PROJECT_INDUSTRY)
        return LIB_ROOT / "Industries" / domain / "Requests" / project / maneuver / mode / source_path.name
    return LIB_ROOT / "Samples" / "JsonUnknown" / source_path.name

def archive_request_to_library(request_data, source_path):
    source_path = Path(source_path).resolve()
    destination = request_library_destination(request_data, source_path).resolve()
    try:
        source_path.relative_to(LIB_ROOT.resolve())
        return source_path
    except ValueError:
        pass
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source_path != destination:
        shutil.copy2(source_path, destination)
    return destination

def should_write_request_directly_to_library(path):
    path = Path(path)
    return path.parent in {Path("."), Path("")} and path.name.startswith("generated_") and path.suffix.lower() == ".json"

def write_request_json(path, request_data):
    path = Path(path)
    write_path = request_library_destination(request_data, path) if should_write_request_directly_to_library(path) else path
    write_path.parent.mkdir(parents=True, exist_ok=True)
    with open(write_path, "w", encoding="utf-8") as f:
        json.dump(request_data, f, indent=2)
    return archive_request_to_library(request_data, write_path)

def prompt_tokens(value):
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9äöüÄÖÜß_+-]+", str(value or "").lower())
        if len(token) >= 3
    }

def request_search_text(request_data):
    parts = []
    scenario = request_data.get("scenario") if isinstance(request_data.get("scenario"), dict) else {}
    parts.extend([
        request_data.get("output_dir"),
        request_data.get("package_mode"),
        request_data.get("signal_value_strategy"),
        scenario.get("project_profile"),
        scenario.get("maneuver_profile"),
        scenario.get("description"),
    ])
    for participant in request_data.get("participants") or []:
        parts.append(participant.get("name"))
        parts.append(participant.get("role"))
        parts.extend(participant.get("provided_services") or [])
        parts.extend(participant.get("consumed_services") or [])
    return " ".join(str(part) for part in parts if part)

def library_candidate_score(request_data, prompt, project_key, maneuver_key, setup):
    if request_data.get("schema") != SCHEMA:
        return 0
    scenario = request_data.get("scenario") if isinstance(request_data.get("scenario"), dict) else {}
    score = 0
    if scenario.get("project_profile") == project_key:
        score += 35
    if maneuver_key and scenario.get("maneuver_profile") == maneuver_key:
        score += 45
    elif not maneuver_key and scenario.get("maneuver_profile") in {None, "", "generic"}:
        score += 10
    if request_data.get("package_mode") == setup["package_mode"]:
        score += 20
    query_tokens = prompt_tokens(prompt)
    candidate_tokens = prompt_tokens(request_search_text(request_data))
    score += min(20, len(query_tokens & candidate_tokens) * 4)
    return min(100, score)

def find_library_request(prompt, project_key, maneuver_key, setup, min_score=70):
    request_roots = [LIB_ROOT / "Industries", LIB_ROOT / "Automotiv" / "Requests"]
    best = None
    for request_root in request_roots:
        if not request_root.exists():
            continue
        for path in request_root.rglob("*.json"):
            try:
                request_data = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            score = library_candidate_score(request_data, prompt, project_key, maneuver_key, setup)
            if score >= min_score and (best is None or score > best["score"]):
                best = {"path": path, "request": request_data, "score": score}
    return best

def request_from_library_match(match, prompt, project_key, maneuver_key, setup):
    request_data = copy.deepcopy(match["request"])
    request_data["output_dir"] = f"generated_{project_key}_{maneuver_key or 'generic'}"
    request_data["library_source"] = {
        "path": str(match["path"]),
        "score": match["score"],
    }
    request_data = normalize_request(request_data, prompt, project_key, maneuver_key, setup)
    request_data["generation_source"] = {
        "type": "library",
        "path": str(match["path"]),
        "score": match["score"],
    }
    return request_data

def request_from_model_response(full_content, prompt, project_key, maneuver_key, setup):
    json_str = extract_json(full_content)
    if not json_str:
        raise ValueError("No JSON block found in model response")
    request_data = json.loads(json_str)
    return normalize_request(request_data, prompt, project_key, maneuver_key, setup)

def print_router_header(args, project_key, maneuver_key, setup):
    print("KI-Router:")
    print(f"  Modus: {args.ai_mode}")
    print(f"  Paket: {setup['package_mode']}")
    print(f"  Werte: {setup['signal_value_strategy']}")
    print(f"  Projektprofil: {project_key}")
    print(f"  Manoeverprofil: {maneuver_key or 'generic'}")
    print("  Reihenfolge: Library -> lokale Profile -> lokale KI -> Nemotron")

def print_router_decision(decision, reason, source=None, score=None):
    print(f"KI-Router Entscheidung: {decision}")
    print(f"  Grund: {reason}")
    if score is not None:
        print(f"  Confidence: {score}%")
    if source is not None:
        print(f"  Quelle: {source}")

def project_profile_industry(project_key, profile=None):
    selected = profile if isinstance(profile, dict) else PROJECT_PROFILES.get(project_key, {})
    if project_key in DEFAULT_PROJECT_PROFILES:
        return "Automotive"
    return selected.get("industry") or DEFAULT_PROJECT_INDUSTRY


def industry_context(industry=None, request_data=None, project_key=None):
    fallback = project_profile_industry(project_key) if project_key else DEFAULT_PROJECT_INDUSTRY
    if request_data is not None:
        return IndustryContext.from_request(
            request_data,
            fallback=industry or fallback,
            root=INDUSTRY_PROFILE_ROOT,
        )
    return IndustryContext.resolve(industry or fallback, root=INDUSTRY_PROFILE_ROOT)


def ensure_simulation_memory_database(industry=DEFAULT_PROJECT_INDUSTRY):
    context = industry_context(industry)
    service = IndustryKnowledgeService(context)
    service.ensure()
    return service.memory.path

def utc_now_text():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def read_json_if_exists(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None

def memory_candidate_score(row, prompt, project_key, maneuver_key, setup):
    score = 0
    if row["project_profile"] == project_key:
        score += 30
    if maneuver_key and row["maneuver_profile"] == maneuver_key:
        score += 35
    elif not maneuver_key and row["maneuver_profile"] in {"", "generic"}:
        score += 10
    if row["package_mode"] == setup["package_mode"]:
        score += 15
    if row["signal_value_strategy"] == setup["signal_value_strategy"]:
        score += 10
    score += min(10, len(prompt_tokens(prompt) & prompt_tokens(row["prompt"])) * 2)
    return min(100, score)

def find_simulation_memory(
    prompt,
    project_key,
    maneuver_key,
    setup,
    limit=3,
    min_score=55,
    industry=None,
):
    context = industry_context(industry, project_key=project_key)
    rows = IndustryKnowledgeService(context).memory.recent(limit=200)
    scored = []
    for row in rows:
        item = dict(row)
        score = memory_candidate_score(item, prompt, project_key, maneuver_key, setup)
        if score >= min_score:
            item["score"] = score
            scored.append(item)
    scored.sort(key=lambda item: (item["score"], item["id"]), reverse=True)
    return scored[:limit]

def print_memory_context(memory_matches):
    if not memory_matches:
        print("Learning-Memory: keine passenden frueheren Simulationen gefunden")
        return
    print(f"Learning-Memory: {len(memory_matches)} passende fruehere Simulation(en) gefunden")
    for item in memory_matches:
        print(
            f"  #{item['id']} Score {item['score']}% | {item['created_utc']} | "
            f"{item['project_profile']}/{item['maneuver_profile']} | Trace: {item.get('trace_dir') or 'n/a'}"
        )

def attach_learning_context(request_data, memory_matches):
    if not memory_matches:
        return request_data
    request_data["learning_context"] = [
        {
            "memory_id": item["id"],
            "score": item["score"],
            "created_utc": item["created_utc"],
            "prompt": item["prompt"],
            "trace_dir": item.get("trace_dir"),
            "formats": item.get("formats"),
            "duration_s": item.get("duration_s"),
            "can_frames": item.get("can_frames"),
            "ethernet_frames": item.get("ethernet_frames"),
            "plausibility_score": item.get("plausibility_score"),
        }
        for item in memory_matches
    ]
    return request_data

def estimate_plausibility_score(manifest, interface):
    score = 70
    warnings = []
    if isinstance(manifest, dict):
        warnings.extend(manifest.get("warnings") or [])
        if manifest.get("can_enabled") and manifest.get("can_frames", 0) == 0:
            score -= 25
        if manifest.get("ethernet_enabled") and manifest.get("ethernet_frames", 0) == 0:
            score -= 15
        if manifest.get("duration_s"):
            score += 5
        if manifest.get("formats"):
            score += 5
    if isinstance(interface, dict):
        if interface.get("restbus"):
            score += 10
        warnings.extend(interface.get("warnings") or [])
    score -= min(30, len(warnings) * 5)
    return max(0, min(100, score))

def record_simulation_learning(request_path, request_data, industry=None):
    scenario = request_data.get("scenario") if isinstance(request_data.get("scenario"), dict) else {}
    context = industry_context(
        industry,
        request_data=request_data,
        project_key=scenario.get("project_profile"),
    )
    service = IndustryKnowledgeService(context)
    service.ensure()
    trace_dir = Path(str(request_data.get("output_dir") or "")).resolve()
    manifest = read_json_if_exists(trace_dir / "generation_manifest.json")
    interface = read_json_if_exists(trace_dir / "simulation_interface.json")
    generation_source = request_data.get("generation_source") if isinstance(request_data.get("generation_source"), dict) else {}
    manifest_dict = manifest if isinstance(manifest, dict) else {}
    interface_dict = interface if isinstance(interface, dict) else {}
    warnings = (manifest_dict.get("warnings") or []) + (interface_dict.get("warnings") or [])
    restbus = interface_dict.get("restbus") if isinstance(interface_dict.get("restbus"), dict) else {}
    memory_id = service.memory.insert(
        {
            "created_utc": utc_now_text(),
            "prompt": scenario.get("description") or "",
            "project_profile": scenario.get("project_profile") or "generic_project",
            "maneuver_profile": scenario.get("maneuver_profile") or "generic",
            "package_mode": request_data.get("package_mode") or "legacy",
            "signal_value_strategy": request_data.get("signal_value_strategy") or "calculated",
            "generation_source_type": generation_source.get("type"),
            "request_path": str(Path(request_path).resolve()),
            "trace_dir": str(trace_dir),
            "formats": ",".join(manifest_dict.get("formats") or []),
            "duration_s": manifest_dict.get("duration_s") or interface_dict.get("duration_s"),
            "can_frames": manifest_dict.get("can_frames") or restbus.get("can_frames"),
            "ethernet_frames": manifest_dict.get("ethernet_frames"),
            "warnings_count": len(warnings),
            "plausibility_score": estimate_plausibility_score(manifest, interface),
            "manifest_json": json.dumps(manifest, indent=2, default=str) if manifest is not None else None,
            "interface_json": json.dumps(interface, indent=2, default=str) if interface is not None else None,
        }
    )
    service.graph.record_simulation(
        memory_id,
        request_data,
        manifest=manifest_dict,
        interface=interface_dict,
    )
    print(f"Learning-Memory: Simulation #{memory_id} gespeichert in {service.memory.path}")
    print(f"Knowledge-Graph: aktualisiert in {service.graph.path}")
    print(f"Learning-Memory: Trace {trace_dir}")
    return memory_id

def build_simulation_setup(prompt, package_mode, signal_value_strategy):
    package = PACKAGE_MODES[package_mode]
    return {
        "package_mode": package_mode,
        "package_description": package["description"],
        "signal_value_strategy": signal_value_strategy,
        "signal_value_description": SIGNAL_VALUE_STRATEGIES[signal_value_strategy],
        "message_value_policy": {
            "counter": "alive counters are calculated per frame and cycle",
            "crc": "CRC is calculated after payload packing",
            "time": "signal values are functions of timestamp, frame id, cycle and signal index",
            "faults": "configured fault injection may alter CRC, counter, DLC and timing",
            "filtering": "optional domain-aware Kalman smoothing is applied to physical-looking time-series signals",
        },
        "filter_system": {
            "enabled": signal_value_strategy in {"calculated", "hybrid"},
            "algorithm": "kalman",
            "domain": "generic",
            "profile": "generic",
        },
    }

def apply_simulation_setup(request_data, setup):
    package_mode = setup["package_mode"]
    package = PACKAGE_MODES[package_mode]
    request_data["package_mode"] = package_mode
    request_data["signal_value_strategy"] = setup["signal_value_strategy"]
    request_data["message_value_policy"] = setup["message_value_policy"]
    request_data["filter_system"] = copy.deepcopy(setup["filter_system"])
    request_data["formats"] = package["formats"]
    if setup.get("channels") is not None:
        request_data["channels"] = int(setup["channels"])
    if package_mode in {"ethernet", "mixed"}:
        request_data["eth_bitrate"] = int(setup.get("eth_bitrate") or 1_000_000_000)
        request_data["eth_bitrates"] = str(setup.get("eth_bitrates") or package["eth_bitrates"])
        request_data["eth_messages"] = int(setup.get("eth_messages") or package["eth_messages"])
    else:
        request_data.pop("eth_bitrate", None)
        request_data.pop("eth_bitrates", None)
        request_data.pop("eth_messages", None)
    return request_data

def service_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = re.split(r"[,;|\n]+", value)
    elif isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = [value]
    services = []
    for item in raw_values:
        service = re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(item or "").strip()).strip("_")
        if service and service not in services:
            services.append(service.upper())
    return services

def import_domain_defaults(industry, package_mode):
    key = str(industry or "automotive").strip().lower()
    defaults = {
        "automotive": ("fd", 5, 120, 20.0),
        "industrial": ("fd", 4, 80, 30.0),
        "robotics": ("mixed", 4, 100, 20.0),
        "medical": ("fd", 3, 60, 30.0),
        "building": ("fd", 3, 60, 30.0),
        "energy": ("fd", 4, 80, 30.0),
        "aerospace": ("fd", 5, 120, 20.0),
        "rail": ("fd", 5, 120, 30.0),
        "maritime": ("mixed", 4, 80, 30.0),
    }
    bus_type, channels, messages, duration_s = defaults.get(key, ("fd", 4, 80, 20.0))
    if package_mode == "ethernet":
        bus_type = "ethernet"
    elif package_mode == "mixed":
        bus_type = "mixed"
    return {
        "bus_type": bus_type,
        "channels": channels,
        "messages": messages,
        "duration_s": duration_s,
    }

def normalize_import_participant(raw_participant, index, channel_count):
    if isinstance(raw_participant, str):
        raw_participant = {"name": raw_participant}
    if not isinstance(raw_participant, dict):
        raise ValueError(f"participants[{index}] must be an object or string")
    name = raw_participant.get("name") or raw_participant.get("id") or raw_participant.get("ecu")
    if not name:
        name = f"NODE_{index + 1}"
    raw_signals = raw_participant.get("signals")
    provided_signal_alias = None if contains_external_signal_records(raw_signals) else raw_signals
    participant = {
        "name": sanitize_folder_name(name).upper(),
        "role": str(raw_participant.get("role") or raw_participant.get("type") or "ecu").strip().lower(),
        "channel": int(raw_participant.get("channel", index % max(1, channel_count))),
        "cycle_ms": int(raw_participant.get("cycle_ms") or raw_participant.get("period_ms") or raw_participant.get("cycle") or 20),
        "provided_services": service_list(
            raw_participant.get("provided_services")
            or raw_participant.get("publishes")
            or provided_signal_alias
            or raw_participant.get("outputs")
        ),
        "consumed_services": service_list(
            raw_participant.get("consumed_services")
            or raw_participant.get("subscribes")
            or raw_participant.get("inputs")
            or raw_participant.get("commands")
        ),
        "health": str(raw_participant.get("health") or "nominal").strip().lower(),
    }
    external_signals = external_signal_records(raw_signals or raw_participant.get("signal_definitions") or raw_participant.get("message_signals"))
    if external_signals:
        participant["signals"] = external_signals
        participant["signal_source"] = str(raw_participant.get("signal_source") or "external")
    if participant["channel"] < 0:
        participant["channel"] = 0
    participant["channel"] = participant["channel"] % max(1, channel_count)
    if raw_participant.get("gateway_to_channel") is not None:
        participant["gateway_to_channel"] = int(raw_participant["gateway_to_channel"]) % max(1, channel_count)
    return participant

def add_import_gateway_if_needed(participants, channel_count):
    channels = {int(item.get("channel", 0)) for item in participants}
    has_gateway = any("gateway" in str(item.get("role", "")).lower() or "GATEWAY" in item.get("name", "") for item in participants)
    if len(channels) < 2 or has_gateway:
        return
    gateway = {
        "name": "INTEGRATION_GATEWAY",
        "role": "gateway",
        "channel": 0,
        "cycle_ms": 50,
        "provided_services": ["ROUTING_STATUS", "SYNC_TIME"],
        "consumed_services": [],
        "gateway_to_channel": min(1, max(0, channel_count - 1)),
        "health": "nominal",
    }
    for participant in participants:
        if int(participant.get("channel", 0)) != 0:
            add_unique(gateway["consumed_services"], "ROUTING_STATUS")
            add_unique(participant.setdefault("consumed_services", []), "SYNC_TIME")
    participants.append(gateway)

def normalize_imported_profile(import_data, import_path=None, industry_override=None, project_key_override=None):
    if not isinstance(import_data, dict):
        raise ValueError("Import file must contain a JSON object")
    if import_data.get("schema") == SCHEMA:
        request_data = copy.deepcopy(import_data)
        request_data.setdefault("generation_source", {"type": "imported_simulation_config", "path": str(import_path or "")})
        return request_data, None

    industry = industry_override or import_data.get("industry") or import_data.get("domain") or "Generic"
    project_key = project_key_override or import_data.get("project_key") or import_data.get("key") or import_data.get("name")
    if not project_key:
        project_key = Path(import_path).stem if import_path else "imported_project"
    project_key = sanitize_folder_name(project_key).lower()
    package_mode = str(import_data.get("package_mode") or import_data.get("network_package") or "mixed").lower()
    if package_mode not in PACKAGE_MODES:
        package_mode = "mixed" if package_mode in {"auto", "ethernet+can", "can+ethernet"} else "can"
    defaults = import_domain_defaults(industry, package_mode)
    channels = int(import_data.get("channels") or defaults["channels"])
    participants = [
        normalize_import_participant(item, index, channels)
        for index, item in enumerate(import_data.get("participants") or import_data.get("nodes") or import_data.get("devices") or [])
    ]
    add_import_gateway_if_needed(participants, channels)
    if len(participants) < 2:
        raise ValueError("Import needs at least two participants/devices")

    profile = {
        "description": str(import_data.get("description") or f"Imported {industry} integration profile '{project_key}'."),
        "bus_type": str(import_data.get("bus_type") or defaults["bus_type"]),
        "channels": channels,
        "duration_s": float(import_data.get("duration_s") or defaults["duration_s"]),
        "messages": int(import_data.get("messages") or max(defaults["messages"], len(participants) * 4)),
        "participants": participants,
        "industry": str(industry).lower(),
        "source": str(import_path or "inline"),
    }
    setup = build_simulation_setup(profile["description"], package_mode, str(import_data.get("signal_value_strategy") or "calculated"))
    setup["channels"] = channels
    setup["eth_messages"] = int(import_data.get("eth_messages") or max(1, min(500, len(participants))))
    request_data = {
        "schema": SCHEMA,
        "simulation_mode": "restbus",
        "bus_type": profile["bus_type"],
        "channels": channels,
        "duration_s": profile["duration_s"],
        "messages": profile["messages"],
        "nominal_bitrate": int(import_data.get("nominal_bitrate") or 500000),
        "data_bitrate": int(import_data.get("data_bitrate") or 2000000),
        "seed": int(import_data.get("seed") or 42),
        "participants": [clone_participant(item) for item in participants],
        "output_dir": trace_output_dir_for_prompt(project_key),
        "scenario": {
            "package_mode": package_mode,
            "signal_value_strategy": setup["signal_value_strategy"],
            "channels": channels,
            "eth_messages": setup.get("eth_messages"),
            "domain": str(industry).lower(),
            "project_profile": project_key,
            "maneuver_profile": import_data.get("maneuver") or "imported",
            "description": profile["description"],
        },
        "generation_source": {
            "type": "profile_import",
            "schema": import_data.get("schema") or PROFILE_IMPORT_SCHEMA,
            "path": str(import_path or ""),
            "industry": str(industry).lower(),
        },
    }
    normalized_hardware = normalize_hardware_config(import_data)
    if normalized_hardware["hardware"] or normalized_hardware["networks"]:
        request_data["hardware"] = normalized_hardware["hardware"]
        request_data["networks"] = normalized_hardware["networks"]
        if normalized_hardware["technology_profiles"]:
            request_data["technology_profiles"] = normalized_hardware["technology_profiles"]
    apply_simulation_setup(request_data, setup)
    request_data["filter_system"]["domain"] = str(industry).lower()
    request_data["filter_system"]["profile"] = project_key
    return validate_request_consistency(request_data), (project_key, profile)

def ensure_project_profile_table(industry):
    db_path = project_profile_db_path(industry)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_profiles (
                key TEXT PRIMARY KEY,
                industry TEXT NOT NULL,
                description TEXT NOT NULL,
                bus_type TEXT NOT NULL,
                channels INTEGER NOT NULL,
                duration_s REAL NOT NULL,
                messages INTEGER,
                participants_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
    return db_path

def install_imported_profile(project_key, profile):
    db_path = ensure_project_profile_table(profile.get("industry") or DEFAULT_PROJECT_INDUSTRY)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO project_profiles
            (key, industry, description, bus_type, channels, duration_s, messages, participants_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                industry=excluded.industry,
                description=excluded.description,
                bus_type=excluded.bus_type,
                channels=excluded.channels,
                duration_s=excluded.duration_s,
                messages=excluded.messages,
                participants_json=excluded.participants_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                project_key,
                profile.get("industry") or DEFAULT_PROJECT_INDUSTRY.lower(),
                profile["description"],
                profile["bus_type"],
                int(profile["channels"]),
                float(profile["duration_s"]),
                int(profile["messages"]) if profile.get("messages") is not None else None,
                json.dumps(profile["participants"], ensure_ascii=False),
            ),
        )
    return db_path

def write_import_template(path):
    template = {
        "schema": PROFILE_IMPORT_SCHEMA,
        "industry": "Generic",
        "project_key": "external_vehicle_platform",
        "description": "Imported topology from another project. Replace nodes with your real components.",
        "package_mode": "mixed",
        "bus_type": "fd",
        "channels": 5,
        "duration_s": 20,
        "messages": 120,
        "participants": [
            {
                "name": "LIDAR_FRONT",
                "role": "lidar_sensor",
                "channel": 1,
                "cycle_ms": 20,
                "provided_services": ["OBJECT_LIST", "LIDAR_HEALTH"],
                "consumed_services": ["SYNC_TIME"],
                "signals": [
                    {
                        "name": "OEM_ObjectDistance",
                        "start_bit": 16,
                        "length": 16,
                        "factor": 0.01,
                        "offset": 0,
                        "minimum": 0,
                        "maximum": 65535,
                        "unit": "m",
                    },
                    {
                        "name": "OEM_ObjectRelSpeed",
                        "start_bit": 32,
                        "length": 16,
                        "factor": 0.01,
                        "offset": -327.68,
                        "minimum": 0,
                        "maximum": 65535,
                        "unit": "m/s",
                    },
                ],
            },
            {
                "name": "CENTRAL_GATEWAY",
                "role": "gateway",
                "channel": 0,
                "cycle_ms": 50,
                "provided_services": ["ROUTING_STATUS", "SYNC_TIME"],
                "consumed_services": ["OBJECT_LIST", "DIAGNOSTIC_REQUEST"],
                "gateway_to_channel": 2,
            },
            {
                "name": "DIAG_TESTER",
                "role": "tester",
                "channel": 4,
                "cycle_ms": 100,
                "provided_services": ["DIAGNOSTIC_REQUEST"],
                "consumed_services": ["ROUTING_STATUS", "LIDAR_HEALTH"],
            },
            {
                "name": "ADAS_CONTROLLER",
                "role": "domain_controller",
                "channel": 2,
                "cycle_ms": 10,
                "provided_services": ["TRAJECTORY_PLAN"],
                "consumed_services": ["OBJECT_LIST", "ROUTING_STATUS"],
            },
            {
                "name": "PLC_CONTROLLER",
                "role": "industrial_controller",
                "channel": 3,
                "cycle_ms": 20,
                "provided_services": ["MACHINE_STATE"],
                "consumed_services": ["TEMPERATURE", "PRESSURE"],
            },
        ],
        "field_aliases": {
            "participants": "also accepts nodes/devices",
            "provided_services": "also accepts publishes/string-list signals/outputs",
            "consumed_services": "also accepts subscribes/inputs/commands",
            "cycle_ms": "also accepts period_ms/cycle",
        },
        "external_signal_policy": {
            "signals_as_objects": "preserved as external signal definitions",
            "preserved_fields": ["name", "start_bit", "length", "factor", "offset", "minimum", "maximum", "unit", "kind"],
            "fallback": "built-in physical signal catalog is used only when no external signal definitions are provided",
        },
        "integration_contract": {
            "import_cli": "py nemotron.py --import-profile imported_profile.json --out generated_config.json",
            "run_cli": "py communication_simulator.py --config generated_config.json",
            "python_api": "from communication_simulator import run_simulation",
        },
        "domain_hints": {
            "automotive": ["CAN-FD", "Ethernet", "SOME/IP", "service_discovery", "gateway", "diagnostics"],
            "industrial": ["OPC_UA", "client_server", "pubsub", "PLC", "field_device", "sensor"],
            "robotics": ["ROS2", "DDS", "publisher", "subscriber", "lidar", "camera", "controller"],
        },
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2)
    return path

def physical_ai_request_from_workflow(prompt, workflow_key):
    ensure_profile_cache()
    workflow = PHYSICAL_AI_WORKFLOWS[workflow_key]
    skill_paths = discover_skill_paths()
    used_skills = ["physical-ai-neural-reconstruction"] + [step["skill"] for step in workflow.get("steps", [])]
    missing_skills = [skill for skill in used_skills if skill not in skill_paths]
    upstream_root = (
        os.getenv("NUREC_SKILLS_UPSTREAM_ROOT")
        or os.getenv("PHYSICAL_AI_SKILL_HUB_UPSTREAM_ROOT")
        or str(Path.home() / ".physical-ai-skill-hub" / "upstreams" / "nurec-skills")
    )
    required_env = ["NGC_API_KEY", "HF_TOKEN"]
    return {
        "schema": "can-simulator.physical-ai-workflow-request.v1",
        "domain": "physical_ai",
        "router_skill": "physical-ai-neural-reconstruction",
        "router_skill_path": skill_paths.get("physical-ai-neural-reconstruction"),
        "upstream_skills_root": upstream_root,
        "missing_skill_bodies": missing_skills,
        "readiness": physical_ai_readiness(check_network=False, login_ngc=False),
        "workflow": workflow_key,
        "description": workflow["description"],
        "prompt": prompt,
        "steps": [
            {
                "order": index,
                "skill": step["skill"],
                "skill_path": skill_paths.get(step["skill"]),
                "summary": step["summary"],
            }
            for index, step in enumerate(workflow.get("steps", []), start=1)
        ],
        "required_environment": {
            key: "set" if os.getenv(key) else "missing"
            for key in required_env
        },
        "notes": [
            "This is a router workflow only; do not invent or execute NuRec/NRE/NCore commands from this file.",
            "Read the listed upstream skill body before running mutating conversion, training, rendering, or download commands.",
            "Hugging Face gated PhysicalAI licenses must be accepted before dataset downloads.",
        ],
    }

def list_profiles():
    ensure_profile_cache()
    print(f"Config DB: {CONFIG_DB_PATH}")
    print("Projects:")
    for key, profile in PROJECT_PROFILES.items():
        source = profile.get("source")
        suffix = f" [{source}]" if source else ""
        print(f"  {key}: {profile['description']}{suffix}")
    print("\nPackage modes:")
    for key, mode in PACKAGE_MODES.items():
        print(f"  {key}: {mode['description']} -> {mode['formats']}")
    print("\nSignal value strategies:")
    for key, description in SIGNAL_VALUE_STRATEGIES.items():
        print(f"  {key}: {description}")
    print("\nOutput formats:")
    print(f"  can: {', '.join(sorted(CAN_OUTPUT_FORMATS))}")
    print(f"  ethernet: {', '.join(sorted(ETH_OUTPUT_FORMATS))}")
    print("\nPhysical AI skill names:")
    print(f"  {', '.join(PHYSICAL_AI_SKILL_NAMES)}")
    print("\nManeuvers:")
    for key, profile in MANEUVER_PROFILES.items():
        print(f"  {key}: {profile['description']}")
    print("\nPhysical AI workflows:")
    for key, workflow in PHYSICAL_AI_WORKFLOWS.items():
        print(f"  {key}: {workflow['description']}")

def infer_project(prompt, selected):
    if selected and selected != "auto":
        return selected
    text = prompt.lower()
    if any(word in text for word in ["adas", "autonom", "autonomous", "spur", "lane", "aeb", "notbrems", "acc", "radar", "kamera"]):
        return "adas"
    if any(word in text for word in [
        "motor", "engine", "verbrenner", "ice", "powertrain", "antrieb", "getriebe",
        "transmission", "battery", "batterie", "hochvolt", "hv", "high voltage",
        "ev", "electric", "hybrid", "bms", "inverter", "wechselrichter", "dcdc",
        "dc/dc", "onboard charger", "obc", "laden", "charging", "ladeport",
        "precharge", "vorkondition", "kontaktor", "contactor", "fuel", "kraftstoff",
        "lambda", "nox", "dpf", "abgas",
    ]):
        return "powertrain"
    if any(word in text for word in [
        "body", "komfort", "licht", "tuer", "tür", "hvac", "sitz", "fenster",
        "kessy", "keyless", "peps", "radio", "infotainment", "hud", "kombi",
        "cluster", "instrument", "airbag", "srs", "tacho", "display", "head unit",
        "telematik", "telematics", "ecall", "tpms", "reifendruck", "ota",
        "over the air", "over-the-air", "gps", "gnss", "v2x", "car2x", "c2x",
        "cloud", "mobilfunk", "cellular", "5g", "lte", "wifi", "wlan",
        "bluetooth", "cybersecurity", "security", "update",
    ]):
        return "body"
    return "adas"

def infer_maneuver(prompt, selected):
    ensure_profile_cache()
    if selected and selected != "auto":
        return selected
    text = prompt.lower()
    for key, profile in MANEUVER_PROFILES.items():
        if any(keyword in text for keyword in profile.get("keywords", [])):
            return key
    return None

def sanitize_folder_name(value):
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    value = re.sub(r"_+", "_", value).strip("._")
    return value or "generated_restbus_simulation"

def trace_output_dir_for_prompt(prompt, prefix=None):
    timestamp = sanitize_folder_name(prefix) if prefix else time.strftime("%Y_%m_%d_%H_%M")
    scenario = sanitize_folder_name(prompt)
    return str(TRACE_ROOT / f"{timestamp}_{scenario}")

def clone_participant(participant):
    return copy.deepcopy(participant)

def participant_map(participants):
    return {str(participant.get("name", "")).upper(): participant for participant in participants}

def ensure_participant(participants, participant):
    existing = participant_map(participants).get(str(participant.get("name", "")).upper())
    if existing is None:
        participants.append(clone_participant(participant))
        return participants[-1]
    for key, value in participant.items():
        if key in {"provided_services", "consumed_services"}:
            existing_values = existing.setdefault(key, [])
            for service in value:
                if service not in existing_values:
                    existing_values.append(service)
        elif existing.get(key) in (None, "", []):
            existing[key] = value
    return existing

def add_unique(values, item):
    if item not in values:
        values.append(item)

def find_or_create_node(participants, name, role="ecu", channel=0, cycle_ms=20):
    nodes = participant_map(participants)
    node = nodes.get(name.upper())
    if node is not None:
        return node
    node = {
        "name": name,
        "role": role,
        "channel": channel,
        "cycle_ms": cycle_ms,
        "provided_services": [],
        "consumed_services": [],
        "health": "nominal",
    }
    participants.append(node)
    return node

def apply_service_link(participants, sender_name, service, receiver_name):
    sender = find_or_create_node(participants, sender_name)
    receiver = find_or_create_node(participants, receiver_name)
    add_unique(sender.setdefault("provided_services", []), service)
    add_unique(receiver.setdefault("consumed_services", []), service)

def apply_maneuver_profile(request_data, maneuver_key):
    ensure_profile_cache()
    if not maneuver_key:
        return
    profile = MANEUVER_PROFILES[maneuver_key]
    participants = request_data.setdefault("participants", [])
    for participant in profile.get("required_participants", []):
        ensure_participant(participants, participant)
    for sender_name, service, receiver_name in profile.get("service_links", []):
        apply_service_link(participants, sender_name, service, receiver_name)
    nodes = participant_map(participants)
    for name, cycle_ms in profile.get("cycle_overrides", {}).items():
        if name in nodes:
            nodes[name]["cycle_ms"] = cycle_ms
    request_data["duration_s"] = float(request_data.get("duration_s") or profile.get("duration_s") or 20.0)
    if profile.get("duration_s"):
        request_data["duration_s"] = max(float(request_data["duration_s"]), float(profile["duration_s"]))

def apply_fault_hints(request_data, prompt):
    text = prompt.lower()
    participants = request_data.get("participants", [])
    if not participants:
        return
    nodes = participant_map(participants)
    if any(word in text for word in ["kamera fehler", "camera fault", "kamera degradiert", "verschmutzte kamera"]):
        for name in ["CAMERA_FRONT_WIDE"]:
            if name in nodes:
                nodes[name]["health"] = "degraded"
    if any(word in text for word in ["radar ausfall", "radar offline", "radar failure"]):
        for name in ["RADAR_FRONT_LONG_RANGE"]:
            if name in nodes:
                nodes[name]["health"] = "offline"
    if any(word in text for word in ["gateway fehler", "gateway degraded", "routing problem"]):
        for name, participant in nodes.items():
            if "GATEWAY" in name:
                participant["health"] = "degraded"

def normalize_request(request_data, prompt, project_key, maneuver_key, setup):
    profile = PROJECT_PROFILES[project_key]
    selected_industry = project_profile_industry(project_key, profile)
    request_data.setdefault("schema", SCHEMA)
    request_data["simulation_mode"] = "restbus"
    request_data.setdefault("bus_type", profile["bus_type"])
    request_data.setdefault("channels", profile["channels"])
    request_data.setdefault("nominal_bitrate", 500000)
    request_data.setdefault("data_bitrate", 2000000)
    request_data.setdefault("seed", 42)
    if profile.get("messages") is not None:
        request_data["messages"] = max(int(request_data.get("messages") or 0), int(profile["messages"]))
    else:
        request_data.setdefault("messages", None)
    request_data.setdefault("duration_s", profile["duration_s"])
    request_data["output_dir"] = trace_output_dir_for_prompt(prompt, setup.get("trace_prefix"))

    participants = request_data.get("participants")
    if not isinstance(participants, list) or len(participants) < 2:
        request_data["participants"] = [clone_participant(item) for item in profile["participants"]]
    else:
        for participant in profile["participants"]:
            ensure_participant(participants, participant)

    apply_maneuver_profile(request_data, maneuver_key)
    apply_fault_hints(request_data, prompt)
    apply_simulation_setup(request_data, setup)
    request_data["scenario"] = {
        "package_mode": setup["package_mode"],
        "signal_value_strategy": setup["signal_value_strategy"],
        "channels": request_data.get("channels"),
        "eth_messages": request_data.get("eth_messages"),
        "industry": selected_industry,
        "domain": IndustryContext.resolve(selected_industry).key,
        "project_profile": project_key,
        "maneuver_profile": maneuver_key or "generic",
        "description": prompt,
    }
    request_data["filter_system"]["industry"] = selected_industry
    request_data["filter_system"]["domain"] = IndustryContext.resolve(selected_industry).key
    request_data["filter_system"]["profile"] = maneuver_key or project_key or "generic"
    return validate_request_consistency(request_data)

def build_profile_context(project_key, maneuver_key, setup):
    project = PROJECT_PROFILES[project_key]
    context = {
        "simulation_setup_first": setup,
        "selected_project_profile": project_key,
        "project_description": project["description"],
        "recommended_bus_type": project["bus_type"],
        "recommended_channels": project["channels"],
        "recommended_participants": project["participants"],
    }
    if maneuver_key:
        maneuver = MANEUVER_PROFILES[maneuver_key]
        context["selected_maneuver_profile"] = maneuver_key
        context["maneuver_description"] = maneuver["description"]
        context["maneuver_service_links"] = maneuver.get("service_links", [])
        context["maneuver_cycle_overrides"] = maneuver.get("cycle_overrides", {})
    return json.dumps(context, indent=2)

def local_request_from_profiles(prompt, project_key, maneuver_key, setup):
    request_data = {
        "schema": SCHEMA,
        "simulation_mode": "restbus",
        "output_dir": f"generated_{project_key}_{maneuver_key or 'generic'}",
        "participants": [clone_participant(item) for item in PROJECT_PROFILES[project_key]["participants"]],
    }
    request_data = normalize_request(request_data, prompt, project_key, maneuver_key, setup)
    request_data["generation_source"] = {
        "type": "local_profiles",
        "project_profile": project_key,
        "maneuver_profile": maneuver_key or "generic",
        "project_db": str(project_profile_db_path()),
        "maneuver_db": str(MANEUVER_DB_PATH),
    }
    return request_data

def run_trace_generator(request_path):
    subprocess.run(
        [sys.executable, "communication_simulator.py", "--config", str(request_path)],
        check=True,
    )

def run_trace_generator_and_learn(request_path, request_data):
    run_trace_generator(request_path)
    return record_simulation_learning(request_path, request_data)

def main():
    global PROJECT_PROFILES, MANEUVER_PROFILES, PHYSICAL_AI_WORKFLOWS

    status = StatusBar()
    status.update(3, "Initialisiere Config-Library")
    load_runtime_config_from_library()
    status.update(4, "Initialisiere Projektprofil-Library")
    ensure_project_profile_library()
    PROJECT_PROFILES = load_project_profiles_from_library()
    status.update(8, f"Lade {len(PROJECT_PROFILES)} Projektprofile")
    status.update(10, "Initialisiere Manoever-Datenbank")
    ensure_maneuver_database()
    MANEUVER_PROFILES = load_maneuver_profiles()
    PHYSICAL_AI_WORKFLOWS = load_physical_ai_workflows()
    status.update(12, f"Lade {len(MANEUVER_PROFILES)} Manoever, {len(PHYSICAL_AI_WORKFLOWS)} Physical-AI-Workflows")

    parser = argparse.ArgumentParser(description="Nemotron-powered CAN Simulation Assistant")
    parser.add_argument("prompt", nargs="*", help="Natural language description of the simulation scenario")
    parser.add_argument("--out", default="generated_request.json", help="Output JSON file for the request")
    parser.add_argument("--run", action="store_true", help="Run the simulation immediately after generation")
    parser.add_argument("--project", choices=["auto", *PROJECT_PROFILES.keys()], default="auto", help="Project profile used to shape the restbus topology")
    parser.add_argument("--maneuver", choices=["auto", *MANEUVER_PROFILES.keys()], default="auto", help="Maneuver profile used to shape services, timing, and faults")
    parser.add_argument("--package-mode", choices=["auto", *PACKAGE_MODES.keys()], default="auto", help="First setup decision: can, ethernet, or mixed output package")
    parser.add_argument("--signal-values", choices=["auto", *SIGNAL_VALUE_STRATEGIES.keys()], default="auto", help="First setup decision: how message signal values are filled")
    parser.add_argument("--channels", type=int, choices=range(1, 17), default=None, metavar="1-16", help="CAN channel count for CAN or mixed package mode")
    parser.add_argument("--eth-messages", type=int, default=None, help="Ethernet communication stream count for Ethernet or mixed package mode")
    parser.add_argument("--trace-prefix", default=None, help="Prefix for emulated trace folder, e.g. 2026_06_19_19_04")
    parser.add_argument("--domain", choices=["auto", "automotive", "physical_ai"], default="auto", help="Domain router: automotive CAN/restbus or Physical AI NuRec workflow")
    parser.add_argument("--workflow", choices=["auto", *PHYSICAL_AI_WORKFLOWS.keys()], default="auto", help="Physical AI workflow profile")
    parser.add_argument("--offline", action="store_true", help="Generate from local project/maneuver profiles without calling the AI API")
    parser.add_argument("--ai-mode", choices=["offline", "local", "hybrid", "cloud"], default="hybrid", help="AI routing: offline profiles, local AI, hybrid local/cloud, or cloud only")
    parser.add_argument("--api-timeout", type=int, default=60, help="Seconds to wait for each Nemotron API attempt before falling back")
    parser.add_argument("--api-retries", type=int, default=2, help="Nemotron retry count with smaller reasoning budgets")
    parser.add_argument("--local-ai-timeout", type=int, default=10, help="Seconds to wait for each local AI attempt")
    parser.add_argument("--local-ai-retries", type=int, default=0, help="Local AI retry count")
    parser.add_argument("--list-profiles", action="store_true", help="List available project and maneuver profiles")
    parser.add_argument("--check-physical-ai", action="store_true", help="Check Physical AI/NuRec skills, tokens, Docker, Hugging Face access, and optional NGC login")
    parser.add_argument("--login-ngc", action="store_true", help="With --check-physical-ai, run docker login nvcr.io using NGC_API_KEY without printing the token")
    parser.add_argument("--write-import-template", default=None, help="Write a JSON template for importing an external hardware/topology profile")
    parser.add_argument("--import-profile", default=None, help="Import an external hardware/topology profile into a standalone simulation configuration")
    parser.add_argument("--install-imported-profile", action="store_true", help="Store --import-profile as a reusable project profile in physic_lib/Industries/<industry>")
    parser.add_argument("--import-industry", default=None, help="Override imported industry/domain, e.g. Automotive, Industrial, Robotics")
    parser.add_argument("--import-project-key", default=None, help="Override imported project profile key")
    args = parser.parse_args()
    if args.eth_messages is not None and args.eth_messages < 1:
        parser.error("--eth-messages must be at least 1")
    if args.api_timeout < 10:
        parser.error("--api-timeout must be at least 10 seconds")
    if args.api_retries < 0:
        parser.error("--api-retries must be 0 or greater")
    if args.local_ai_timeout < 5:
        parser.error("--local-ai-timeout must be at least 5 seconds")
    if args.local_ai_retries < 0:
        parser.error("--local-ai-retries must be 0 or greater")
    if args.offline:
        args.ai_mode = "offline"

    if args.write_import_template:
        template_path = write_import_template(args.write_import_template)
        status.update(100, "Import-Template geschrieben")
        print(f"Import template: {template_path}")
        return

    if args.list_profiles:
        status.update(100, "Profile geladen")
        list_profiles()
        return

    if args.check_physical_ai:
        readiness = physical_ai_readiness(check_network=True, login_ngc=args.login_ngc, status=status)
        status.update(100, "Physical-AI Pruefung fertig")
        print_physical_ai_readiness(readiness)
        return

    if args.import_profile:
        status.update(30, "Lese externes Importprofil")
        import_path = Path(args.import_profile)
        with open(import_path, "r", encoding="utf-8-sig") as f:
            import_data = json.load(f)
        status.update(55, "Normalisiere Importprofil")
        request_data, profile_info = normalize_imported_profile(
            import_data,
            import_path=import_path,
            industry_override=args.import_industry,
            project_key_override=args.import_project_key,
        )
        status.update(72, "Schreibe Simulationskonfiguration")
        library_path = write_request_json(args.out, request_data)
        installed_db = None
        if args.install_imported_profile:
            if not profile_info:
                print("Info: imported file is already a simulation configuration; no project profile installed.")
            else:
                installed_db = install_imported_profile(*profile_info)
        if args.run:
            status.update(88, "Starte Simulation aus Import")
            status.line()
            run_trace_generator_and_learn(library_path, request_data)
        status.update(100, "Import fertig")
        print(f"Success: Imported profile saved as simulation configuration: {library_path}")
        if installed_db:
            print(f"Installed profile DB: {installed_db}")
        return

    if isinstance(args.prompt, list):
        args.prompt = " ".join(args.prompt).strip()

    interactive_start = not args.prompt
    if interactive_start:
        status.line()
        ask_interactive_simulation_setup(args)

    if not args.prompt:
        print("No prompt provided.")
        print("Example: ADAS Projekt Spurwechsel mit Kamera Fehler")
        try:
            args.prompt = input("Simulation scenario: ").strip()
        except EOFError:
            args.prompt = ""
        if not args.prompt:
            print("Error: No simulation scenario entered.")
            parser.print_help()
            sys.exit(1)
        args.run = choose_interactive_bool("Trace-Erstellung direkt starten?", True)

    status.update(20, "Analysiere Simulations-Setup")
    package_mode = infer_package_mode(args.prompt, args.package_mode)
    signal_value_strategy = infer_signal_value_strategy(args.prompt, args.signal_values)
    setup = build_simulation_setup(args.prompt, package_mode, signal_value_strategy)
    if args.channels is not None:
        setup["channels"] = int(args.channels)
    if args.eth_messages is not None:
        setup["eth_messages"] = int(args.eth_messages)
    if args.trace_prefix:
        setup["trace_prefix"] = args.trace_prefix
    status.update(28, f"Paket={package_mode}, Werte={signal_value_strategy}")
    status.update(32, "Analysiere Szenario")
    domain_key = infer_domain(args.prompt, args.domain)
    if domain_key == "physical_ai":
        workflow_key = infer_physical_ai_workflow(args.prompt, args.workflow)
        if workflow_key not in PHYSICAL_AI_WORKFLOWS:
            print(f"\nError: Unknown Physical AI workflow '{workflow_key}'. Use --list-profiles.")
            sys.exit(1)
        status.update(45, f"Physical AI Workflow={workflow_key}")
        status.update(65, "Erzeuge NuRec Router-Workflow")
        request_data = physical_ai_request_from_workflow(args.prompt, workflow_key)
        status.update(85, "Schreibe Workflow-Datei")
        library_path = write_request_json(args.out, request_data)
        if args.run:
            status.line()
            print("Info: --run is disabled for Physical AI router workflows. Read the listed upstream skills before executing NuRec commands.")
        status.update(100, f"Fertig: {args.out}")
        print(f"Success: Generated Physical AI workflow request saved to {args.out}")
        print(f"Library: {library_path}")
        return

    project_key = infer_project(args.prompt, args.project)
    maneuver_key = infer_maneuver(args.prompt, args.maneuver)
    if maneuver_key and maneuver_key not in MANEUVER_PROFILES:
        print(f"\nError: Unknown maneuver profile '{maneuver_key}'. Use --list-profiles.")
        sys.exit(1)
    status.update(40, f"Projekt={project_key}, Manoever={maneuver_key or 'generic'}")
    profile_context = build_profile_context(project_key, maneuver_key, setup)
    status.line()
    print_router_header(args, project_key, maneuver_key, setup)
    memory_matches = find_simulation_memory(args.prompt, project_key, maneuver_key, setup)
    print_memory_context(memory_matches)

    if args.ai_mode in {"offline", "local", "hybrid"}:
        status.update(45, "Suche passende Library-Vorlage")
        library_match = find_library_request(args.prompt, project_key, maneuver_key, setup)
        if library_match is not None:
            status.line()
            print_router_decision(
                "Library-Treffer nutzen",
                "Ein vorhandener validierter Request passt zu Projekt, Manoever und Paketmodus.",
                source=library_match["path"],
                score=library_match["score"],
            )
            status.update(58, f"Nutze Library-Treffer ({library_match['score']}%)")
            request_data = request_from_library_match(library_match, args.prompt, project_key, maneuver_key, setup)
            attach_learning_context(request_data, memory_matches)
            status.update(75, "Schreibe Request-Datei")
            library_path = write_request_json(args.out, request_data)
            if args.run:
                status.update(88, "Starte CAN-Simulation")
                status.line()
                run_trace_generator_and_learn(library_path, request_data)
            status.update(100, f"Fertig: {args.out}")
            print(f"Success: Generated request from library saved to {library_path}")
            print(f"Library source: {library_match['path']}")
            print(f"Library: {library_path}")
            return

    if args.ai_mode == "offline" or (args.ai_mode == "hybrid" and maneuver_key):
        status.line()
        print_router_decision(
            "Lokale Profile nutzen",
            "Das Manoever ist bekannt; Projektprofil und Manoeverdatenbank reichen fuer eine deterministische Simulation.",
            source=MANEUVER_DB_PATH,
        )
        status.update(55, "Erzeuge Restbus-Request aus lokalen Profilen")
        request_data = local_request_from_profiles(args.prompt, project_key, maneuver_key, setup)
        attach_learning_context(request_data, memory_matches)
        status.update(75, "Schreibe Request-Datei")
        library_path = write_request_json(args.out, request_data)
        if args.run:
            status.update(88, "Starte CAN-Simulation")
            status.line()
            run_trace_generator_and_learn(library_path, request_data)
        status.update(100, f"Fertig: {args.out}")
        print(f"Success: Generated profile-based request saved to {library_path}")
        print(f"Library: {library_path}")
        return

    if args.ai_mode in {"local", "hybrid"}:
        status.update(50, "Frage lokale KI an")
        status.line()
        print_router_decision(
            "Lokale KI fragen",
            "Kein ausreichender Library-Treffer und kein deterministischer Profilpfad hat gegriffen.",
            source=f"{LOCAL_AI_BASE_URL} / {LOCAL_AI_MODEL}",
        )
        print(f"--- Querying Local AI ({LOCAL_AI_MODEL}) ---")
        print(f"Base URL: {LOCAL_AI_BASE_URL}")
        print(f"Request: {args.prompt}")
        print("-" * 50)
        try:
            full_content = query_local_ai(
                args.prompt,
                profile_context,
                max_retries=args.local_ai_retries,
                timeout_s=args.local_ai_timeout,
            )
            print("\n" + "-" * 50)
            status.update(72, "Verarbeite lokale KI-Antwort")
            request_data = request_from_model_response(full_content, args.prompt, project_key, maneuver_key, setup)
            request_data["generation_source"] = {
                "type": "local_ai",
                "model": LOCAL_AI_MODEL,
                "base_url": LOCAL_AI_BASE_URL,
            }
            attach_learning_context(request_data, memory_matches)
            status.update(84, "Schreibe Request-Datei")
            library_path = write_request_json(args.out, request_data)
            if args.run:
                status.update(92, "Starte CAN-Simulation")
                status.line()
                run_trace_generator_and_learn(library_path, request_data)
            status.update(100, f"Fertig: {args.out}")
            print(f"Success: Generated request from local AI saved to {library_path}")
            print(f"Library: {library_path}")
            return
        except Exception as e:
            status.line()
            print(f"Local AI failed: {e}")
            if args.ai_mode == "local":
                print_router_decision(
                    "Fallback auf lokale Profile",
                    "Lokale KI war nicht verfuegbar oder lieferte keine valide Antwort.",
                    source=MANEUVER_DB_PATH,
                )
                print("Falling back to local project/maneuver profile generation.")
                request_data = local_request_from_profiles(args.prompt, project_key, maneuver_key, setup)
                attach_learning_context(request_data, memory_matches)
                library_path = write_request_json(args.out, request_data)
                if args.run:
                    status.update(88, "Starte CAN-Simulation")
                    status.line()
                    run_trace_generator_and_learn(library_path, request_data)
                status.update(100, f"Fertig: {args.out}")
                print(f"Success: Generated local fallback request saved to {library_path}")
                print(f"Library: {library_path}")
                return
            print("Continuing with cloud fallback.")

    if args.ai_mode in {"cloud", "hybrid"}:
        if not os.getenv("NVIDIA_API_KEY"):
            status.line()
            if args.ai_mode == "cloud":
                print("Error: NVIDIA_API_KEY is not set. Use --ai-mode offline/local/hybrid fallback or set it in .env.")
                sys.exit(1)
            print_router_decision(
                "Fallback auf lokale Profile",
                "Nemotron ist ohne NVIDIA_API_KEY nicht verfuegbar.",
                source=MANEUVER_DB_PATH,
            )
            print("NVIDIA_API_KEY is not set. Falling back to local project/maneuver profile generation.")
            request_data = local_request_from_profiles(args.prompt, project_key, maneuver_key, setup)
            attach_learning_context(request_data, memory_matches)
            library_path = write_request_json(args.out, request_data)
            if args.run:
                status.update(88, "Starte CAN-Simulation")
                status.line()
                run_trace_generator_and_learn(library_path, request_data)
            status.update(100, f"Fertig: {args.out}")
            print(f"Success: Generated fallback request saved to {library_path}")
            print(f"Library: {library_path}")
            return

        status.update(55, "Frage Nemotron KI an")
        status.line()
        print_router_decision(
            "Nemotron KI fragen",
            "Library/lokale KI konnten keine ausreichende Loesung liefern oder Cloud-Modus wurde explizit gewaehlt.",
            source="nvidia/nemotron-3-ultra-550b-a55b",
        )
        print(f"--- Querying Nemotron-3 Ultra (Thinking Enabled) ---")
        print(f"Request: {args.prompt}")
        print(f"Project profile: {project_key}")
        print(f"Maneuver profile: {maneuver_key or 'generic'}")
        print("-" * 50)

        try:
            full_content = query_nemotron(args.prompt, profile_context, max_retries=args.api_retries, timeout_s=args.api_timeout)
            print("\n" + "-" * 50)
            status.update(72, "Verarbeite KI-Antwort")
            request_data = request_from_model_response(full_content, args.prompt, project_key, maneuver_key, setup)
            request_data["generation_source"] = {
                "type": "nemotron",
                "model": "nvidia/nemotron-3-ultra-550b-a55b",
            }
            attach_learning_context(request_data, memory_matches)
            status.update(84, "Schreibe Request-Datei")
            library_path = write_request_json(args.out, request_data)

            if args.run:
                status.update(92, "Starte CAN-Simulation")
                status.line()
                run_trace_generator_and_learn(library_path, request_data)
            status.update(100, f"Fertig: {args.out}")
            print(f"Success: Generated request saved to {library_path}")
            print(f"Library: {library_path}")
            return
        except Exception as e:
            status.line()
            print(f"Nemotron API failed: {e}")
            print_router_decision(
                "Fallback auf lokale Profile",
                "Nemotron war nicht erreichbar oder lieferte keine valide Antwort.",
                source=MANEUVER_DB_PATH,
            )
            print("Falling back to local project/maneuver profile generation.")
            try:
                request_data = local_request_from_profiles(args.prompt, project_key, maneuver_key, setup)
                attach_learning_context(request_data, memory_matches)
                library_path = write_request_json(args.out, request_data)
                status.update(100, f"Fertig: {args.out}")
                print(f"Success: Generated fallback request saved to {args.out}")
                print(f"Library: {library_path}")
                if args.run:
                    print(f"Running simulation: {sys.executable} communication_simulator.py --config {library_path}")
                    run_trace_generator_and_learn(library_path, request_data)
                return
            except Exception as fallback_error:
                status.line()
                print(f"Fallback generation failed: {fallback_error}")
                sys.exit(1)

    status.line()
    print(f"Error: AI mode '{args.ai_mode}' did not produce a request.")
    sys.exit(1)

if __name__ == "__main__":
    main()
