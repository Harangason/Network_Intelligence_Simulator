from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bus_technologies import BUILTIN_TECHNOLOGIES, catalog_summary, resolve_technology, technology_registry
from communication_simulator import CONFIG_SCHEMA, CommunicationSimulator, run_simulation
from hardware_profile import (
    HardwareProfileService,
    hardware_profile_summary,
    normalize_hardware_config,
    validate_hardware_profile,
)
from physic_lib.Industries.generator_base import BaseTechnologyGenerator
from physic_lib.Industries.registry import TechnologyRegistry
from universal_trace import UniversalTraceGenerator, generate_universal_events


class TechnologyRegistryTests(unittest.TestCase):
    def test_industry_generators_are_structured_and_complete(self) -> None:
        registry = TechnologyRegistry()
        generated_ids = {
            technology_id
            for generator in registry.generators
            for technology_id in generator.generate()
        }

        self.assertEqual(len(registry.generators), 10)
        self.assertTrue(all(isinstance(generator, BaseTechnologyGenerator) for generator in registry.generators))
        self.assertEqual(generated_ids, set(BUILTIN_TECHNOLOGIES))
        self.assertEqual(len(generated_ids), 54)
        self.assertEqual(
            {item["domain"] for item in registry.summary()["generators"]},
            {
                "automotive",
                "industrial_automation",
                "embedded_systems",
                "aerospace",
                "rail",
                "marine",
                "building_automation",
                "energy",
                "robotics_ros",
                "generic_networking",
            },
        )

    def test_builtin_catalog_covers_major_bus_families(self) -> None:
        summary = catalog_summary()

        self.assertGreaterEqual(summary["technology_count"], 50)
        for technology in (
            "can_fd",
            "lin",
            "flexray",
            "ethercat",
            "i2c",
            "arinc429",
            "mil_std_1553",
            "spacewire",
            "mvb",
            "nmea2000",
            "knx",
            "dds_rtps",
        ):
            self.assertIn(technology, summary["technologies"])

    def test_custom_technology_profile_is_first_class(self) -> None:
        registry = technology_registry(
            [
                {
                    "id": "vendor_bus_x",
                    "family": "custom",
                    "medium": "fiber",
                    "topology": "ring",
                    "access": "time_triggered",
                    "addressing": "node_id",
                    "max_payload_bytes": 128,
                }
            ]
        )

        profile = resolve_technology("vendor_bus_x", registry)
        self.assertTrue(profile["custom"])
        self.assertEqual(profile["medium"], "fiber")
        self.assertFalse(profile.get("requires_profile", False))


