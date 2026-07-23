from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bus_technologies import BUILTIN_TECHNOLOGIES
from standalone_cli import (
    InteractiveStandaloneCli,
    StandaloneCliRunner,
    StandaloneSimulationOptions,
    TechnologyCatalogMenu,
    domain_for_technology,
)


class TechnologyCatalogMenuTests(unittest.TestCase):
    def test_menu_contains_every_registered_technology_once(self) -> None:
        menu = TechnologyCatalogMenu()
        technologies = [
            technology
            for _, _, domain_technologies in menu.domains
            for technology in domain_technologies
        ]

        self.assertEqual(len(menu.domains), 10)
        self.assertEqual(len(technologies), 54)
        self.assertEqual(set(technologies), set(BUILTIN_TECHNOLOGIES))

    def test_domain_is_derived_from_generator_ownership(self) -> None:
        self.assertEqual(domain_for_technology("arinc429"), "aerospace")
        self.assertEqual(domain_for_technology("ethercat"), "industrial_automation")
        self.assertEqual(domain_for_technology("ros2"), "robotics_ros")


class StandaloneSimulationOptionsTests(unittest.TestCase):
    def test_options_create_hardware_port_interface_and_fault_model(self) -> None:
        options = StandaloneSimulationOptions(
            technology="arinc429",
            industry="aerospace",
            output_dir=Path("test"),
            node_count=3,
            bitrate=100_000,
            cycle_ms=20,
            payload_bytes=4,
            max_events=123,
            dropout_probability=0.1,
            corruption_probability=0.2,
        )

        config = options.to_config()

        self.assertEqual(config["networks"][0]["technology"], "arinc429")
        self.assertEqual(config["networks"][0]["bitrate"], 100_000)
        self.assertEqual(
            config["networks"][0]["fault_model"],
            {"dropout_probability": 0.1, "corruption_probability": 0.2},
        )
        self.assertEqual(len(config["hardware"]), 3)
        self.assertEqual(
            config["hardware"][0]["ports"][0]["network_interfaces"][0]["technology"],
            "arinc429",
        )
        self.assertEqual(len(config["communications"][0]["receivers"]), 2)
        self.assertEqual(config["max_events"], 123)

    def test_interactive_dialog_collects_non_can_technology(self) -> None:
        answers = iter(
            [
                "4",  # Aerospace
                "1",  # ARINC 429
                "",   # bitrate
                "3",  # nodes
                "2.5",
                "20",
                "4",
                "7",
                "500",
                "0.1",
                "0.02",
                "",
                "flight_test",
            ]
        )
        output: list[str] = []
        cli = InteractiveStandaloneCli(
            input_function=lambda _: next(answers),
            output_function=output.append,
        )

        options = cli.collect()

        self.assertEqual(options.technology, "arinc429")
        self.assertEqual(options.industry, "aerospace")
        self.assertEqual(options.node_count, 3)
        self.assertEqual(options.duration_s, 2.5)
        self.assertEqual(options.payload_bytes, 4)
        self.assertEqual(options.output_dir, Path("flight_test"))

    def test_runner_writes_universal_trace_for_non_can_bus(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            options = StandaloneSimulationOptions(
                technology="modbus_rtu",
                industry="industrial_automation",
                output_dir=Path(temp_dir),
                formats=("universal-jsonl", "universal-csv"),
                duration_s=0.01,
                node_count=2,
                cycle_ms=10,
                payload_bytes=8,
            )

            result = StandaloneCliRunner().run(options)

            self.assertEqual(result["status"], "completed")
            self.assertGreater(result["trace"]["events"], 0)
            self.assertEqual(result["trace"]["technologies"], ["modbus_rtu"])
            self.assertTrue((Path(temp_dir) / "traces" / "universal_trace.jsonl").is_file())
            self.assertTrue((Path(temp_dir) / "traces" / "universal_trace.csv").is_file())


if __name__ == "__main__":
    unittest.main()
