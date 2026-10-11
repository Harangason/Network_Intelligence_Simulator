"""Adapter between HTTP payloads and the existing simulator API."""

from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path
from threading import RLock
from typing import Any

from .config import SIMULATOR_ROOT


if str(SIMULATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIMULATOR_ROOT))

from bus_technologies import DEFAULT_TECHNOLOGY_REGISTRY  # noqa: E402
try:  # package import in API/tests; fallback keeps the standalone backend entry point working
    from ..communication.technologies import (
        DEFAULT_TECHNOLOGY_REGISTRY as COMMUNICATION_TECHNOLOGY_REGISTRY,
        MODEL_TYPES,
    )
except ImportError:  # pragma: no cover - exercised by the standalone launcher
    from communication.technologies import (  # type: ignore[no-redef]
        DEFAULT_TECHNOLOGY_REGISTRY as COMMUNICATION_TECHNOLOGY_REGISTRY,
        MODEL_TYPES,
    )
from communication_simulator import CommunicationSimulator  # noqa: E402
from simulation_cancellation import check_cancellation  # noqa: E402
from standalone_cli import (  # noqa: E402
    DOMAIN_LABELS,
    SUPPORTED_STANDALONE_FORMATS,
    StandaloneSimulationOptions,
    domain_for_technology,
)

from .runtime_analysis import RuntimeBusLoadMonitor


DEFAULT_WORKFLOW_EVENT_LIMIT = 100_000


def _validate_explicit_physical_realizations(config: dict[str, Any]) -> None:
    realizations = list(config.get("physical_realizations") or [])
    realizations.extend((config.get("parameters") or {}).get("physical_realizations") or [])
    for edge in (config.get("topology") or {}).get("edges") or []:
        if isinstance(edge, dict) and isinstance(edge.get("physicalRealization"), dict):
            realizations.append({**edge["physicalRealization"],
                "connection_id": edge.get("id"), "technology_id": edge.get("bus")})
    for realization in realizations:
        if not isinstance(realization, dict):
            raise ValueError("Physische Realisierung muss ein Objekt sein.")
        result = COMMUNICATION_TECHNOLOGY_REGISTRY.validate_physical_realization(realization)
        if result["status"] != "VALID":
            detail = "; ".join(item["code"] for item in result["findings"])
            raise ValueError(f"Physical-Realization-Validierung fehlgeschlagen: {detail}")


