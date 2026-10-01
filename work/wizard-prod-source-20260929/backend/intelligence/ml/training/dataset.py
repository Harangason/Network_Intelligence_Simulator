"""Dataset builder with versioned synthetic simulator evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from ..core.feature_schema import FEATURE_SCHEMA_VERSION


@dataclass(frozen=True)
class DatasetVersion:
    dataset_id: str
    version: str
    created_at: str
    source_snapshot: str
    train_count: int
    validation_count: int
    test_count: int
    class_distribution: dict[str, int]
    feature_schema_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MLDatasetBuilder:
    def __init__(self, task: str, extractor: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.task = task
        self.extractor = extractor

    def collect(self, examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"features": self.extractor(item["input"]), "label": item["label"], "source": item.get("source", "synthetic")} for item in examples]

    def sanitize(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in rows if row.get("label") and isinstance(row.get("features"), dict)]

    def deduplicate(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        result = []
        for row in rows:
            key = (row["label"], tuple(sorted(row["features"].items())))
            if key in seen:
                continue
            seen.add(key)
            result.append(row)
        return result

    def balance(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(rows, key=lambda row: (str(row["label"]), str(row["features"])))

    def split(self, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        ordered = self.balance(self.deduplicate(self.sanitize(rows)))
        train, validation, test = [], [], []
        by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in ordered:
            by_label[str(row["label"])].append(row)
        for label_rows in by_label.values():
            for index, row in enumerate(label_rows):
                if index == 0:
                    train.append(row)
                elif index % 5 == 1:
                    validation.append(row)
                elif index % 5 == 2:
                    test.append(row)
                else:
                    train.append(row)
        if not train:
            train = ordered
        return {"train": train, "validation": validation, "test": test}

    def version(self, splits: dict[str, list[dict[str, Any]]]) -> DatasetVersion:
        rows = [row for split in splits.values() for row in split]
        return DatasetVersion(
            dataset_id=f"{self.task.lower()}-synthetic",
            version="1.0",
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            source_snapshot="SimulatorMLGoldenSet-v1",
            train_count=len(splits.get("train", [])),
            validation_count=len(splits.get("validation", [])),
            test_count=len(splits.get("test", [])),
            class_distribution=dict(Counter(str(row["label"]) for row in rows)),
            feature_schema_version=FEATURE_SCHEMA_VERSION,
        )

    def export(self, examples: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], DatasetVersion]:
        splits = self.split(self.collect(examples))
        return splits, self.version(splits)


def simulator_ml_golden_examples(task: str) -> list[dict[str, Any]]:
    if task == "SIGNAL_SEMANTIC_CLASSIFICATION":
        return [
            _signal("MotorTemperature", "degC", "signed", 16, -40, 200, "TEMPERATURE"),
            _signal("CoolantTemperature", "degC", "signed", 16, -40, 150, "TEMPERATURE"),
            _signal("MotorRPM", "rpm", "unsigned", 16, 0, 9000, "ROTATIONAL_SPEED"),
            _signal("WheelSpeed", "km/h", "unsigned", 16, 0, 300, "ROTATIONAL_SPEED"),
            _signal("FuelPressure", "bar", "unsigned", 16, 0, 2500, "PRESSURE"),
            _signal("BatteryCurrent", "A", "signed", 16, -1000, 1000, "CURRENT"),
            _signal("BatteryVoltage", "V", "unsigned", 16, 0, 1000, "VOLTAGE"),
            _signal("DoorPosition", "%", "unsigned", 8, 0, 100, "POSITION"),
            _signal("GatewayStatus", "code", "unsigned", 8, 0, 255, "OPERATING_STATE", {"OFF": 0, "READY": 3}),
            _signal("AliveCounter", "code", "unsigned", 4, 0, 15, "COUNTER"),
        ]
    if task == "STATUS_MODEL_CLASSIFICATION":
        return [
            _signal("GatewayStatus", "code", "unsigned", 8, 0, 255, "GATEWAY_STATUS_MODEL", {"OFF": 0, "READY": 3}),
            _signal("MotorHealthStatus", "code", "unsigned", 8, 0, 255, "HEALTH_STATE_MODEL", {"OK": 0, "ERROR": 6}),
            _signal("SensorQualityStatus", "code", "unsigned", 8, 0, 255, "QUALITY_STATE_MODEL", {"GOOD": 0, "INVALID": 2}),
        ]
    if task == "PHYSICAL_MODEL_SELECTION":
        return [
            _signal("MotorTemperature", "degC", "signed", 16, -40, 200, "physical/temperature.py"),
            _signal("MotorRPM", "rpm", "unsigned", 16, 0, 9000, "physical/rotational_speed.py"),
            _signal("FuelPressure", "bar", "unsigned", 16, 0, 2500, "physical/pressure.py"),
            _signal("BatteryCurrent", "A", "signed", 16, -1000, 1000, "physical/current.py"),
            _signal("BatteryVoltage", "V", "unsigned", 16, 0, 1000, "physical/voltage.py"),
        ]
    if task == "TRACE_FAULT_CLASSIFICATION":
        return [
            {"input": {"signals": [{"value": 10}, {"value": 12}], "bus_load": [{"load_percent": 20}]}, "label": "NORMAL"},
            {"input": {"signals": [{"value": 0}, {"value": 0}], "faults": ["STUCK_SIGNAL"]}, "label": "STUCK_SIGNAL"},
            {"input": {"signals": [{"value": 90}, {"value": 120}], "faults": ["OVERHEATING"]}, "label": "OVERHEATING"},
            {"input": {"bus_load": [{"load_percent": 95}], "faults": ["NETWORK_OVERLOAD"]}, "label": "NETWORK_OVERLOAD"},
            {"input": {"faults": ["MESSAGE_LOSS", "dropout"], "events": [{"jitter_ms": 1}]}, "label": "MESSAGE_LOSS"},
            {"input": {"events": [{"jitter_ms": 20}], "faults": ["JITTER_FAULT"]}, "label": "JITTER_FAULT"},
        ]
    return []


def _signal(name: str, unit: str, data_type: str, bits: int, minimum: float, maximum: float, label: str, enum_values: dict[str, int] | None = None) -> dict[str, Any]:
    return {
        "input": {
            "name": name,
            "unit": unit,
            "data_type": data_type,
            "length_bits": bits,
            "min_value": minimum,
            "max_value": maximum,
            "data": {"enum_values": enum_values or {}},
            "communication": {"producer_type": "ECU", "cycle_time_ms": 10},
            "protocol_bindings": [{"protocol": "CAN_FD"}],
        },
        "label": label,
        "source": "SimulatorMLGoldenSet-v1",
    }
