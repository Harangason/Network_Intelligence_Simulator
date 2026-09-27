import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import markdown_system


class MarkdownSystemTests(unittest.TestCase):
    def test_inventories_structural_cases_and_preserves_unmapped_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "suite.md"
            source.write_text(
                "# Master\n## S01-A: create\nExact requirements\n"
                "A later paragraph references S02 but does not define it.\n"
                "| ID | Requirement |\n| --- | --- |\n| S03-B | validate |\n"
                "```powershell\n# S99-A: this is inert\nRemove-Item important\n```\n",
                encoding="utf-8",
            )
            report = markdown_system.inventory(source)
            self.assertEqual(["S01-A", "S03-B"], [x["test_id"] for x in report["structural_case_candidates"]])
            self.assertEqual(["S02"], report["unstructured_case_ids"])
            self.assertNotIn("S99-A", report["explicit_case_id_mentions"])
            self.assertEqual("INVENTORY_ONLY_REVIEW_REQUIRED", report["interpretation"])

    def test_markdown_preparation_is_incomplete_and_does_not_register_or_execute(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "suite.md"
            source.write_text("# S01-A: test\nRequirement\n", encoding="utf-8")
            result = markdown_system.prepare_markdown(source, root / "out")
            self.assertEqual("NEEDS_SEMANTIC_NORMALIZATION", result["status"])
            self.assertFalse(result["registered_or_executed"])
            draft = json.loads(Path(result["normalization_draft"]).read_text(encoding="utf-8"))
            self.assertEqual("INCOMPLETE_REVIEW_REQUIRED", draft["status"])
            self.assertIsNone(draft["test_cases"][0]["mutating"])
            self.assertEqual("INCOMPLETE_REQUIRES_SEMANTIC_NORMALIZATION", draft["test_cases"][0]["review_status"])

    def test_project_preparation_generates_rules_manager_intake_without_mutating_registry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            (root / "docs").mkdir(parents=True)
            (root / "docs" / "contract.md").write_text("# Contract", encoding="utf-8")
            (root / "tests").mkdir()
            result = markdown_system.prepare_project(root, root / ".tool-checker" / "docs" / "intake")
            self.assertEqual("PREPARATION_REQUIRED", result["status"])
            self.assertEqual(1, result["markdown_count"])
            content = Path(result["intake_template"]).read_text(encoding="utf-8")
            self.assertIn("Rules-Manager-Prüfung", content)
            self.assertIn("BLOCKED", content)

    def test_ab_variants_are_cases_but_parent_scenario_is_a_family(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "suite.md"
            source.write_text("## S01 — family\n### S01-A — typed\nA requirements\n### S01-B — untyped\nB requirements\n", encoding="utf-8")
            report = markdown_system.inventory(source)
            self.assertEqual(["S01-A", "S01-B"], [row["test_id"] for row in report["structural_case_candidates"]])
            self.assertEqual("S01", report["scenario_families"][0]["family_id"])
            self.assertEqual([], report["unstructured_case_ids"])
            self.assertEqual([2, 3], report["structural_case_candidates"][0]["source_lines"])


if __name__ == "__main__":
    unittest.main()
