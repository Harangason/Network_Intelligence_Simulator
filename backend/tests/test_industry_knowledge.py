from __future__ import annotations

import sqlite3
import sys
import tempfile
import types
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from industry_knowledge import (
    IndustryContext,
    IndustryKnowledgeService,
    IndustryMemoryStore,
    KnowledgeGraphStore,
)


class IndustryContextTests(unittest.TestCase):
    def test_aliases_resolve_to_existing_domain_folder_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self.assertEqual(IndustryContext.resolve("industrial", root=root).name, "IndustrialAutomation")
            self.assertEqual(IndustryContext.resolve("ros2", root=root).name, "RoboticsROS")
            self.assertEqual(IndustryContext.resolve("afdx", root=root).name, "Afdx")

    def test_request_domain_controls_both_storage_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            context = IndustryContext.from_request(
                {"scenario": {"industry": "Aerospace", "domain": "automotive"}},
                root=Path(temp_dir),
            )

            self.assertEqual(context.name, "Aerospace")
            self.assertEqual(
                context.memory_path,
                Path(temp_dir) / "Aerospace" / "Learning" / "simulation_memory.db",
            )
            self.assertEqual(
                context.graph_path,
                Path(temp_dir) / "Aerospace" / "Knowledge" / "knowledge_graph.db",
            )


class IndustryMemoryStoreTests(unittest.TestCase):
    def _values(self, prompt: str) -> dict[str, object]:
        return {
            "created_utc": "2026-07-23T00:00:00Z",
            "prompt": prompt,
            "project_profile": "test",
            "maneuver_profile": "generic",
            "package_mode": "mixed",
            "signal_value_strategy": "calculated",
        }

    def test_memories_are_isolated_by_industry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            aerospace = IndustryMemoryStore(IndustryContext.resolve("aerospace", root=root))
            automotive = IndustryMemoryStore(IndustryContext.resolve("automotive", root=root))

            aerospace.insert(self._values("flight control"))
            automotive.insert(self._values("body control"))

            self.assertEqual([row["prompt"] for row in aerospace.recent()], ["flight control"])
            self.assertEqual([row["prompt"] for row in automotive.recent()], ["body control"])
            self.assertNotEqual(aerospace.path, automotive.path)

    def test_legacy_lowercase_learning_database_is_copied_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            context = IndustryContext.resolve("aerospace", root=root)
            legacy = context.directory / "learning" / "simulation_memory.db"
            legacy.parent.mkdir(parents=True)
            with closing(sqlite3.connect(legacy)) as connection:
                with connection:
                    connection.execute("CREATE TABLE marker (value TEXT)")
                    connection.execute("INSERT INTO marker VALUES ('preserved')")

            store = IndustryMemoryStore(context)
            store.ensure()

            with closing(sqlite3.connect(store.path)) as connection:
                value = connection.execute("SELECT value FROM marker").fetchone()[0]
            self.assertEqual(value, "preserved")
            self.assertTrue(legacy.exists())


class KnowledgeGraphStoreTests(unittest.TestCase):
    def test_simulation_topology_is_persisted_as_nodes_and_edges(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            context = IndustryContext.resolve("aerospace", root=Path(temp_dir))
            service = IndustryKnowledgeService(context)
            memory_id = service.memory.insert(
                {
                    "created_utc": "2026-07-23T00:00:00Z",
                    "prompt": "AFDX flight control",
                    "project_profile": "flight_control",
                    "maneuver_profile": "generic",
                    "package_mode": "ethernet",
                    "signal_value_strategy": "calculated",
                }
            )
            request = {
                "scenario": {
                    "industry": "Aerospace",
                    "project_profile": "flight_control",
                    "maneuver_profile": "generic",
                    "description": "AFDX flight control",
                },
                "package_mode": "ethernet",
                "networks": [{"id": "afdx_a", "technology": "arinc664_afdx"}],
                "hardware": [
                    {
                        "id": "flight_control_computer",
                        "ports": [
                            {
                                "id": "eth0",
                                "network_interfaces": [
                                    {
                                        "id": "fcc_afdx",
                                        "technology": "arinc664_afdx",
                                        "network": "afdx_a",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "communications": [
                    {
                        "id": "flight_state",
                        "sender_interface": "fcc_afdx",
                        "receivers": ["display_afdx"],
                    }
                ],
            }

            run_id = service.graph.record_simulation(memory_id, request)

            involved = service.graph.neighbors(run_id, relation="INVOLVES")
            networks = service.graph.neighbors(run_id, relation="USES_NETWORK")
            self.assertEqual([node["node_key"] for node in involved], ["flight_control_computer"])
            self.assertEqual([node["node_key"] for node in networks], ["afdx_a"])
            self.assertEqual(
                service.graph.neighbors("network:afdx_a", relation="USES_TECHNOLOGY")[0]["node_key"],
                "arinc664_afdx",
            )

    def test_graph_database_is_industry_local(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            graph = KnowledgeGraphStore(IndustryContext.resolve("energy", root=root))

            graph.ensure()

            self.assertEqual(
                graph.path,
                root / "Energy" / "Knowledge" / "knowledge_graph.db",
            )
            self.assertTrue(graph.path.is_file())


class NemotronKnowledgeIntegrationTests(unittest.TestCase):
    def test_recording_uses_industry_from_request(self) -> None:
        try:
            import openai  # noqa: F401
            openai_patch = {}
        except ModuleNotFoundError:
            openai_module = types.ModuleType("openai")
            openai_module.OpenAI = type(
                "OpenAI",
                (),
                {"__init__": lambda self, *args, **kwargs: None},
            )
            openai_patch = {"openai": openai_module}

        with patch.dict(sys.modules, openai_patch):
            import nemotron

            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir) / "Industries"
                request = {
                    "scenario": {
                        "industry": "Energy",
                        "project_profile": "substation",
                        "maneuver_profile": "generic",
                        "description": "IEC 61850 substation",
                    },
                    "package_mode": "ethernet",
                    "signal_value_strategy": "calculated",
                    "output_dir": str(Path(temp_dir) / "trace"),
                    "networks": [{"id": "station_bus", "technology": "iec61850"}],
                }

                with patch.object(nemotron, "INDUSTRY_PROFILE_ROOT", root):
                    memory_id = nemotron.record_simulation_learning(
                        Path(temp_dir) / "request.json",
                        request,
                    )

                self.assertEqual(memory_id, 1)
                self.assertTrue((root / "Energy" / "Learning" / "simulation_memory.db").is_file())
                self.assertTrue((root / "Energy" / "Knowledge" / "knowledge_graph.db").is_file())
                self.assertFalse((root / "Automotive" / "Learning" / "simulation_memory.db").exists())


if __name__ == "__main__":
    unittest.main()
