from __future__ import annotations

from collections import defaultdict


class SignalRuntimeState:
    def __init__(self) -> None:
        self.values: dict[str, float] = {}
        self.timestamps: dict[str, float] = {}
        self.history: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self.discrete_state: dict[str, str] = {}

    def previous(self, signal_id: str, fallback: float) -> float:
        return self.values.get(signal_id, fallback)

    def update(self, signal_id: str, time_s: float, value: float) -> None:
        self.values[signal_id] = value
        self.timestamps[signal_id] = time_s
        self.history[signal_id].append((time_s, value))

    def dt(self, signal_id: str, time_s: float, fallback: float) -> float:
        previous_time = self.timestamps.get(signal_id)
        if previous_time is None:
            return fallback
        return max(0.0, time_s - previous_time)

    def delayed(self, signal_id: str, time_s: float, delay_s: float, fallback: float) -> float:
        target = time_s - delay_s
        prior = [value for timestamp, value in self.history.get(signal_id, []) if timestamp <= target]
        return prior[-1] if prior else fallback

