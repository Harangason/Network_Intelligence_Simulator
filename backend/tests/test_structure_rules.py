from backend.engineering.structure_rules import (
    adapt_structure_name,
    equivalent_system_names,
    infer_device_type,
    normalize_hardware_name,
    recommend_structure_name,
    score_structure_parent,
    semantic_name_signature,
    semantic_name_similarity,
)


def test_hardware_name_keeps_type_in_separate_field():
    assert normalize_hardware_name("Ultraschallverarbeitung-ECU") == "Ultraschallverarbeitung"
    assert normalize_hardware_name("RobotController") == "Robot"
    assert normalize_hardware_name("Airbagsteuergerät") == "Airbag"
    assert normalize_hardware_name("Airbag-Steuergeraet-2") == "Airbag-2"
    assert normalize_hardware_name("System-Gateway") == "System"
    assert normalize_hardware_name("ECU") == "ECU"


def test_infer_device_type_from_engineering_name():
    assert infer_device_type("Thermal-ECU") == "ECU"
    assert infer_device_type("System-Gateway") == "Gateway"
    assert infer_device_type("Temperatursensor") == "SensorController"
    assert infer_device_type("Ventil-Aktor") == "ActuatorController"
    assert infer_device_type("Unbekannt", "IndustrialPC") == "IndustrialPC"
    assert infer_device_type("EGRValvePositionSensor") == "SensorController"
    assert infer_device_type("EGRValvePosition", "SensorController") == "SensorController"
    assert infer_device_type("Sensor processing", "ECU") == "ECU"


def test_recommended_names_follow_the_selected_parent():
    hardware = {"name": "Thermal-ECU"}
    function = {"name": "Temperaturregelung", "interface_type": None}
    interface = {"name": "Bus", "interface_type": "CAN_FD"}

    assert recommend_structure_name("Function", {"name": "Funktion"}, hardware) == "Thermal Funktion"
    assert recommend_structure_name("Interface", interface, function) == "Temperaturregelung_CAN_FD"
    assert recommend_structure_name("Message", {"name": "Message"}, interface) == "BusData"


def test_parent_score_uses_context_current_assignment_and_feedback():
    child = {
        "name": "Thermal Temperaturregelung",
        "description": "Temperatur",
        "domain": "automotive",
    }
    thermal = {"id": "thermal", "name": "Thermal-ECU", "domain": "automotive"}
    motion = {"id": "motion", "name": "Motion-ECU", "domain": "automotive"}

    thermal_score, thermal_reasons = score_structure_parent(
        child,
        thermal,
        current_parent_id="thermal",
        accepted_examples=2,
    )
    motion_score, _ = score_structure_parent(
        child,
        motion,
        rejected_examples=2,
    )

    assert thermal_score > motion_score
    assert "bestehende Zuordnung" in thermal_reasons
    assert any("Lernbeispiele" in reason for reason in thermal_reasons)


def test_semantic_duplicate_detection_ignores_ecu_context_and_language():
    score = semantic_name_similarity(
        "FrontLeftTirePressureSensor_Erfassung",
        "ReifendrucksensorVorneLinks Erfassung",
        left_context="Motion-ECU",
        right_context="Chassis-ECU",
    )

    assert score >= 0.78
    assert semantic_name_signature("ThermalECU_Steuerung", context="Thermal-ECU") == ("control",)


def test_system_synonyms_are_precise_enough_for_adas():
    assert semantic_name_similarity("ADAS", "Fahrerassistenz-ECU") == 1.0
    assert semantic_name_similarity("ADAS", "Driver Assistance ECU") == 1.0
    assert semantic_name_similarity("ADAS", "Driver Door ECU") < 0.86
    assert equivalent_system_names("ADAS", "Fahrerassistenz-ECU") == (True, 1.0)
    assert equivalent_system_names("Abgasnachbehandlung-ECU", "Airbag-ECU")[0] is False


def test_copied_names_are_adapted_to_the_target_ecu():
    assert (
        adapt_structure_name(
            "Motion-ECU_Steuerung",
            "Motion-ECU",
            "Chassis-ECU",
        )
        == "Chassis-ECU_Steuerung"
    )
