from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


@dataclass
class ScalarKalmanFilter:
    """Small dependency-free 1D Kalman filter for simulated signal traces."""

    estimate: float
    covariance: float = 1.0
    process_noise: float = 0.08
    measurement_noise: float = 4.0

    def update(self, measurement: float) -> float:
        self.covariance += self.process_noise
        gain = self.covariance / (self.covariance + self.measurement_noise)
        self.estimate = self.estimate + gain * (measurement - self.estimate)
        self.covariance = (1.0 - gain) * self.covariance
        return self.estimate


@dataclass
class ConstantVelocityKalmanFilter:
    """2-state Kalman filter for position/velocity-like simulated behavior."""

    position: float
    velocity: float = 0.0
    p00: float = 1.0
    p01: float = 0.0
    p10: float = 0.0
    p11: float = 1.0
    process_noise: float = 0.15
    measurement_noise: float = 6.0

    def update(self, measurement: float, dt_s: float) -> float:
        dt_s = max(0.001, min(1.0, dt_s))
        self.position += self.velocity * dt_s

        p00 = self.p00 + dt_s * (self.p10 + self.p01) + dt_s * dt_s * self.p11 + self.process_noise
        p01 = self.p01 + dt_s * self.p11
        p10 = self.p10 + dt_s * self.p11
        p11 = self.p11 + self.process_noise

        innovation = measurement - self.position
        innovation_covariance = p00 + self.measurement_noise
        k0 = p00 / innovation_covariance
        k1 = p10 / innovation_covariance

        self.position += k0 * innovation
        self.velocity += k1 * innovation
        self.p00 = (1.0 - k0) * p00
        self.p01 = (1.0 - k0) * p01
        self.p10 = p10 - k1 * p00
        self.p11 = p11 - k1 * p01
        return self.position


@dataclass
class SignalFilterBank:
    domain: str
    profile: str
    enabled: bool = True
    last_timestamp_by_key: Dict[str, float] = field(default_factory=dict)
    scalar_filters: Dict[str, ScalarKalmanFilter] = field(default_factory=dict)
    cv_filters: Dict[str, ConstantVelocityKalmanFilter] = field(default_factory=dict)
    stats: Dict[str, int] = field(default_factory=lambda: {"updates": 0, "kalman": 0, "clamped": 0})

    def filter_value(
        self,
        *,
        signal_name: str,
        sender: str,
        receiver: str | None,
        role: str | None,
        timestamp_s: float,
        measurement: float,
        minimum: float,
        maximum: float,
    ) -> int:
        if not self.enabled:
            return int(clamp(round(measurement), minimum, maximum))

        key = f"{sender}:{receiver or ''}:{signal_name}"
        previous_timestamp = self.last_timestamp_by_key.get(key, timestamp_s)
        dt_s = timestamp_s - previous_timestamp
        self.last_timestamp_by_key[key] = timestamp_s

        kind = classify_signal(self.domain, self.profile, signal_name, sender, role)
        if kind == "constant_velocity":
            filt = self.cv_filters.get(key)
            if filt is None:
                filt = ConstantVelocityKalmanFilter(
                    position=float(measurement),
                    measurement_noise=measurement_noise_for(signal_name, role),
                    process_noise=process_noise_for(self.domain, self.profile, signal_name, role),
                )
                self.cv_filters[key] = filt
            value = filt.update(float(measurement), dt_s)
            self.stats["kalman"] += 1
        elif kind == "scalar":
            filt = self.scalar_filters.get(key)
            if filt is None:
                filt = ScalarKalmanFilter(
                    estimate=float(measurement),
                    measurement_noise=measurement_noise_for(signal_name, role),
                    process_noise=process_noise_for(self.domain, self.profile, signal_name, role),
                )
                self.scalar_filters[key] = filt
            value = filt.update(float(measurement))
            self.stats["kalman"] += 1
        else:
            value = measurement

        clamped = clamp(round(value), minimum, maximum)
        if clamped != round(value):
            self.stats["clamped"] += 1
        self.stats["updates"] += 1
        return int(clamped)

    def summary(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "domain": self.domain,
            "profile": self.profile,
            "updates": self.stats["updates"],
            "kalman_updates": self.stats["kalman"],
            "clamped_values": self.stats["clamped"],
            "scalar_filters": len(self.scalar_filters),
            "constant_velocity_filters": len(self.cv_filters),
        }


