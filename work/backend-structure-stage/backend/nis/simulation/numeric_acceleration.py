"""Optional deterministic CUDA acceleration for bulk numeric simulation work.

The engineering model and database remain authoritative on the CPU.  This
module only accelerates side-effect-free reductions over already generated
numeric data.  Every public operation has a pure-Python fallback so the same
project remains runnable without CUDA or CuPy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import os
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class AccelerationInfo:
    requested: str
    backend: str
    device: str | None
    item_count: int
    accelerated: bool
    deterministic: bool = True
    fallback_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mode() -> str:
    mode = os.environ.get("NUMERIC_ACCELERATOR", "auto").strip().lower()
    return mode if mode in {"auto", "cuda", "cpu"} else "auto"


def _minimum_items() -> int:
    try:
        return max(1, int(os.environ.get("NUMERIC_ACCELERATOR_MIN_ITEMS", "256")))
    except ValueError:
        return 256


def _cupy_backend(item_count: int):
    requested = _mode()
    if requested == "cpu":
        return None, AccelerationInfo(requested, "python", None, item_count, False, fallback_reason="cpu-forced")
    if item_count < _minimum_items():
        return None, AccelerationInfo(requested, "python", None, item_count, False, fallback_reason="below-batch-threshold")
    try:
        import cupy as cp  # type: ignore[import-not-found]

        if cp.cuda.runtime.getDeviceCount() < 1:
            raise RuntimeError("no CUDA device")
        properties = cp.cuda.runtime.getDeviceProperties(0)
        raw_name = properties.get("name", "CUDA") if isinstance(properties, dict) else "CUDA"
        device = raw_name.decode("utf-8", errors="replace") if isinstance(raw_name, bytes) else str(raw_name)
        return cp, AccelerationInfo(requested, "cupy-cuda", device, item_count, True)
    except Exception as error:  # CUDA discovery must never break a simulation.
        return None, AccelerationInfo(
            requested,
            "python",
            None,
            item_count,
            False,
            fallback_reason=f"{type(error).__name__}: {str(error)[:160]}",
        )


def acceleration_status(*, probe_items: int = 256) -> dict[str, Any]:
    """Return the actually usable numeric backend, not just driver presence."""
    _backend, info = _cupy_backend(max(probe_items, _minimum_items()))
    return info.as_dict()


def _python_burst(values: Sequence[float]) -> float:
    return max(
        (sum(values[index:index + 3]) / len(values[index:index + 3]) for index in range(len(values))),
        default=0.0,
    )


def trace_statistics(
    deltas: Sequence[float],
    load_by_network: Mapping[str, Sequence[float]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Summarize trace comparisons and load windows on CUDA when worthwhile."""
    item_count = len(deltas) + sum(len(values) for values in load_by_network.values())
    cp, info = _cupy_backend(item_count)
    if cp is None:
        changed = sum(1 for delta in deltas if abs(float(delta)) > 1e-12)
        rmse = math.sqrt(sum(float(delta) ** 2 for delta in deltas) / len(deltas)) if deltas else 0.0
        networks = {
            network_id: {
                "average_percent": sum(float(value) for value in values) / len(values),
                "peak_percent": max((float(value) for value in values), default=0.0),
            }
            for network_id, values in load_by_network.items()
            if values
        }
        all_loads = [float(value) for values in load_by_network.values() for value in values]
        return {
            "changed_samples": changed,
            "rmse": rmse,
            "average_percent": sum(all_loads) / len(all_loads) if all_loads else 0.0,
            "peak_percent": max(all_loads, default=0.0),
            "burst_percent": max((_python_burst([float(value) for value in values]) for values in load_by_network.values()), default=0.0),
            "networks": networks,
        }, info.as_dict()

    delta_values = cp.asarray(deltas, dtype=cp.float64)
    changed = int(cp.count_nonzero(cp.abs(delta_values) > 1e-12).item()) if deltas else 0
    rmse = float(cp.sqrt(cp.mean(cp.square(delta_values))).item()) if deltas else 0.0
    all_arrays = []
    networks: dict[str, dict[str, float]] = {}
    burst = 0.0
    for network_id, raw_values in load_by_network.items():
        if not raw_values:
            continue
        values = cp.asarray(raw_values, dtype=cp.float64)
        all_arrays.append(values)
        prefix = cp.concatenate((cp.zeros(1, dtype=cp.float64), cp.cumsum(values)))
        starts = cp.arange(values.size)
        ends = cp.minimum(starts + 3, values.size)
        rolling = (prefix[ends] - prefix[starts]) / (ends - starts)
        network_average = float(cp.mean(values).item())
        network_peak = float(cp.max(values).item())
        burst = max(burst, float(cp.max(rolling).item()))
        networks[network_id] = {
            "average_percent": network_average,
            "peak_percent": network_peak,
        }
    if all_arrays:
        loads = cp.concatenate(all_arrays)
        average = float(cp.mean(loads).item())
        peak = float(cp.max(loads).item())
    else:
        average = peak = 0.0
    cp.cuda.get_current_stream().synchronize()
    return {
        "changed_samples": changed,
        "rmse": rmse,
        "average_percent": average,
        "peak_percent": peak,
        "burst_percent": burst,
        "networks": networks,
    }, info.as_dict()


def grouped_route_statistics(
    network_groups: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """Reduce route load columns per physical network in deterministic batches."""
    item_count = sum(len(items) * 4 for items in network_groups.values())
    cp, info = _cupy_backend(item_count)
    fields = ("average_load_percent", "peak_load_percent", "burst_load_percent")
    if cp is None:
        return {
            network_id: {
                **{field: sum(float(item[field]) for item in items) for field in fields},
                "worst_end_to_end_latency_ms": max((float(item["end_to_end_latency_ms"]) for item in items), default=0.0),
            }
            for network_id, items in network_groups.items()
        }, info.as_dict()

    result: dict[str, dict[str, float]] = {}
    for network_id, items in network_groups.items():
        values = cp.asarray(
            [[float(item[field]) for field in fields] + [float(item["end_to_end_latency_ms"])] for item in items],
            dtype=cp.float64,
        )
        sums = cp.sum(values[:, :3], axis=0)
        result[network_id] = {
            **{field: float(sums[index].item()) for index, field in enumerate(fields)},
            "worst_end_to_end_latency_ms": float(cp.max(values[:, 3]).item()) if items else 0.0,
        }
    cp.cuda.get_current_stream().synchronize()
    return result, info.as_dict()
