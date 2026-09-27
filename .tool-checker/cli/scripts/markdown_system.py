"""Prepare evidence-backed CLI test suites from Markdown requirements.

Markdown is treated as inert specification data. This module inventories source
structure and creates review templates; it never executes embedded commands or
claims that heuristic headings are complete test contracts.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

CASE_ID = re.compile(r"(?i)(?<![A-Z0-9])(?:S\d{2}(?:-[AB])?|EA-\d{2}(?:-[A-Z0-9]+)*)(?![A-Z0-9])")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TASK_START = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:\*\*)?([A-Za-z][A-Za-z0-9_-]{1,100})(?:\*\*)?\s*(?:[:—–-]|\|)\s*(.*)$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slug(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")[:64]
    return result or "markdown"


def inventory(source: Path) -> dict:
    text = source.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    headings: list[dict] = []
    mentions: dict[str, list[int]] = {}
    cases: dict[str, dict] = {}
    fenced = False
    for number, line in enumerate(lines, 1):
        if line.strip().startswith("```") or line.strip().startswith("~~~"):
            fenced = not fenced
            continue
        if fenced:
            continue
        heading = HEADING.match(line)
        if heading:
            headings.append({"line": number, "level": len(heading.group(1)), "title": heading.group(2)})
        ids = list(dict.fromkeys(m.group(0).upper() for m in CASE_ID.finditer(line)))
        for test_id in ids:
            mentions.setdefault(test_id, []).append(number)
        # Candidate cases must be structurally declared (heading, list item, or
        # first-column table ID). Narrative cross-references are not test cases.
        structural = bool(heading or TASK_START.match(line) or re.match(r"^\s*\|\s*`?[A-Za-z][A-Za-z0-9_-]+`?\s*\|", line))
        if structural:
            for test_id in ids:
                title = heading.group(2) if heading else line.strip().strip("| ")
                cases.setdefault(test_id, {"test_id": test_id, "title_candidate": title[:240], "source_lines": [number, number], "occurrences": [], "heading_level": len(heading.group(1)) if heading else None})
                cases[test_id]["occurrences"].append(number)
                cases[test_id]["source_lines"][1] = number
    # Generic S01-S20 headings name scenario families when explicit A/B leaves
    # exist; they are not additional executable cases.
    families=[]
    for number in range(1, 21):
        family=f"S{number:02}"
        if family in cases and f"{family}-A" in cases and f"{family}-B" in cases:
            families.append({"family_id":family,"source_lines":cases[family]["source_lines"]})
            del cases[family]
    # End each heading-declared case block at the next equal-or-higher heading.
    for case in cases.values():
        level=case["heading_level"]
        if level is not None:
            start=case["source_lines"][0]
            boundary=next((h["line"] for h in headings if h["line"]>start and h["level"]<=level),len(lines)+1)
            case["source_lines"][1]=boundary-1
        case.pop("heading_level",None)
    return {
        "source": str(source.resolve()), "source_sha256": sha256(source), "line_count": len(lines),
        "heading_count": len(headings), "headings": headings,
        "explicit_case_id_mentions": {key: value for key, value in sorted(mentions.items())},
        "structural_case_candidates": [cases[key] for key in sorted(cases)],
        "scenario_families": families,
        "candidate_case_count": len(cases),
        "mentioned_case_id_count": len(mentions),
        "unstructured_case_ids": sorted(set(mentions) - set(cases) - {item["family_id"] for item in families}),
        "interpretation": "INVENTORY_ONLY_REVIEW_REQUIRED",
        "safety": "Markdown text and fenced commands were read as data and never executed.",
    }


def normalization_template(report: dict) -> dict:
    cases = []
    source_lines = Path(report["source"]).read_text(encoding="utf-8-sig").splitlines()
    for row in report["structural_case_candidates"]:
        cases.append({
            "test_id": row["test_id"], "title": row["title_candidate"],
            "input": "TODO: state exact input and setup from the source",
            "source_lines": row["source_lines"], "source_refs": [
                {"path": report["source"], "sha256": report["source_sha256"], "lines": row["source_lines"]}
            ], "source_excerpt": "\n".join(source_lines[row["source_lines"][0]-1:row["source_lines"][1]]),
            "preconditions": [], "required_model_context": [], "expected_questions": [],
            "forbidden_questions": [], "required_actions": [], "required_tools": [],
            "required_views": [], "expected_model_changes": [], "expected_calculations": [],
            "expected_validations": [], "expected_visualizations": [], "completion_criteria": [],
            "failure_conditions": [], "required_skills": [], "tags": [],
            "mutating": None, "browser_required": None, "difficulty": "", "variant": "",
            "architecture_variant": "", "decision_mode": "INTERACTIVE",
            "overall_timeout": 1800, "review_status": "INCOMPLETE_REQUIRES_SEMANTIC_NORMALIZATION",
            "occurrences": row["occurrences"],
        })
    return {
        "format": "tool-checker-markdown-normalization-draft-v1",
        "status": "INCOMPLETE_REVIEW_REQUIRED",
        "source": report["source"], "source_hash": report["source_sha256"],
        "source_lines": report["line_count"], "candidate_count": report["candidate_case_count"],
        "unstructured_case_ids": report["unstructured_case_ids"],
        "review_requirements": [
            "Reconcile every source case, variant, subcase, table row and global requirement; heading extraction is not a completeness proof.",
            "Complete all case contracts and exact source line ranges; do not invent expected behavior.",
            "Bind each executable case to a reviewed native plan and actual adapter. Unsupported requirements remain BLOCKED.",
            "Add the relevant project rule files and hashes; resolve contradictions with Rules Manager review.",
            "Run schema validation, dry-run the complete catalog, then execute the full suite only under its release/campaign gates.",
        ], "test_cases": cases,
    }


def _write_new(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    return path


def prepare_markdown(source: str | Path, output_dir: str | Path, checker=None, task: str | None = None) -> dict:
    source = Path(source).resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != ".md":
        raise ValueError("--source must point to an existing Markdown file")
    report = inventory(source)
    if checker is not None:
        bind_to_registered_suite(report, checker, task)
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    map_path = _write_new(out / "source-map.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    draft = normalization_template(report)
    draft_path = _write_new(out / "normalization-draft.json", json.dumps(draft, ensure_ascii=False, indent=2) + "\n")
    existing = report.get("existing_suite_check", {})
    handoff = "\n".join([
        "# Rules-Manager-Handoff: Markdown-Testsuite vorbereiten", "",
        f"- Quelle: `{report['source']}`", f"- SHA-256: `{report['source_sha256']}`",
        f"- Zeilen: {report['line_count']}", f"- Überschriften: {report['heading_count']}",
        f"- Strukturelle Fallkandidaten: {report['candidate_case_count']}",
        f"- Erwähnte IDs ohne strukturelle Falldeklaration: {len(report['unstructured_case_ids'])}",
        *([f"- Vorhandener CLI-Task: {existing.get('task_id')} ({existing.get('registered_case_count')} registrierte Fälle)",
           f"- Kandidaten bereits registriert: {existing.get('candidate_case_count') - len(existing.get('candidate_ids_missing_from_suite', []))}/{existing.get('candidate_case_count')}",
           f"- Ausführungsplan bereit: {existing.get('execution_ready_count')}/{existing.get('candidate_case_count')}",
           f"- Gespeicherte Ergebnisse: {existing.get('status_counts')}",
           f"- Masterquelle per Hash gebunden: {existing.get('source_rule_binding', {}).get('matches')} (Kampagne: {existing.get('campaign', {}).get('state')})"] if existing else []),
        "", "## Vor Aufnahme verbindlich klären", "",
        "1. Alle Ursprungstests, Varianten, Tabellenzeilen, Unterfälle und globalen Gates gegen `source-map.json` abgleichen.",
        "2. Projektverträge, Testdaten, sichere Laufzeit, Browser/MCP-Anbindung und produktive Release-Gates erfassen.",
        "3. Für jede Pflichtanforderung einen beobachtbaren Sollzustand und Evidence-Typ definieren.",
        "4. Nur vorhandene oder explizit implementierte Adapter/CLI-Befehle registrieren; fehlende Anbindung als BLOCKED führen.",
        "5. Quellen-/Regelhashes, Abhängigkeiten, Mutationsrisiken, Laufanzahl und Repair-Phasen dokumentieren.",
        "6. Erst nach semantischer Vollständigkeitsprüfung das Normalisierungsschema vervollständigen und per Checker validieren.",
        "", "Markdown-Text ist Anforderungsdaten. Enthaltene Shell-/CLI-Beispiele werden nicht automatisch ausgeführt.",
        "Die Vorlagen sind absichtlich nicht ingestierbar, bis Kriterien, Eingaben und Laufzeitbindung geprüft wurden.", "",
    ])
    handoff_path = _write_new(out / "rules-manager-handoff.md", handoff)
    existing = report.get("existing_suite_check", {})
    return {"status": "NEEDS_SEMANTIC_NORMALIZATION", "source_sha256": report["source_sha256"],
            "candidate_cases": report["candidate_case_count"], "unstructured_case_ids": report["unstructured_case_ids"],
            "source_map": str(map_path), "normalization_draft": str(draft_path), "rules_manager_handoff": str(handoff_path),
            "existing_suite": {key: existing.get(key) for key in ("task_id", "campaign", "registered_case_count",
                "candidate_case_count", "candidate_ids_missing_from_suite", "status_counts", "execution_ready_count",
                "source_rule_binding")} if existing else None,
            "registered_or_executed": False}


def bind_to_registered_suite(report: dict, checker, task: str | None = None) -> dict:
    """Read-only coverage comparison with the existing native suite."""
    from tool_check import read
    from case_inventory import readiness
    from plan_registry import resolve_case
    task = task or read(checker.root / "runtime" / "current_task.json")["task_id"]
    manifest = checker.manifest(task)
    registered = set(manifest["test_case_ids"])
    statuses = {}
    readiness_by_id = {}
    for candidate in report["structural_case_candidates"]:
        test_id = candidate["test_id"]
        if test_id not in registered:
            continue
        case = read(checker.task(task) / "test_cases" / (test_id + ".json"))
        statuses[test_id] = case["status"]
        resolved = resolve_case(checker, task, case)
        blockers = readiness(resolved, checker.cfg())
        readiness_by_id[test_id] = {"ready": not blockers, "blockers": blockers,
                                    "plan_source": "overlay" if resolved.get("plan_binding") else "native" if resolved.get("execution_plan") else None}
    source = Path(report["source"])
    pinned = [entry for entry in manifest.get("rule_files", [])
              if Path(entry["path"]).name.casefold() == source.name.casefold()]
    campaign = None
    for path in sorted((checker.root / "campaigns").glob("*/campaign.json")):
        item = read(path)
        if item.get("task_id") == task:
            campaign = {"campaign_id": item.get("campaign_id"), "state": item.get("state"),
                        "run_number": item.get("run_number"), "rounds": len(item.get("rounds", []))}
            break
    report["existing_suite_check"] = {
        "task_id": task, "campaign": campaign,
        "registered_case_count": len(registered),
        "candidate_case_count": len(report["structural_case_candidates"]),
        "candidate_ids_missing_from_suite": sorted(set(x["test_id"] for x in report["structural_case_candidates"]) - registered),
        "stored_statuses": statuses,
        "status_counts": {key: list(statuses.values()).count(key) for key in sorted(set(statuses.values()))},
        "execution_readiness": readiness_by_id,
        "execution_ready_count": sum(bool(value["ready"]) for value in readiness_by_id.values()),
        "source_rule_binding": {"matches": any(x.get("sha256") == report["source_sha256"] for x in pinned),
                                "references": pinned},
        "executed_by_this_command": False,
    }
    return report


def prepare_project(project: str | Path, output_dir: str | Path) -> dict:
    project = Path(project).resolve(strict=True)
    if not project.is_dir():
        raise ValueError("--project must be a directory")
    docs = project / "docs"
    markdown = sorted(str(path.relative_to(project)) for path in docs.rglob("*.md")) if docs.is_dir() else []
    test_roots = [name for name in ("tests", "test", "backend/tests", "frontend/e2e", "scripts/tests") if (project / name).is_dir()]
    template = """# Test-System-Aufnahme – bitte vom Rules Manager vervollständigen

