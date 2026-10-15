"""Offline regression fixtures; fake model IDs are never availability claims."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

import verify_assessment as checker


def fixture(root):
    (root / "evidence").mkdir()
    (root / "evidence/source.txt").write_text("Fixture source: POST /answer calls fake_client.generate.\n")
    (root / "evidence/official.txt").write_text("Synthetic documentation fixture, not a real model claim.\n")
    model = dict(
        id="assistant-model", provider="openai", name="Synthetic test model", model_id="fixture.fake",
        region="us-east-1", endpoint="bedrock-mantle",
        base_url="https://bedrock-mantle.us-east-1.api.aws/openai/v1",
        inference_path="/openai/v1/responses", api="Responses",
        inference_geography="us-east-1 in-region fixture", rationale="Fixture decision",
        fallback_policy="Fail explicitly; no provider substitution",
        evaluation_criteria=["Validate required JSON fields and refusals"],
        verification="unverified", verification_notes="Synthetic fixture; never queried a provider",
        official_evidence=[],
    )
    route = dict(
        id="generate", kind="ai_call", workload="fixture", runtime_scope="runtime",
        source_location="app.py:8", trigger="fake_client.generate", purpose="Generate reply",
        evidence=["evidence/source.txt"], ai_usage="direct", ai_route_ids=["generate"],
        disposition="Port client behind the existing JSON response schema",
        acceptance_criteria=["Malformed output is rejected before returning JSON"],
        service_mapping_ids=["ai"], target_node_ids=["aws-ai"], capability_ids=["reply"],
        model_ref="assistant-model", target_gap="",
        source_contract={key: f"Observed fixture {key}" for key in ("sdk_method", "source_model") + checker.FEATURES},
        feature_mapping=[dict(
            feature=key, source_behavior=f"Source {key}", target_behavior=f"Target {key}",
            implementation="Application adapter pending source-specific implementation",
            status="application_change", evidence=["evidence/source.txt"],
        ) for key in checker.FEATURES],
        examples=dict(source_request='{"messages":[{"role":"user","content":"fixture"}]}',
                      target_request='{"input":"fixture","store":false}',
                      target_response='{"output":[{"type":"message","content":[]}]}'),
    )
    entry = {k: copy.deepcopy(v) for k, v in route.items() if k not in {
        "model_ref", "target_gap", "source_contract", "feature_mapping", "examples",
    }}
    entry.update(id="http-answer", kind="http", trigger="POST /answer", ai_usage="indirect")
    data = dict(
        contract=checker.CONTRACT, source_commit="a" * 40,
        provenance=dict(plugin_name="azure-aws-migration", plugin_version="test",
                        skill_path="fixture/SKILL.md", skill_sha256="b" * 64),
        evidence_policy="repository_and_official_docs",
        model_policy=dict(allowed_providers=["openai"], constraint="OpenAI only"),
        coverage=dict(status="complete", scope="fixture app", reviewed_paths=["app.py"],
                      discovery_evidence=["evidence/source.txt"], omissions=[]),
        discoveries=[dict(id=r["id"] + "-site", kind=r["kind"], source_location=r["source_location"],
                          evidence=r["evidence"], disposition="included", route_id=r["id"],
                          reason="Source inspected") for r in (entry, route)],
        routes=[entry, route], models=[model],
    )
    (root / "assessment.md").write_text("# Fixture assessment\n\n" + "\n\n".join(
        "## " + title + "\n\nFixture findings: source-only proposed migration; no execution."
        for title in checker.HEADINGS) + "\n")
    return data


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = fixture(self.root)

    def save(self):
        (self.root / "assessment-contract.json").write_text(json.dumps(self.data))

    def valid(self):
        checker.validate(self.root, self.data)

    def rejected(self, match):
        with self.assertRaisesRegex(ValueError, match):
            self.valid()

    def test_complete_contract_renders_and_rechecks(self):
        self.save()
        checker.audit(self.root, render=True)
        checker.audit(self.root)

    def test_discovered_route_cannot_disappear(self):
        self.data["routes"].pop()
        self.rejected("unaccounted")

    def test_unlinked_ai_call_cannot_appear(self):
        self.data["discoveries"].pop()
        self.rejected("discovered call sites")

    def test_missing_feature_rejected(self):
        self.data["routes"][1]["feature_mapping"].pop()
        self.rejected("incomplete API")

    def test_unknown_model_rejected(self):
        self.data["routes"][1]["model_ref"] = "missing"
        self.rejected("unknown model")

    def test_unresolved_model_allowed_when_visible(self):
        self.data["models"] = []
        self.data["routes"][1].update(model_ref=None, target_gap="Model docs prohibited; select after verification")
        self.save()
        checker.audit(self.root, render=True)
        self.assertIn("Model docs prohibited", (self.root / "assessment.md").read_text())

    def test_unresolved_model_without_reason_rejected(self):
        self.data["routes"][1].update(model_ref=None)
        self.rejected("explicit gap")

    def test_documented_model_requires_route_evidence(self):
        self.data["models"][0]["verification"] = "documented"
        self.rejected("exact ID/route evidence")

    def test_provider_policy_enforced(self):
        self.data["models"][0]["provider"] = "another-provider"
        self.rejected("allowed-provider")

    def documented(self):
        self.data["models"][0].update(verification="documented", official_evidence=[dict(
            url="https://docs.aws.amazon.com/fixture", snapshot_path="evidence/official.txt",
            checked_at="2026-09-17", supports=sorted(checker.CLAIMS),
        )])

    def test_documented_fixture_evidence_contract(self):
        self.documented()
        self.valid()

    def test_wrong_region_url_rejected(self):
        self.documented()
        self.data["models"][0]["region"] = "us-west-2"
        self.rejected("Region and URL disagree")

    def test_repository_only_blocks_official_claims(self):
        self.documented()
        self.data["evidence_policy"] = "repository_only"
        self.rejected("repository-only policy")

    def test_missing_official_claim_rejected(self):
        self.documented()
        self.data["models"][0]["official_evidence"][0]["supports"].remove("api")
        self.rejected("route evidence")

    def test_feature_support_requires_official_evidence(self):
        self.data["routes"][1]["feature_mapping"][0]["status"] = "supported"
        self.rejected("selected-model official")

    def test_missing_response_translation_rejected(self):
        del self.data["routes"][1]["examples"]["target_response"]
        self.rejected("target_response")

    def test_stale_main_report_rejected(self):
        self.save()
        checker.audit(self.root, render=True)
        self.data["models"][0]["model_id"] = "fixture.changed"
        self.save()
        with self.assertRaisesRegex(ValueError, "tables missing/stale"):
            checker.audit(self.root)

    def test_partial_coverage_disclosed(self):
        self.data["coverage"].update(status="partial", omissions=["Unavailable shared source"])
        self.save()
        checker.audit(self.root, render=True)
        self.assertIn("Unavailable shared source", (self.root / "assessment.md").read_text())

    def test_false_complete_coverage_rejected(self):
        self.data["coverage"]["omissions"] = ["Missing shared dependency"]
        self.rejected("contradicts omissions")

    def test_non_ai_scope_allowed(self):
        self.data["models"] = []
        self.data["routes"] = self.data["routes"][:1]
        self.data["routes"][0].update(ai_usage="none", ai_route_ids=[], disposition="Static route; no Bedrock mapping")
        self.data["discoveries"] = self.data["discoveries"][:1]
        self.data["coverage"]["no_ai_reason"] = "Only a static route exists in the fixture."
        self.save()
        checker.audit(self.root, render=True)

    def package(self):
        for name, data in {
            "service-mapping.json": dict(source_commit=self.data["source_commit"], entries=[dict(id="ai")]),
            "architecture/architecture.json": dict(source_commit=self.data["source_commit"], nodes=[dict(id="aws-ai")]),
            "evidence.json": dict(source_commit=self.data["source_commit"]),
            "implementation-ledger.json": dict(capabilities=[dict(id="reply")]),
            "deployment/ai-routes.json": checker.deployment_routes(self.data),
        }.items():
            path = self.root / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(data))

    def test_deployment_bindings_pass(self):
        self.package()
        checker.validate(self.root, self.data, package=True)

    def test_model_config_drift_rejected(self):
        self.package()
        path = self.root / "deployment/ai-routes.json"
        data = json.loads(path.read_text())
        data["routes"][0]["model_id"] = "different"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "Deployment model routes differ"):
            checker.validate(self.root, self.data, package=True)

    def test_unknown_architecture_reference_rejected(self):
        self.package()
        self.data["routes"][0]["target_node_ids"] = ["absent"]
        with self.assertRaisesRegex(ValueError, "unknown target_node_ids"):
            checker.validate(self.root, self.data, package=True)

    def test_unsafe_evidence_path_rejected(self):
        self.data["routes"][0]["evidence"] = ["../outside"]
        self.rejected("unsafe path")


if __name__ == "__main__":
    unittest.main()