def _workflow_event_limit() -> int:
    raw = os.environ.get("WORKFLOW_EVENT_LIMIT", str(DEFAULT_WORKFLOW_EVENT_LIMIT)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_WORKFLOW_EVENT_LIMIT
    return min(10_000_000, max(1, value))


class SimulationService:
    def __init__(self) -> None:
        self.simulator = CommunicationSimulator()
        self.runtime_load_monitor = RuntimeBusLoadMonitor()
        self._catalog_lock = RLock()
        self._catalog_snapshot = None

    def catalog(self) -> dict[str, Any]:
        # Callers may edit their result without editing the registry or the
        # HTTP snapshot shared by concurrent requests.
        return copy.deepcopy(self._catalog_entry()[2])

    def catalog_json(self) -> bytes:
        """Serve the complete registry without serializing 14k fields per read."""
        return self._catalog_entry()[3]

    def _catalog_entry(self):
        with self._catalog_lock:
            while True:
                registry = COMMUNICATION_TECHNOLOGY_REGISTRY
                revision = registry.revision
                cached = self._catalog_snapshot
                if cached is not None and cached[0] is registry and cached[1] == revision:
                    return cached
                data = self._build_catalog()
                encoded = json.dumps(data, ensure_ascii=False, allow_nan=False,
                                     separators=(',', ':')).encode('utf-8')
                # Onboarding can replace a generated pack while we build.
                # Publish only a snapshot of one unchanged registry revision.
                if registry is COMMUNICATION_TECHNOLOGY_REGISTRY and revision == registry.revision:
                    self._catalog_snapshot = (registry, revision, data, encoded)
                    return self._catalog_snapshot

    def _build_catalog(self) -> dict[str, Any]:
        profiles = {profile["id"]: profile for profile in COMMUNICATION_TECHNOLOGY_REGISTRY.profiles()}
        domains: list[dict[str, Any]] = []
        for model_type in MODEL_TYPES:
            selected_ids = list(model_type.get("recommended_technologies") or [
                technology_id for technology_id, profile in profiles.items() if profile["domain"] == model_type["id"]
            ])
            # Recommendations control order, not catalog visibility. Every
            # registered technology must expose its evidence status in its
            # owning domain, including profiles without a sizing model.
            selected_ids.extend(
                technology_id for technology_id, profile in profiles.items()
                if profile["domain"] == model_type["id"]
                and technology_id not in selected_ids
            )
            technologies = []
            for technology_id in selected_ids:
                if technology_id not in profiles:
                    continue
                technology = copy.deepcopy(profiles[technology_id])
                technology.setdefault("kind", "protocol" if technology["layer"] in {"NETWORK", "TRANSPORT", "APPLICATION", "INDUSTRY_PROFILE"} else "network")
                technology.setdefault("family", technology["domain"])
                technology.setdefault("medium", technology["hardware_interface"])
                technology.setdefault("topology", "technology_specific")
                technology.setdefault("native_formats", [])
                technology["parameter_schema"] = self._parameter_schema(technology_id, technology)
                technology['parameter_defaults_review'] = COMMUNICATION_TECHNOLOGY_REGISTRY.parameter_defaults_review(technology_id)
                for device_field in technology.get('local_timing_schema') or []:
                    if device_field['key'] == 'bitrate_bps' and technology['parameter_defaults_review']['values'].get('bitrate_bps'):
                        device_field['default'] = technology['parameter_defaults_review']['values']['bitrate_bps']
                technologies.append(technology)
            domains.append({**copy.deepcopy(model_type), "technologies": technologies})
        summary = COMMUNICATION_TECHNOLOGY_REGISTRY.summary()
        return {
            "technology_count": summary["technology_count"],
            "domains": domains,
            "formats": sorted(SUPPORTED_STANDALONE_FORMATS),
            "layers": summary["layers"],
            "implementation_status": summary["implementation_status"],
            "core_model_types": ["HardwareNode", "HardwareInterface", "FunctionalInterface", "TechnologyBinding", "TransportUnit", "PayloadElement"],
        }

    @staticmethod
    def _parameter_schema(technology_id: str, technology: dict[str, Any]) -> list[dict[str, Any]]:
        """Render the registered profile; HTTP does not own parameter definitions."""
        return COMMUNICATION_TECHNOLOGY_REGISTRY.parameter_fields(technology_id)

    def prepare_config(self, payload: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("Die Simulationsanfrage muss ein JSON-Objekt sein.")
        if isinstance(payload.get("config"), dict):
            config = copy.deepcopy(payload["config"])
            for key in (
                "project_id", "scenario", "duration_s", "seed", "formats", "max_events",
                "model_trace_frame_limit", "model_trace_signal_point_limit", "model_trace_points_per_signal",
                "model_trace_event_limit", "golden_trace_event_limit",
                "restbus_session",
                "dropout_probability", "corruption_probability", "duplicate_probability",
                "reordering_probability",
            ):
                if key in payload:
                    config[key] = copy.deepcopy(payload[key])
            if payload.get("workflow_managed"):
                try:
                    requested_events = int(config.get("max_events") or DEFAULT_WORKFLOW_EVENT_LIMIT)
                except (TypeError, ValueError):
                    requested_events = DEFAULT_WORKFLOW_EVENT_LIMIT
                config["max_events"] = min(max(1, requested_events), _workflow_event_limit())
            config["output_dir"] = str(output_dir)
            _validate_explicit_physical_realizations(config)
            return config

        if not payload.get('technology'):
            raise ValueError('TECHNOLOGY_PROFILE_MISSING: Bitte die verwendete Technologie ausdrücklich auswählen.')
        technology_id = str(payload['technology'])
        initial_validation = COMMUNICATION_TECHNOLOGY_REGISTRY.validate_parameters(technology_id, payload)
        if initial_validation['status'] != 'VALID':
            detail = '; '.join(f"{item['code']}: {item['message']}" for item in initial_validation['findings'])
            raise ValueError(f'Technology-Validierung fehlgeschlagen: {detail}')
        communication_profile = COMMUNICATION_TECHNOLOGY_REGISTRY.profile(technology_id)
        if communication_profile.get('connection_type') == 'DIRECT_IO':
            raise ValueError('DIRECT_IO_BINDING_REQUIRED: Direkte I/O-Signale benötigen einen physischen Signalanschluss und Gerätetiming, keine Bus-Nachricht.')
        technology = DEFAULT_TECHNOLOGY_REGISTRY.resolve(technology_id)
        if technology.get("requires_profile"):
            raise ValueError(f"TECHNOLOGY_EXECUTION_MODEL_MISSING: Für {technology_id} ist kein ausführbarer Standalone-Generator registriert. Parameterkatalog und Ausführungsmodell sind getrennte Nachweise.")

        formats_value = payload.get("formats") or ["universal-jsonl", "universal-csv"]
        if isinstance(formats_value, str):
            formats = tuple(
                token for token in re.split(r"[\s,;]+", formats_value.lower()) if token
            )
        else:
            formats = tuple(str(item).strip().lower() for item in formats_value if str(item).strip())
        unknown_formats = sorted(set(formats) - SUPPORTED_STANDALONE_FORMATS)
        if unknown_formats:
            raise ValueError(f"Unbekannte Ausgabeformate: {', '.join(unknown_formats)}")

        data_phase_rate = payload.get('data_bitrate',payload.get('data_bitrate_bps'))
        if data_phase_rate is None and payload.get('can_fd_brs') is False:
            data_phase_rate = payload.get('arbitration_bitrate',payload.get('nominal_bitrate_bps',payload.get('bitrate',payload.get('bitrate_bps'))))
        options = StandaloneSimulationOptions(
            technology=technology["id"],
            industry=str(payload.get("industry") or domain_for_technology(technology["id"])),
            output_dir=output_dir,
            formats=formats,
            duration_s=float(payload.get("duration_s", 1.0)),
            seed=int(payload.get("seed", 42)),
            node_count=int(payload.get("node_count", 2)),
            bitrate=payload.get("bitrate", payload.get("bitrate_bps")),
            arbitration_bitrate=payload.get("arbitration_bitrate", payload.get("nominal_bitrate_bps")),
            data_bitrate=data_phase_rate,
            cycle_ms=float(payload.get("cycle_ms", 100.0)),
            payload_bytes=int(payload.get("payload_bytes", min(8, int(technology.get("max_payload_bytes") or 8)))),
            max_events=int(payload.get("max_events", 100_000)),
            dropout_probability=float(payload.get("dropout_probability", 0.0)),
            corruption_probability=float(payload.get("corruption_probability", 0.0)),
            network_id=str(payload["network_id"]) if payload.get("network_id") else None,
        )
        communication_profile = COMMUNICATION_TECHNOLOGY_REGISTRY.profile(technology_id)
        rate_model = communication_profile.get("rate_model") or {}
        rate_fields = rate_model.get("fields") or []
        rate_parameters = {**payload, **{key: payload[key] for key in
            ("bitrate_bps", "nominal_bitrate_bps", "data_bitrate_bps") if key in payload}}
        if options.bitrate is not None:
            field = "nominal_bitrate_bps" if "nominal_bitrate_bps" in rate_fields else "bitrate_bps"
            rate_parameters.setdefault(field, options.bitrate)
        if options.arbitration_bitrate is not None:
            rate_parameters["nominal_bitrate_bps"] = options.arbitration_bitrate
        if options.data_bitrate is not None:
            rate_parameters["data_bitrate_bps"] = options.data_bitrate
        validation = COMMUNICATION_TECHNOLOGY_REGISTRY.validate_parameters(technology_id, rate_parameters)
        if validation["status"] != "VALID":
            detail = "; ".join(f"{item['code']}: {item['message']}" for item in validation["findings"])
            raise ValueError(f"Technology-Validierung fehlgeschlagen: {detail}")
        self._validate_options(options, communication_profile)
        config = options.to_config()
        # Keep profile-specific user inputs through the legacy standalone
        # adapter. Its universal options cannot describe native word/VL/link
        # parameters; silently dropping them would restore historical values.
        supplied_fields = {field['key']: field for field in
                           COMMUNICATION_TECHNOLOGY_REGISTRY.parameter_fields(technology_id)
                           if field['key'] in payload}
        config['parameters'] = {'technology': communication_profile['id'],
                                **{key: copy.deepcopy(payload[key]) for key in supplied_fields}}
        for network in config.get('networks') or []:
            network['parameters'] = {key: copy.deepcopy(payload[key]) for key, field in supplied_fields.items()
                                     if field['scope'] == 'network'}
        for communication in config.get('communications') or []:
            communication['parameters'] = {key: copy.deepcopy(payload[key]) for key, field in supplied_fields.items()
                                           if field['scope'] in {'message', 'signal', 'route'}}
        if payload.get("physical_realizations") is not None:
            config["physical_realizations"] = copy.deepcopy(payload["physical_realizations"])
        _validate_explicit_physical_realizations(config)
        return config

    @staticmethod
    def _validate_options(
        options: StandaloneSimulationOptions,
        technology: dict[str, Any],
    ) -> None:
        if not 2 <= options.node_count <= 100:
            raise ValueError("node_count muss zwischen 2 und 100 liegen.")
        if options.duration_s <= 0 or options.cycle_ms <= 0:
            raise ValueError("Dauer und Zyklus müssen größer als 0 sein.")
        if not 1 <= options.max_events <= 10_000_000:
            raise ValueError("max_events muss zwischen 1 und 10.000.000 liegen.")
        if options.bitrate is not None and options.bitrate < 1:
            raise ValueError("Die Bitrate muss mindestens 1 bit/s betragen.")
        payload_limit = technology.get("max_payload_bytes")
        if options.payload_bytes < 0 or payload_limit is not None and options.payload_bytes > payload_limit:
            raise ValueError(f"payload_bytes muss zwischen 0 und {payload_limit} liegen.")
        for label, value in (
            ("dropout_probability", options.dropout_probability),
            ("corruption_probability", options.corruption_probability),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{label} muss zwischen 0 und 1 liegen.")

    def run(
        self,
        payload: dict[str, Any],
        output_dir: Path,
        *,
        validate_only: bool = False,
    ) -> dict[str, Any]:
        check_cancellation(force=True)
        config = self.prepare_config(payload, output_dir)
        project_id = str(payload.get("project_id") or config.get("project_id") or "default")
        if payload.get("workflow_managed") or project_id != "default":
            from ..engineering.simulation import enrich_simulation_config, validate_scenario

            frozen_model = config.get("engineering_model") if payload.get("workflow_snapshot_id") else None
            config = enrich_simulation_config(config, project_id, model=frozen_model)
            config["scenario"] = validate_scenario(
                config.get("scenario") if isinstance(config.get("scenario"), dict) else {},
                config.get("engineering_model") if isinstance(config.get("engineering_model"), dict) else {},
            )
        check_cancellation(force=True)
        result = self.simulator.run(config, validate_only=validate_only)
        check_cancellation(force=True)
        if not validate_only:
            if result.get("status") == "validation_failed" or (result.get("hardware_validation") or {}).get("valid") is False:
                findings = (result.get("hardware_validation") or {}).get("findings") or []
                details = "; ".join(str(item.get("message")) for item in findings if item.get("severity") == "error")
                raise ValueError("Hardware-Validierung fehlgeschlagen: " + (details or "kein ausführbarer Simulationslauf"))
            result["runtime_metrics"] = self.runtime_load_monitor.analyze(result, config)
            check_cancellation(force=True)
            if payload.get("workflow_managed") or project_id != "default":
                from ..engineering.simulation import artifact_job_id, persist_trace_metadata

                persist_trace_metadata(project_id, str(payload.get('simulation_job_id') or artifact_job_id(output_dir)), result, config)
        return result
