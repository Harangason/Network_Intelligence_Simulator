"""Extensible technology registry and resolvers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from .components import (
    IdentityDecoder,
    IdentityEncoder,
    TechnologyBindingAdapter,
    TechnologyLoadCalculator,
    TechnologyTimingModel,
    TechnologyTransportGenerator,
    TechnologyValidator,
)
from .models import ImplementationStatus, Layer, TechnologyCapability, TechnologyProfile, TechnologyStack, TransportRequirement
from .physical import physical_profile, validate_physical_realization


LAYER_ORDER = {layer.value: index for index, layer in enumerate(Layer)}


def _identity_token(value: Any) -> str:
    token = str(value or "custom_protocol").strip().lower().replace("-", "_").replace("/", "_").replace(" ", "_")
    while "__" in token:
        token = token.replace("__", "_")
    return token


# Ingress aliases belong to technology identities and are exported with them.
# Device classes (for example SPS/PLC) are not communication technologies.
BUILTIN_PROFILE_ALIASES = {
    "can_fd": ("CANFD",), "can_xl": ("CANXL",), "someip": ("some_ip",),
    "ethernet": ("automotiveethernet",), "modbus_tcp": ("modbustcp",),
    "modbus_rtu": ("modbusrtu",), "opc_ua": ("opcua",),
    "arinc429": ("arinc",), "mil_std_1553": ("milstd_1553",), "dds": ("dds_rtps",),
    "ros2": ("ROS2", "ROS_2", "ros-2", "ros2_dds"),
    "rs485": ("rs_485",), "rs422": ("rs_422",),
}
BUILTIN_INGRESS_ALIASES = {
    _identity_token(alias): canonical
    for canonical, aliases in BUILTIN_PROFILE_ALIASES.items() for alias in aliases
}


def format_rate_bps(value: int) -> str:
    rate = int(value)
    for divisor, unit in ((1_000_000_000, "Gbit/s"), (1_000_000, "Mbit/s"), (1_000, "kbit/s")):
        if rate >= divisor:
            number = rate / divisor
            rendered = f"{number:.3f}".rstrip("0").rstrip(".").replace(".", ",")
            return f"{rendered} {unit}"
    return f"{rate} bit/s"


class TechnologyRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, TechnologyProfile] = {}
        self._aliases: dict[str, str] = {}
        self._bindings: dict[str, Any] = {}
        self._generators: dict[str, Any] = {}
        self._validators: dict[str, list[Any]] = {}
        self._encoders: dict[str, Any] = {}
        self._decoders: dict[str, Any] = {}
        self._load_calculators: dict[str, Any] = {}
        self._timing_models: dict[str, Any] = {}

    def normalize_id(self, value: Any) -> str:
        token = _identity_token(value)
        return self._aliases.get(token, BUILTIN_INGRESS_ALIASES.get(token, token))

    def register_profile(self, technology_id: str, profile: dict[str, Any]) -> None:
        key = self.normalize_id(technology_id)
        if key in self._profiles:
            raise ValueError(f"technology already registered: {key}")
        supplied_aliases = profile.get("aliases") or ()
        if not isinstance(supplied_aliases, (list, tuple)):
            raise ValueError("technology aliases must be a list")
        label = str(profile.get("label") or key).strip()
        aliases = list(dict.fromkeys(str(alias).strip() for alias in
                       (*BUILTIN_PROFILE_ALIASES.get(key, ()), label, *supplied_aliases)
                       if str(alias).strip()))
        pending_aliases: dict[str, str] = {}
        for alias in aliases:
            alias_key = _identity_token(alias)
            if alias_key and alias_key != key:
                owner = self._aliases.get(alias_key, BUILTIN_INGRESS_ALIASES.get(alias_key))
                if alias_key in self._profiles and alias_key != key:
                    raise ValueError(f"technology alias conflicts with canonical identity: {alias_key}")
                if owner and owner != key:
                    raise ValueError(f"technology alias already registered: {alias_key}")
                pending_aliases[alias_key] = key
        self._profiles[key] = TechnologyProfile.from_dict({
            **deepcopy(profile), "id": key, "canonical_id": key, "display_name": label,
            "aliases": aliases,
            "classification": profile.get("connection_type") or profile["layer"],
            "fallback_allowed": False,
            # A profile describes available models; registration supplies no
            # project parameters, physical realization or execution evidence.
            "verification_status": "UNVERIFIED", "verification_scope": "REGISTRY_TEMPLATE",
        })
        self._aliases.update(pending_aliases)

    def register_generated_profile(self, profile: dict[str, Any]) -> None:
        """Register or update a validated generated pack without touching built-ins."""
        technology_id = self.normalize_id(profile.get("id"))
        existing = self._profiles.get(technology_id)
        if existing and existing.to_dict().get("knowledge_origin") != "GENERATED_TECHNOLOGY_PACK":
            raise ValueError(f"generated pack cannot replace built-in technology: {technology_id}")
        if profile.get("knowledge_origin") != "GENERATED_TECHNOLOGY_PACK":
            raise ValueError("generated profile origin is missing")
        # An imported description cannot install executable capacity code.
        profile = deepcopy(profile)
        profile["id"] = technology_id
        profile["capacity_evidence"] = {
            "status": "MODEL_MISSING", "frame_model": None,
            "schedule_model": None, "requires_confirmed_device_parameters": True,
        }
        components = dict(profile.get("components") or {})
        components.update(timing_model=None, load_model=None)
        profile["components"] = components
        registries = ("_profiles", "_aliases", "_bindings", "_generators", "_validators",
                      "_encoders", "_decoders", "_load_calculators", "_timing_models")
        before = {name: dict(getattr(self, name)) for name in registries}
        try:
            if existing:
                self._aliases = {alias: owner for alias, owner in self._aliases.items() if owner != technology_id}
                for name in registries:
                    if name != "_aliases":
                        getattr(self, name).pop(technology_id, None)
            self.register_defaults([profile])
        except Exception:
            # Validation and alias failures must leave the previously registered
            # profile, its aliases and all executable components usable.
            for name, values in before.items():
                setattr(self, name, values)
            raise

    def register_binding(self, technology_id: str, binding: Any) -> None:
        self._bindings[self.normalize_id(technology_id)] = binding

    def register_generator(self, technology_id: str, generator: Any) -> None:
        self._generators[self.normalize_id(technology_id)] = generator

    def register_validator(self, technology_id: str, validator: Any) -> None:
        self._validators.setdefault(self.normalize_id(technology_id), []).append(validator)

    def register_encoder(self, technology_id: str, encoder: Any) -> None:
        self._encoders[self.normalize_id(technology_id)] = encoder

    def register_decoder(self, technology_id: str, decoder: Any) -> None:
        self._decoders[self.normalize_id(technology_id)] = decoder

    def register_load_calculator(self, technology_id: str, calculator: Any) -> None:
        self._load_calculators[self.normalize_id(technology_id)] = calculator

    def register_timing_model(self, technology_id: str, timing_model: Any) -> None:
        self._timing_models[self.normalize_id(technology_id)] = timing_model

    def register_defaults(self, definitions: Iterable[dict[str, Any]]) -> None:
        for raw in definitions:
            technology_id = self.normalize_id(raw["id"])
            profile = {**raw, "capabilities": TechnologyCapability(**raw.get("capabilities", {})).to_dict()}
            self.register_profile(technology_id, profile)
            status = ImplementationStatus(profile["implementation_status"])
            if status in {ImplementationStatus.IMPLEMENTED, ImplementationStatus.PARTIAL, ImplementationStatus.EXPERIMENTAL, ImplementationStatus.LEGACY}:
                binding = TechnologyBindingAdapter(technology_id, self.validate_binding_stack)
                self.register_binding(technology_id, binding)
                self.register_generator(technology_id, TechnologyTransportGenerator(technology_id, profile["transport_unit"], profile.get("max_payload_bytes")))
                self.register_validator(technology_id, TechnologyValidator(technology_id, profile))
                self.register_encoder(technology_id, IdentityEncoder())
                self.register_decoder(technology_id, IdentityDecoder())
                # Generic payload-plus-overhead arithmetic is not a technology
                # timing model. Only profiles backed by a capacity branch expose
                # these adapters to callers.
                if (profile.get("capacity_evidence") or {}).get("status") == "MODEL_AVAILABLE":
                    timing = TechnologyTimingModel(technology_id, profile)
                    self.register_timing_model(technology_id, timing)
                    self.register_load_calculator(technology_id, TechnologyLoadCalculator(technology_id, timing))

    def get_capabilities(self, technology_id: str) -> dict[str, bool]:
        return deepcopy(self.profile(technology_id)["capabilities"])

    def profile(self, technology_id: str) -> dict[str, Any]:
        key = self.normalize_id(technology_id)
        if key not in self._profiles:
            raise KeyError(f"unknown technology: {key}")
        return self._profiles[key].to_dict()

    def profiles(self) -> list[dict[str, Any]]:
        return [self._profiles[key].to_dict() for key in sorted(self._profiles)]

    def list_all(self) -> list[dict[str, Any]]:
        """Enumerate canonical definitions without implying verified projects."""
        return self.profiles()

    def resolve_stack(self, stack: str | Iterable[str]) -> dict[str, Any]:
        ids = tuple(self.normalize_id(item) for item in ([stack] if isinstance(stack, str) else stack))
        stack_model = TechnologyStack(ids)
        profiles = [self.profile(item) for item in ids]
        layers = [LAYER_ORDER[profile["layer"]] for profile in profiles]
        if layers != sorted(layers):
            raise ValueError(f"technology stack layers are not ordered: {ids}")
        top = ids[-1]
        return {
            "stack": stack_model,
            "profiles": profiles,
            "binding": self.resolve_binding(ids),
            "generator": self.resolve_generator(ids),
            "validators": self._validators.get(top, []),
            "encoder": self._encoders.get(top),
            "decoder": self._decoders.get(top),
            "timing_model": self._timing_models.get(top),
            "load_calculator": self._load_calculators.get(top),
        }

    def resolve_binding(self, stack: str | Iterable[str]) -> Any:
        ids = [self.normalize_id(item) for item in ([stack] if isinstance(stack, str) else stack)]
        for technology_id in reversed(ids):
            if technology_id in self._bindings:
                return self._bindings[technology_id]
        raise LookupError(f"no executable binding for stack: {ids}")

    def validate_binding_stack(self, technology_id: str, stack: Iterable[str]) -> tuple[str, ...]:
        """Validate an explicit choice; registry defaults are never inserted here."""
        key = self.normalize_id(technology_id)
        ids = tuple(self.normalize_id(item) for item in stack)
        if not ids or ids[-1] != key or len(ids) != len(set(ids)):
            raise ValueError("TECHNOLOGY_STACK_MISMATCH: duplicate layers or wrong binding technology")
        profiles = [self.profile(item) for item in ids]
        layers = [LAYER_ORDER[item["layer"]] for item in profiles]
        if layers != sorted(layers):
            raise ValueError("TECHNOLOGY_STACK_ORDER_INVALID: layers must be explicitly ordered")
        profile = self.profile(key)
        declared = profile.get("stack_variants") or [profile.get("default_stack") or [key]]
        variants = {tuple(self.normalize_id(item) for item in variant) for variant in declared}
        if ids not in variants:
            raise ValueError(f"TECHNOLOGY_STACK_UNVERIFIED: {ids} is not an explicitly declared stack for {key}")
        return ids

    def resolve_generator(self, stack: str | Iterable[str]) -> Any:
        ids = [self.normalize_id(item) for item in ([stack] if isinstance(stack, str) else stack)]
        for technology_id in reversed(ids):
            if technology_id in self._generators:
                return self._generators[technology_id]
        raise LookupError(f"no executable generator for stack: {ids}")

    def validate_chain(self, stack: str | Iterable[str], context: dict[str, Any]) -> list[dict[str, Any]]:
        resolved = self.resolve_stack(stack)
        findings = []
        for validator in resolved["validators"]:
            findings.extend(vars(item) for item in validator.validate(context))
        return findings

    def mechanisms(self, technology_id: str) -> dict[str, list[str]]:
        return deepcopy(self.profile(technology_id).get("mechanisms") or {})

    def physical_profile(self, technology_id: str):
        self.profile(technology_id)
        return physical_profile(self.normalize_id(technology_id))

    def validate_physical_realization(self, realization: dict[str, Any]) -> dict[str, Any]:
        technology_id = self.normalize_id(realization.get("technology_id") or realization.get("technology"))
        if technology_id not in self._profiles:
            return {"realization_id": realization.get("id"), "technology_id": technology_id,
                    "physical_layer_profile_id": None, "status": "INVALID", "findings": [{
                        "severity": "BLOCKER", "code": "TECHNOLOGY_PROFILE_MISSING",
                        "message": f"No technology profile is registered for {technology_id}",
                    }]}
        return validate_physical_realization({**realization, "technology_id": technology_id})

    def validate_parameters(self, technology_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
        key = self.normalize_id(technology_id)
        if key not in self._profiles:
            return {"technology_id": key, "status": "UNKNOWN", "findings": [{
                "stage": "TECHNOLOGY_PROFILE", "code": "TECHNOLOGY_PROFILE_MISSING",
                "message": f"No technology profile is registered for {key}", "severity": "BLOCKER",
            }]}
        profile = self._profiles[key].to_dict()
        stack = tuple(self.normalize_id(item) for item in (profile.get("default_stack") or (key,)))
        missing_stack = sorted(set(stack) - self._profiles.keys())
        if missing_stack:
            return {"technology_id": key, "status": "INVALID", "findings": [{
                "stage": "TECHNOLOGY_PROFILE", "code": "TECHNOLOGY_STACK_PROFILE_MISSING",
                "message": f"Registered stack layer is missing: {stack_id}", "severity": "BLOCKER",
            } for stack_id in missing_stack]}
        rate_fields = {"bitrate_bps", "nominal_bitrate_bps", "data_bitrate_bps"}
        supplied_rate_fields = set(parameters) & rate_fields
        stack_rate_fields = {
            field
            for stack_id in stack
            if stack_id in self._profiles
            for field in self._profiles[stack_id].rate_model.get("fields", ())
        }
        findings = [{
            "stage": "TECHNOLOGY_PARAMETERS",
            "code": "TECHNOLOGY_RATE_MODEL_MISMATCH",
            "message": f"{field} is not valid for {key} or its registered stack",
            "severity": "BLOCKER",
        } for field in sorted(supplied_rate_fields - stack_rate_fields)]
        shared_parameters = {field: value for field, value in parameters.items() if field not in rate_fields}
        for stack_id in stack:
            allowed = set(self._profiles[stack_id].rate_model.get("fields") or ()) if stack_id in self._profiles else set()
            layer_parameters = {
                **shared_parameters,
                **{field: parameters[field] for field in supplied_rate_fields & allowed},
            }
            for validator in self._validators.get(stack_id, ()):
                findings.extend(vars(item) for item in validator.validate({"parameters": layer_parameters}))
        # Validation of an empty/partial request must not certify a complete
        # physical transport. Catalog defaults are proposals, not supplied data.
        missing = sorted(stack_rate_fields - supplied_rate_fields)
        if missing and not any(item["code"] == "TECHNOLOGY_RATE_MODEL_MISMATCH" for item in findings):
            already_missing = any(item["code"] == "TECHNOLOGY_PARAMETER_INVALID" for item in findings)
            if not already_missing:
                findings.extend({
                    "stage": "TECHNOLOGY_PARAMETERS", "code": "TECHNOLOGY_PARAMETER_MISSING",
                    "message": f"{field} requires an explicit value for {key}",
                    "parameter": field, "severity": "BLOCKER",
                } for field in missing)
        required_parameters = sorted({
            field for stack_id in stack
            for field in self._profiles[stack_id].definition["required_parameters"]
        })
        for field in required_parameters:
            if field in stack_rate_fields:
                continue  # Rate validation above has stricter type/unit rules.
            value = parameters.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                findings.append({
                    "stage": "TECHNOLOGY_PARAMETERS", "code": "TECHNOLOGY_PARAMETER_MISSING",
                    "message": f"{field} requires an explicit value for {key}",
                    "parameter": field, "severity": "BLOCKER",
                })
        incomplete = findings and all(item["code"] in {
            "TECHNOLOGY_PARAMETER_MISSING", "TECHNOLOGY_PARAMETER_INVALID",
        } for item in findings)
        return {"technology_id": key,
                "status": "UNVERIFIED" if incomplete else "INVALID" if findings else "VALID",
                "findings": findings, "required_parameters": required_parameters,
                "validation_scope": "DECLARED_PROFILE_PARAMETERS",
                "required_parameter_completeness": "UNVERIFIED"}

    def change_parameters(self, previous_technology: str, target_technology: str, parameters: dict[str, Any]) -> dict[str, Any]:
        previous = self.profile(previous_technology)
        target = self.profile(target_technology)
        previous_fields = set((previous.get("rate_model") or {}).get("fields") or ())
        target_fields = set((target.get("rate_model") or {}).get("fields") or ())
        retained = {key: value for key, value in parameters.items() if key not in previous_fields or key in target_fields}
        invalidated = sorted(key for key in parameters if key in previous_fields and key not in target_fields)
        validation = self.validate_parameters(target_technology, retained)
        return {
            "technology_id": self.normalize_id(target_technology), "parameters": retained,
            "invalidated_fields": invalidated, "validation": validation,
            "dependent_status": {name: "STALE" for name in ("capacity", "timing", "routing_feasibility", "simulation", "trace_expectations")},
        }

    def audit_bindings(self, bindings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for binding in bindings:
            technology_id = binding.get("technology_profile_id") or binding.get("technology_id") or binding.get("technology")
            result = self.validate_parameters(str(technology_id or ""), dict(binding.get("parameters") or {}))
            for finding in result["findings"]:
                findings.append({**finding, "binding_id": binding.get("binding_id") or binding.get("id"), "technology_id": result["technology_id"]})
        return findings

    def summary(self) -> dict[str, Any]:
        profiles = self.profiles()
        return {
            "technology_count": len(profiles),
            "implementation_status": {
                status.value: sum(profile["implementation_status"] == status.value for profile in profiles)
                for status in ImplementationStatus
            },
            "layers": [layer.value for layer in Layer],
            "technologies": profiles,
        }


class BindingResolver:
    def __init__(self, registry: TechnologyRegistry) -> None:
        self.registry = registry

    def resolve(
        self,
        *,
        requirement: TransportRequirement,
        hardware_capabilities: Iterable[str] = (),
        domain_profile: str | None = None,
    ) -> list[dict[str, Any]]:
        hardware = {str(item).lower() for item in hardware_capabilities}
        candidates: list[dict[str, Any]] = []
        for profile in self.registry.profiles():
            if profile["implementation_status"] not in {"IMPLEMENTED", "PARTIAL", "EXPERIMENTAL", "LEGACY"}:
                continue
            if domain_profile and profile["domain"] not in {domain_profile, "generic_networking", "custom"}:
                continue
            capabilities = profile["capabilities"]
            complexity = requirement.data_complexity.upper()
            if complexity in {"IMAGE_STREAM", "POINT_CLOUD", "AUDIO_STREAM"} and not capabilities["supports_streams"]:
                continue
            if requirement.safety and not capabilities["supports_safety_profile"]:
                continue
            if requirement.redundancy and not capabilities["supports_redundancy"]:
                continue
            required_interface = str(profile.get("hardware_interface") or "").lower()
            if hardware and required_interface not in hardware:
                continue
            bitrate = int(profile.get("default_bitrate") or 0)
            if requirement.bandwidth_bps and bitrate and bitrate < requirement.bandwidth_bps:
                continue
            score = 100
            score += 15 if domain_profile == profile["domain"] else 0
            score += 10 if requirement.deterministic and profile.get("deterministic") else 0
            candidates.append({"technology_id": profile["id"], "score": score, "profile": profile})
        return sorted(candidates, key=lambda item: (-item["score"], item["technology_id"]))


class GeneratorResolver:
    def __init__(self, registry: TechnologyRegistry) -> None:
        self.registry = registry

    def resolve(self, binding: Any) -> Any:
        return self.registry.resolve_generator(binding.stack.technology_ids)
