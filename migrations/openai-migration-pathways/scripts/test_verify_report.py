"""Shared-report regressions. Evidence and approvals in fixtures are synthetic."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import evaluate_routes as engine
import verify_assessment
import verify_advisor_assessment
import verify_report as report
from test_verify_assessment import fixture as code_fixture


def fixture(root):
    (root / "summary.txt").write_text("Fictional Azure OpenAI assistant. Region and exact source model are unknown.")
    data = {
        "contract": "migration-report-v1", "mode": "discovery", "source_commit": None,
        "scope": "Fictional assistant", "limitations": "Description only; no source, account or runtime inspection.",
        "evidence": [{"id": "summary", "kind": "user_description", "path": "summary.txt", "description": "Synthetic supplied requirements"}],
        "workloads": [{"id": "assistant", "name": "Assistant", "scope_status": "confirmed", "description": "Answer questions", "evidence": ["summary"]}],
        "routes": [{"id": "generate", "workload_id": "assistant", "ai": True, "source_interface": "Azure OpenAI; API unconfirmed",
                    "purpose": "Answer questions", "rationale": "No route selected until requirements are resolved",
                    "evidence": ["summary"], "evaluation": None, "not_run_reason": "Model, API and residency requirements have not been supplied."}],
        "blockers": [{"id": "requirements", "kind": "missing_information", "finding": "Source requirements incomplete",
                      "impact": "Cannot select a supported route", "owner": "Application owner",
                      "resolution": "Supply source model, API and data boundary", "priority": "high", "status": "open",
                      "route_ids": ["generate"], "service_mapping_ids": ["model-service"], "blocks": ["route_selection"],
                      "required_tests": ["Evaluate the confirmed requirements"], "evidence": ["summary"]}],
        "orchestrations": [],
        "service_mappings": [{"id": "model-service", "workload_ids": ["assistant"], "route_ids": ["generate"],
                              "source_service": "Azure OpenAI", "target_service": "Amazon Bedrock, route unresolved",
                              "source_evidence_state": "reported", "pattern": "replace", "decision": "conditional",
                              "rationale": "Target requested; exact model and API still require evaluation.",
                              "required_changes": ["Confirm source contract before designing adapter"], "dependencies": [], "evidence": ["summary"]}],
        "empty_reasons": {"orchestrations": "Existing tools and state were not described; orchestration requirements remain unresolved."},
    }
    (root / "assessment.md").write_text("# Fictional discovery assessment\n\n" + "\n\n".join(
        "## " + title + "\n\nDescription-based example. Scope and missing inputs remain explicit."
        for title in report.HEADINGS) + "\n")
    return data


def orchestration():
    return {"id": "retrieval", "name": "Application retrieval", "origin": "proposed", "acceptance": "proposed",
            "implementation_status": "design_only", "route_ids": ["generate"], "service_mapping_ids": ["model-service"],
            "blocker_ids": ["requirements"], "control_flow": ["Authorize document scope", "Retrieve permitted snippets"],
            "state": "Application owns tool transcript", "permissions": "Enforce tenant filter",
            "failure_handling": "Fail closed on permission or retrieval failure", "behavior_difference": "Ranking and citations may differ",
            "required_tests": ["Reject cross-tenant access"], "evidence": ["summary"]}


class ReportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.data = fixture(self.root)

    def save(self):
        (self.root / "report-contract.json").write_text(json.dumps(self.data))

    def check(self):
        return report.validate(self.root, self.data, historical=True)

    def reject(self, message):
        with self.assertRaisesRegex(ValueError, message):
            self.check()

    def evaluated(self, features):
        target = self.root / "compatibility"
        target.mkdir(exist_ok=True)
        shutil.copytree(engine.DEFAULT_REGISTRY.parent, target / "data")
        registry = report.load(target / "data/capabilities.json")
        req = {"models": ["GPT-6.1 Sol"], "entry_regions": ["us-east-1"], "geography": "US",
               "apis": ["responses"], "required_features": features}
        if "independent_guardrail" in features:
            req["allow_orchestration"] = True
        result = engine.evaluate(registry, req, registry["snapshot_date"])
        for name, obj in [("requirements", req), ("evaluation", result)]:
            (target / (name + ".json")).write_text(json.dumps(obj))
        route = self.data["routes"][0]
        route.pop("not_run_reason")
        candidate = next(c for c in result["results"] if c["route"]["api"] == "responses"
                         and c["route"]["endpoint"] == "bedrock-runtime" and c["route"]["inference_mode"] == "geographic")
        route["evaluation"] = {"registry": "compatibility/data/capabilities.json", "requirements": "compatibility/requirements.json",
                               "evaluation": "compatibility/evaluation.json", "selected_candidate_id": candidate["route_id"]}
        return result

    def test_render_then_verify(self):
        self.save()
        report.audit(self.root, render=True)
        report.audit(self.root)
        text = (self.root / "assessment.md").read_text()
        self.assertIn("Central gap and blocker register", text)
        self.assertIn("Azure OpenAI / reported", text)

    def test_fabricated_discovery_commit(self):
        self.data["source_commit"] = "a" * 40
        self.reject("invent a repository")

    def test_false_discovery_inspection(self):
        self.data["evidence"][0]["kind"] = "repository"
        self.reject("cannot claim repository")

    def test_missing_collection(self):
        self.data.pop("orchestrations")
        self.reject("Missing report collection")

    def test_empty_section_needs_reason(self):
        self.data["empty_reasons"] = {}
        self.reject("Explain the empty")

    def test_unknown_mapping_reference(self):
        self.data["blockers"][0]["service_mapping_ids"] = ["invented"]
        self.reject("unknown service_mapping_ids")

    def test_unresolved_route_needs_central_gap(self):
        self.data["blockers"] = []
        self.data["empty_reasons"]["blockers"] = "Incorrectly claims no gaps."
        self.reject("central gap register")

    def test_false_cloud_confirmation(self):
        self.data["service_mappings"][0]["source_evidence_state"] = "cloud_confirmed"
        self.reject("cloud inventory evidence")

    def test_permission_flow_required(self):
        self.data["orchestrations"] = [orchestration()]
        self.data["orchestrations"][0].pop("permissions")
        self.reject("missing substantive")

    def test_unaccepted_implementation(self):
        self.data["orchestrations"] = [orchestration()]
        self.data["orchestrations"][0]["implementation_status"] = "implemented"
        self.reject("accepted design")

    def test_verified_needs_validation_evidence(self):
        o = orchestration()
        o.update(origin="existing", acceptance="not_required", implementation_status="verified",
                 implementation_paths=["summary.txt"])
        self.data["orchestrations"] = [o]
        self.reject("validation_evidence")

    def test_resolved_gap_needs_evidence(self):
        self.data["blockers"][0]["status"] = "resolved"
        self.reject("resolution_evidence")

    def test_unsafe_artifact_path(self):
        self.data["evidence"][0]["path"] = "../outside.txt"
        self.reject("Unsafe report")

    def test_native_gap_survives_proposed_redesign(self):
        self.evaluated(["hosted_file_search"])
        self.data["orchestrations"] = [orchestration()]
        self.assertEqual(self.check()["generate"]["status"], "NO")

    def test_edited_evaluation_rejected(self):
        self.evaluated(["structured_outputs"])
        path = self.root / "compatibility/evaluation.json"
        obj = report.load(path)
        obj["summary"]["YES"] += 1
        path.write_text(json.dumps(obj))
        self.reject("unreproducible")

    def test_orchestrated_requires_design(self):
        self.evaluated(["independent_guardrail"])
        self.reject("accepted orchestration")
        o = orchestration()
        o.update(acceptance="accepted", acceptance_evidence=["summary"])
        self.data["orchestrations"] = [o]
        self.assertEqual(self.check()["generate"]["status"], "ORCHESTRATED")

    def test_stale_table_rejected(self):
        self.save()
        report.audit(self.root, render=True)
        self.data["blockers"][0]["owner"] = "Different owner"
        self.save()
        with self.assertRaisesRegex(ValueError, "missing/stale"):
            report.audit(self.root)

    def test_current_freshness_separate_from_historical_replay(self):
        self.evaluated(["structured_outputs"])
        class LaterClock:
            @staticmethod
            def now(tz=None):
                return datetime(2027, 10, 14, tzinfo=timezone.utc)
        with patch.object(engine, "datetime", LaterClock):
            self.check()
            with self.assertRaisesRegex(ValueError, "Stale route evidence"):
                report.validate(self.root, self.data)

    def test_no_ai_explained_without_fake_model(self):
        self.data["routes"][0].update(ai=False, source_interface="Static page")
        self.data["routes"][0].pop("not_run_reason")
        self.data["blockers"] = []
        self.data["empty_reasons"]["blockers"] = "No blocking requirement identified within supplied static-page scope."
        self.assertEqual(self.check()["generate"]["status"], "NOT_APPLICABLE")

    def test_missing_main_section(self):
        self.save()
        path = self.root / "assessment.md"
        path.write_text(path.read_text().replace("## Azure-to-AWS service mapping", "## Omitted"))
        with self.assertRaisesRegex(ValueError, "Missing/duplicate report section"):
            report.audit(self.root, render=True)


class CodeReportTests(unittest.TestCase):
    setUp = ReportTests.setUp
    save = ReportTests.save
    def prepare_code(self):
        code = code_fixture(self.root)
        self.model_template = copy.deepcopy(code["models"][0])
        code["assessment_revision"] = 3
        code["evidence_policy"] = "repository_only"
        code["models"] = []
        ai = code["routes"][1]
        ai.update(model_ref=None, target_gap="Source-only review; exact route unresolved",
                  route_selection={"selected_candidate_id": None, "rationale": "Evidence restriction",
                                   "tradeoffs": "No target compatibility claim", "alternatives": [],
                                   "next_validation": "Review official documentation when permitted"})
        ai["gaps"] = [{"id": m["feature"], "feature": m["feature"], "kind": "application",
                      "affected_files": ["app.py:8"], "evidence": ["evidence/source.txt"],
                      "proposed_change": "Port adapter contract", "control_flow": "Validate input and output",
                      "state": "No managed history assumed", "failure_handling": "Explicit bounded failure",
                      "behavior_difference": "Unverified parity", "required_tests": ["Contract tests"],
                      "implementation_status": "design_only"} for m in ai["feature_mapping"]]
        self.data.update(mode="code_assessment", source_commit=code["source_commit"])
        self.data["evidence"].append({"id": "source", "kind": "repository", "path": "evidence/source.txt",
                                      "description": "Synthetic fixture source"})
        extra = copy.deepcopy(self.data["routes"][0])
        extra.update(id="http-answer", ai=False, source_interface="POST /answer")
        extra.pop("not_run_reason")
        self.data["routes"].append(extra)
        self.data["blockers"][0]["assessment_gap_refs"] = ["generate:" + g["id"] for g in ai["gaps"]]
        (self.root / "assessment-contract.json").write_text(json.dumps(code))
        compat = self.root / "compatibility"
        compat.mkdir()
        (compat / "index.json").write_text(json.dumps([{"ai_role_id": "generate", "not_run_reason": self.data["routes"][0]["not_run_reason"]}]))
        self.save()
        return code

    def prepare_evaluated_code(self):
        code = self.prepare_code()
        result = ReportTests.evaluated(self, ["structured_outputs"])
        entry = self.data["routes"][0]["evaluation"]
        candidate = next(c for c in result["results"] if c["route_id"] == entry["selected_candidate_id"])
        model = self.model_template
        model.update({k: candidate["route"][k] for k in
                      ("model_id", "region", "endpoint", "base_url", "inference_path", "api")})
        model["name"] = candidate["route"]["model_name"]
        code.update(models=[model], evidence_policy="repository_and_official_docs")
        code["routes"][1].update(model_ref=model["id"], target_gap="")
        code["routes"][1]["route_selection"]["selected_candidate_id"] = entry["selected_candidate_id"]
        index = {"ai_role_id": "generate", **{k: entry[k] for k in ("registry", "requirements", "evaluation")}}
        (self.root / "compatibility/index.json").write_text(json.dumps([index]))
        (self.root / "assessment-contract.json").write_text(json.dumps(code))
        self.save()
        return code

    def test_code_revision_three_integration(self):
        self.prepare_code()
        verify_assessment.audit(self.root, render=True)
        verify_assessment.audit(self.root)
        self.assertEqual(verify_assessment.HEADINGS, report.HEADINGS)

    def test_code_missing_gap_binding(self):
        self.prepare_code()
        self.data["blockers"][0]["assessment_gap_refs"] = []
        self.save()
        with self.assertRaisesRegex(ValueError, "Code gaps missing"):
            verify_assessment.audit(self.root, render=True)

    def test_code_missing_route_binding(self):
        self.prepare_code()
        self.data["routes"].pop()
        self.save()
        with self.assertRaisesRegex(ValueError, "every code-assessment route"):
            verify_assessment.audit(self.root, render=True)

    def test_evaluated_code_end_to_end(self):
        self.prepare_evaluated_code()
        verify_assessment.audit(self.root, render=True, historical=True)
        verify_advisor_assessment.audit(self.root, historical=True)

    def test_code_selected_candidate_cannot_diverge(self):
        self.prepare_evaluated_code()
        self.data["routes"][0]["evaluation"]["selected_candidate_id"] = None
        self.save()
        with self.assertRaisesRegex(ValueError, "Shared selected candidate differs"):
            verify_assessment.audit(self.root, render=True, historical=True)

    def test_canonical_deployment_service_mapping_cannot_diverge(self):
        code = self.prepare_code()
        (self.root / "service-mapping.json").write_text(json.dumps({"entries": self.data["service_mappings"]}))
        report.validate(self.root, self.data, assessment=code, package=True, historical=True)
        self.data["service_mappings"][0]["target_service"] = "A different target"
        with self.assertRaisesRegex(ValueError, "Shared/deployment service mappings differ"):
            report.validate(self.root, self.data, assessment=code, package=True, historical=True)


if __name__ == "__main__":
    unittest.main()