class HardwareProfileTests(unittest.TestCase):
    def test_class_api_matches_compatibility_facade(self) -> None:
        source = {"networks": [{"id": "bus", "technology": "can"}]}
        service = HardwareProfileService()

        self.assertEqual(service.normalize(source), normalize_hardware_config(source))

    def test_hardware_port_interface_network_chain_is_preserved(self) -> None:
        source = {
            "networks": [{"id": "plant_bus", "technology": "profinet"}],
            "hardware": [
                {
                    "id": "plc",
                    "type": "controller",
                    "vendor": "external",
                    "ports": [
                        {
                            "id": "eth0",
                            "physical_type": "ethernet",
                            "network_interfaces": [
                                {
                                    "id": "plc_profinet",
                                    "technology": "profinet",
                                    "network": "plant_bus",
                                    "ipv4": "10.0.0.10/24",
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        profile = normalize_hardware_config(source)
        summary = hardware_profile_summary(profile)
        validation = validate_hardware_profile(profile)

        self.assertEqual(profile["hardware"][0]["vendor"], "external")
        self.assertEqual(profile["hardware"][0]["ports"][0]["network_interfaces"][0]["ipv4"], "10.0.0.10/24")
        self.assertEqual(summary["ports"], 1)
        self.assertEqual(summary["network_interfaces"], 1)
        self.assertTrue(validation["valid"])

    def test_unknown_network_is_reported_without_source_mutation(self) -> None:
        source = {
            "hardware": [
                {
                    "id": "ecu",
                    "ports": [
                        {
                            "id": "can1",
                            "interfaces": [{"id": "ecu_can", "protocol": "can_fd", "bus": "missing_bus"}],
                        }
                    ],
                }
            ]
        }
        original = json.dumps(source, sort_keys=True)

        profile = normalize_hardware_config(source)
        validation = validate_hardware_profile(profile)

        self.assertFalse(validation["valid"])
        self.assertIn("unknown_network", {item["code"] for item in validation["findings"]})
        self.assertEqual(json.dumps(source, sort_keys=True), original)

    def test_port_capability_and_bitrate_mismatch_are_errors(self) -> None:
        profile = normalize_hardware_config(
            {
                "networks": [{"id": "fast_can", "technology": "can_fd", "data_bitrate": 5_000_000}],
                "hardware": [
                    {
                        "id": "legacy_ecu",
                        "ports": [
                            {
                                "id": "can1",
                                "capabilities": {
                                    "classic_can": True,
                                    "can_fd": False,
                                    "max_data_bitrate": 1_000_000,
                                },
                                "interfaces": [
                                    {"id": "legacy_can_if", "technology": "can_fd", "network": "fast_can"}
                                ],
                            }
                        ],
                    }
                ],
            }
        )

        validation = validate_hardware_profile(profile)
        codes = {item["code"] for item in validation["findings"]}

        self.assertFalse(validation["valid"])
        self.assertIn("unsupported_port_technology", codes)
        self.assertIn("port_bitrate_exceeded", codes)


class UniversalSimulationTests(unittest.TestCase):
    def test_class_based_simulator_and_trace_generator_are_available(self) -> None:
        self.assertIsInstance(CommunicationSimulator(), CommunicationSimulator)
        self.assertIsInstance(UniversalTraceGenerator(), UniversalTraceGenerator)

    def test_every_builtin_technology_can_generate_neutral_events(self) -> None:
        networks = []
        node_a_ports = []
        node_b_ports = []
        for technology in BUILTIN_TECHNOLOGIES:
            network_id = f"net_{technology}"
            networks.append({"id": network_id, "technology": technology})
            node_a_ports.append(
                {
                    "id": f"a_{technology}",
                    "interfaces": [
                        {"id": f"a_if_{technology}", "technology": technology, "network": network_id}
                    ],
                }
            )
            node_b_ports.append(
                {
                    "id": f"b_{technology}",
                    "interfaces": [
                        {"id": f"b_if_{technology}", "technology": technology, "network": network_id}
                    ],
                }
            )
        config = {
            "duration_s": 0.001,
            "networks": networks,
            "hardware": [
                {"id": "node_a", "ports": node_a_ports},
                {"id": "node_b", "ports": node_b_ports},
            ],
        }
        profile = normalize_hardware_config(config)

        _, events = generate_universal_events(config, profile, start_utc=0)

        self.assertEqual(
            {event["technology"] for event in events},
            set(BUILTIN_TECHNOLOGIES),
        )

    def test_non_can_and_custom_technologies_generate_events(self) -> None:
        config = {
            "duration_s": 0.1,
            "seed": 7,
            "technology_profiles": [
                {
                    "id": "vendor_bus_x",
                    "family": "custom",
                    "medium": "fiber",
                    "topology": "ring",
                    "access": "time_triggered",
                    "addressing": "node_id",
                    "max_payload_bytes": 16,
                }
            ],
            "networks": [
                {"id": "avionics", "technology": "arinc429"},
                {"id": "vendor", "technology": "vendor_bus_x"},
            ],
            "hardware": [
                {
                    "id": "node_a",
                    "ports": [
                        {"id": "a_arinc", "interfaces": [{"id": "a_arinc_if", "technology": "arinc429", "network": "avionics"}]},
                        {"id": "a_vendor", "interfaces": [{"id": "a_vendor_if", "technology": "vendor_bus_x", "network": "vendor"}]},
                    ],
                },
                {
                    "id": "node_b",
                    "ports": [
                        {"id": "b_arinc", "interfaces": [{"id": "b_arinc_if", "technology": "arinc429", "network": "avionics"}]},
                        {"id": "b_vendor", "interfaces": [{"id": "b_vendor_if", "technology": "vendor_bus_x", "network": "vendor"}]},
                    ],
                },
            ],
        }
        profile = normalize_hardware_config(config)

        routes, events = generate_universal_events(config, profile, start_utc=0)

        self.assertEqual({route["technology"] for route in routes}, {"arinc429", "vendor_bus_x"})
        self.assertEqual({event["technology"] for event in events}, {"arinc429", "vendor_bus_x"})
        vendor_events = [event for event in events if event["technology"] == "vendor_bus_x"]
        self.assertTrue(vendor_events)
        self.assertTrue(all(event["payload_bytes"] <= 16 for event in vendor_events))

    def test_primary_api_writes_clean_standalone_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                "schema": CONFIG_SCHEMA,
                "output_dir": temp_dir,
                "duration_s": 0.05,
                "formats": ["universal-jsonl", "universal-csv"],
                "networks": [{"id": "serial_bus", "technology": "rs485"}],
                "hardware": [
                    {"id": "controller", "ports": [{"id": "rs485_a", "interfaces": [{"id": "controller_if", "technology": "rs485", "network": "serial_bus"}]}]},
                    {"id": "device", "ports": [{"id": "rs485_b", "interfaces": [{"id": "device_if", "technology": "rs485", "network": "serial_bus"}]}]},
                ],
            }

            result = run_simulation(config)

            self.assertEqual(result["status"], "completed")
            self.assertTrue(result["standalone"])
            self.assertGreater(result["trace"]["events"], 0)
            self.assertTrue((Path(temp_dir) / "traces" / "universal_trace.jsonl").is_file())
            self.assertTrue((Path(temp_dir) / "traces" / "universal_trace.csv").is_file())
            self.assertTrue((Path(temp_dir) / "generation_manifest.json").is_file())
            self.assertTrue((Path(temp_dir) / "simulation_result.json").is_file())

    def test_generic_fault_model_marks_dropped_events(self) -> None:
        config = {
            "duration_s": 0.05,
            "networks": [
                {
                    "id": "fieldbus",
                    "technology": "modbus_rtu",
                    "fault_model": {"dropout_probability": 1.0},
                }
            ],
            "hardware": [
                {"id": "master", "ports": [{"id": "a", "interfaces": [{"id": "master_if", "technology": "modbus_rtu", "network": "fieldbus"}]}]},
                {"id": "slave", "ports": [{"id": "b", "interfaces": [{"id": "slave_if", "technology": "modbus_rtu", "network": "fieldbus"}]}]},
            ],
        }
        profile = normalize_hardware_config(config)

        _, events = generate_universal_events(config, profile, start_utc=0)

        self.assertTrue(events)
        self.assertEqual({event["status"] for event in events}, {"dropped"})


if __name__ == "__main__":
    unittest.main()
