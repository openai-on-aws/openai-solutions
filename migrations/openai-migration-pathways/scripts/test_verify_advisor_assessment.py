import json
from pathlib import Path
import tempfile
import unittest
import evaluate_routes
import verify_advisor_assessment as advisor
import verify_assessment
from test_verify_assessment import fixture


class AdvisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = fixture(self.root)
        registry = json.loads(evaluate_routes.DEFAULT_REGISTRY.read_text())
        self.requirements = dict(geography="US", entry_regions=["us-east-1"],
                                 required_features=["prompt_caching"], cache={"prefix_tokens": 8000})
        self.result = evaluate_routes.evaluate(registry, self.requirements)
        candidate = next(r for r in self.result["results"] if r["route"]["model_id"] == "us.openai.gpt-5.6-terra"
                         and r["route"]["api"] == "responses")
        self.data["models"][0].update({k: candidate["route"][k] for k in
                                      ("model_id", "region", "endpoint", "base_url", "inference_path", "api")})
        self.compatibility = self.root / "compatibility"
        self.compatibility.mkdir()
        self.index = [{"ai_role_id": "generate", "requirements": "compatibility/requirements.json",
                       "evaluation": "compatibility/evaluation.json"}]
        self.save()

    def save(self):
        (self.root / "assessment-contract.json").write_text(json.dumps(self.data))
        (self.compatibility / "requirements.json").write_text(json.dumps(self.requirements))
        (self.compatibility / "evaluation.json").write_text(json.dumps(self.result))
        (self.compatibility / "index.json").write_text(json.dumps(self.index))
        verify_assessment.audit(self.root, render=True)

    def test_valid_assessment(self):
        advisor.audit(self.root)

    def test_missing_role(self):
        self.index = []
        self.save()
        with self.assertRaisesRegex(ValueError, "every AI role"):
            advisor.audit(self.root)

    def test_edited_evaluation(self):
        self.result["summary"]["YES"] += 1
        self.save()
        with self.assertRaisesRegex(ValueError, "changed or was edited"):
            advisor.audit(self.root)

    def test_wrong_selected_path(self):
        self.data["models"][0]["inference_path"] = "/v1/responses"
        self.save()
        with self.assertRaisesRegex(ValueError, "missing from evaluated"):
            advisor.audit(self.root)

    def test_incompatible_selected_route(self):
        self.requirements["required_features"].append("inline_guardrails")
        self.result = evaluate_routes.evaluate(json.loads(evaluate_routes.DEFAULT_REGISTRY.read_text()), self.requirements)
        self.save()
        with self.assertRaisesRegex(ValueError, "violates requirements"):
            advisor.audit(self.root)

    def test_repository_only_respects_scope(self):
        self.data["evidence_policy"] = "repository_only"
        self.index = [{"ai_role_id": "generate", "not_run_reason": "Customer restricted this review to repository evidence."}]
        self.save()
        advisor.audit(self.root)


if __name__ == "__main__":
    unittest.main()
