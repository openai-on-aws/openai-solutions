#!/usr/bin/env python3
"""Verify original code assessment plus reproducible per-role route evaluations."""
import argparse
import json
from pathlib import Path
import evaluate_routes
import verify_assessment


def local(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Compatibility artifact escapes assessment directory")
    return path


def audit(root, historical=False):
    verify_assessment.audit(root, historical=historical)
    data = json.loads((root / "assessment-contract.json").read_text())
    roles = {r["id"]: r for r in data["routes"] if r["kind"] == "ai_call"}
    if not roles:
        return
    entries = json.loads((root / "compatibility/index.json").read_text())
    if len(entries) != len(roles) or {x["ai_role_id"] for x in entries} != set(roles):
        raise ValueError("Compatibility index must cover every AI role exactly once")
    models = {m["id"]: m for m in data["models"]}
    normalize = lambda value: value.lower().replace(" ", "_").replace("/", "_")
    for entry in entries:
        if data["evidence_policy"] == "repository_only" and entry.get("not_run_reason"):
            continue
        if data.get("assessment_revision", 1) >= 2 and not entry.get("registry"):
            raise ValueError("New assessments must pin a local registry and its snapshots")
        registry_path = local(root, entry["registry"]) if entry.get("registry") else evaluate_routes.DEFAULT_REGISTRY
        registry = json.loads(registry_path.read_text())
        evaluate_routes.validate_registry(registry, registry_path.parent)
        requirements = json.loads(local(root, entry["requirements"]).read_text())
        saved = json.loads(local(root, entry["evaluation"]).read_text())
        actual = evaluate_routes.evaluate(registry, requirements, saved["evaluated_at"])
        if saved != actual:
            raise ValueError("Route evaluation changed or was edited; regenerate with current evidence/date")
        if not historical:
            current = evaluate_routes.evaluate(registry, requirements)
            if saved["evaluated_at"] > current["evaluated_at"]:
                raise ValueError("Evaluation is future-dated")
            if current["results"] != actual["results"]:
                raise ValueError("Historical evaluation reproduces, but current evidence or claims require refresh")
        role = roles[entry["ai_role_id"]]
        if role["model_ref"] is None:
            continue  # Existing validator requires an explicit target gap.
        model = models[role["model_ref"]]
        matches = [r for r in actual["results"] if
                   all(r["route"][key] == model[key] for key in ("model_id", "region", "endpoint", "base_url", "inference_path"))
                   and normalize(r["route"]["api"]) == normalize(model["api"])]
        if data.get("assessment_revision", 1) >= 2:
            selected = role["route_selection"]["selected_candidate_id"]
            matches = [r for r in matches if r["route_id"] == selected]
        if not matches:
            raise ValueError("Selected model/API/path/Region missing from evaluated candidates")
        if all(r["status"] == "NO" for r in matches) and model["verification"] != "blocked":
            raise ValueError("Selected route violates requirements; mark blocked or revise the accepted requirements")
    print("Advisor compatibility checks passed; account access and runtime behavior are not certified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--historical", action="store_true", help="Reproduce the saved date; does not certify current compatibility")
    args = parser.parse_args()
    audit(args.directory, args.historical)