def classify_signal(domain: str, profile: str, signal_name: str, sender: str, role: str | None) -> str:
    text = " ".join([domain, signal_name, sender, role or ""]).lower()
    if any(token in text for token in ["counter", "crc", "mux", "route", "status", "error", "checksum"]):
        return "raw"
    if any(token in text for token in ["distance", "position", "offset", "range", "lane", "object"]):
        return "constant_velocity"
    if any(token in text for token in ["speed", "velocity", "accel", "yaw", "angle", "torque", "pressure", "temperature", "current", "voltage"]):
        return "scalar"
    if any(token in text for token in ["sensor", "fusion", "imu", "radar", "camera", "lidar"]):
        return "scalar"
    return "raw"


def measurement_noise_for(signal_name: str, role: str | None) -> float:
    text = f"{signal_name} {role or ''}".lower()
    if "camera" in text:
        return 8.0
    if "radar" in text:
        return 3.5
    if "imu" in text:
        return 1.8
    if "wheel" in text:
        return 1.2
    if "ultrasonic" in text:
        return 5.0
    return 4.0


def process_noise_for(domain: str, profile: str, signal_name: str, role: str | None) -> float:
    text = f"{domain} {profile} {signal_name} {role or ''}".lower()
    noise = 0.08
    if any(token in text for token in ["emergency", "brake", "evasive", "lane_change", "cut"]):
        noise += 0.12
    if any(token in text for token in ["powertrain", "kickdown", "torque"]):
        noise += 0.10
    if any(token in text for token in ["body", "hvac", "seat", "door"]):
        noise *= 0.5
    return noise


def create_filter_bank(config: Dict[str, Any] | None, scenario: Dict[str, Any] | None = None) -> SignalFilterBank | None:
    config = config or {}
    scenario = scenario or {}
    if config.get("enabled") is False:
        return None
    algorithm = str(config.get("algorithm") or "kalman").lower()
    if algorithm in {"none", "off", "disabled"}:
        return None
    domain = str(config.get("domain") or scenario.get("domain") or "generic")
    profile = str(config.get("profile") or scenario.get("maneuver_profile") or "generic")
    return SignalFilterBank(domain=domain, profile=profile, enabled=True)


def profile_from_request(request: Dict[str, Any]) -> Dict[str, Any]:
    scenario = request.get("scenario") if isinstance(request.get("scenario"), dict) else {}
    config = request.get("filter_system") if isinstance(request.get("filter_system"), dict) else {}
    if config:
        return config
    strategy = request.get("signal_value_strategy")
    return {
        "enabled": strategy in {"calculated", "hybrid"},
        "algorithm": "kalman",
        "domain": scenario.get("domain") or "generic",
        "profile": scenario.get("maneuver_profile") or "generic",
    }


def summarize_filter_bank(filter_bank: SignalFilterBank | None) -> Dict[str, Any]:
    if filter_bank is None:
        return {"enabled": False}
    return filter_bank.summary()


def summarize_filter_banks(
    filter_banks: Iterable[SignalFilterBank],
    config: Dict[str, Any] | None = None,
    scenario: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    banks = list(filter_banks)
    if not banks:
        return {"enabled": False}
    config = config or {}
    scenario = scenario or {}
    return {
        "enabled": True,
        "algorithm": str(config.get("algorithm") or "kalman"),
        "domain": str(config.get("domain") or scenario.get("domain") or banks[0].domain),
        "profile": str(config.get("profile") or scenario.get("maneuver_profile") or banks[0].profile),
        "banks": len(banks),
        "updates": sum(bank.stats["updates"] for bank in banks),
        "kalman_updates": sum(bank.stats["kalman"] for bank in banks),
        "clamped_values": sum(bank.stats["clamped"] for bank in banks),
        "scalar_filters": sum(len(bank.scalar_filters) for bank in banks),
        "constant_velocity_filters": sum(len(bank.cv_filters) for bank in banks),
    }