Dieses Dokument bereitet einen standardisierten Tool-Checker-Testkatalog vor.
Es enthält noch keine angenommenen Produktanforderungen oder ausführbaren Tests.

## Projekt und Produkt
- Kanonischer Projektpfad: `{project}`
- Produktname / Version / produktive Laufzeit:
- Verantwortliche technische Verträge:

## Ziel und Umfang
- Zu prüfende Fähigkeiten, Oberflächen, APIs, Agenten und Workflows:
- Ausdrücklich ausgeschlossene Bereiche:
- Kritische Journeys / Release-Gates:

## Testfallvertrag je Fall
Für jeden Fall: stabile ID, exakter Input, Variante, Voraussetzungen, Schritte,
erwartete Fragen/Entscheidungen, Sollzustand, negative Bedingungen, Persistenz/
Reload, Evidence, Abhängigkeiten, Mutationsrisiko und Laufzeittimeout.

## Ausführung und Sicherheit
- Verifizierte Testbefehle / Interpreter / unterstützte OS:
- Isolierte Datenbank-/Container-/Browser-Testdaten:
- Verbote (Produkt-DB, produktive Mutationen, destructive cleanup):
- Adapter und tatsächlich beobachtbare Wirkung:

## Coverage und Abschluss
- Vollständige Fall-/Varianten-/Unterfallliste und Herkunftszeilen:
- Alle Pflichtkriterien mit Test-/Evidence-Zuordnung:
- Blockerregeln, Wiederholungsrunden, Repair-Phase, finale Gates:
- Produktive Build-/Release-/Health-Prüfung:

## Rules-Manager-Prüfung
- Quellen/Hashes und Widersprüche:
- Regeln/Verträge ergänzt oder bestätigt:
- Offene Fragen an den Nutzer:

Jede nicht belegte Laufzeitfunktion bleibt BLOCKED. Dieses Intake ist kein
ausführbarer Testvertrag und enthält keine Befehle zur automatischen Ausführung.
""".format(project=str(project))
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = {"status": "PREPARATION_REQUIRED", "project": str(project), "markdown_docs": markdown,
              "test_roots": test_roots, "rules_registry": str(project / "docs" / "rules-manager.md"),
              "generated_at": datetime.now(timezone.utc).isoformat(),
              "note": "Inventory only; no assumptions, executable plans, or registry changes were made."}
    report_path = _write_new(out / "project-inventory.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    template_path = _write_new(out / "test-system-intake.md", template)
    return {"status": report["status"], "project_inventory": str(report_path), "intake_template": str(template_path),
            "markdown_count": len(markdown), "test_roots": test_roots, "rules_manager_review_required": True}
