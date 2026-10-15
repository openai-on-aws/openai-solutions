"""End-to-end synthetic assessment tests; never execution/coverage claims about a customer repo."""
import ast
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import evaluate_routes as engine
import verify_assessment
import verify_advisor_assessment as advisor
from test_verify_assessment import fixture


class RevisionTwoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.data=fixture(self.root);self.data['assessment_revision']=2
        self.data['provenance']['plugin_version']='0.4.0'
        self.route=next(r for r in self.data['routes'] if r['kind']=='ai_call')
        self.req={'models':['GPT-6.1 Sol'],'geography':'US','entry_regions':['us-east-1'],'apis':['responses'],'required_features':['structured_outputs']}
        self.registry=json.loads(engine.DEFAULT_REGISTRY.read_text())
        fixed=datetime.fromisoformat(self.registry['snapshot_date']).replace(tzinfo=timezone.utc)
        class FrozenClock:
            @staticmethod
            def now(tz=None): return fixed
        clock_patch=patch.object(engine,'datetime',FrozenClock)
        clock_patch.start();self.addCleanup(clock_patch.stop)
        self.result=engine.evaluate(self.registry,self.req)
        candidate=next(c for c in self.result['results'] if c['status']=='YES')
        self.data['models'][0].update({k:candidate['route'][k] for k in ['model_id','region','endpoint','base_url','inference_path','api']})
        self.data['models'][0]['name']=candidate['route']['model_name']
        self.route['route_selection']={'selected_candidate_id':candidate['route_id'],'rationale':'Synthetic schema-compatible candidate',
            'tradeoffs':'Quality and account access untested','alternatives':[],'next_validation':'Exercise refusals and account availability'}
        self.route['gaps']=[dict(id='gap-'+m['feature'],feature=m['feature'],kind='application',affected_files=['app.py:8'],
            evidence=['evidence/source.txt'],proposed_change='Implement a reviewed request/response adapter',
            control_flow='Call adapter and validate before returning',state='Application owns history',failure_handling='Return explicit failure after bounded attempts',
            behavior_difference='No parity claim until application tests pass',required_tests=['Reject invalid output'],implementation_status='design_only') for m in self.route['feature_mapping']]
        self.compat=self.root/'compatibility';self.compat.mkdir()
        shutil.copytree(engine.DEFAULT_REGISTRY.parent,self.compat/'data')
        self.index=[{'ai_role_id':self.route['id'],'requirements':'compatibility/requirements.json','evaluation':'compatibility/evaluation.json','registry':'compatibility/data/capabilities.json'}]
        self.save()

    def save(self):
        (self.root/'assessment-contract.json').write_text(json.dumps(self.data))
        (self.compat/'requirements.json').write_text(json.dumps(self.req))
        (self.compat/'evaluation.json').write_text(json.dumps(self.result))
        (self.compat/'index.json').write_text(json.dumps(self.index))

    def test_valid_end_to_end(self):
        verify_assessment.audit(self.root,render=True);advisor.audit(self.root)
        report=(self.root/'assessment.md').read_text()
        self.assertIn('design_only',report);self.assertIn(self.route['route_selection']['selected_candidate_id'],report)

    def test_missing_gap_rejected(self):
        self.route['gaps'].pop();self.save()
        with self.assertRaisesRegex(ValueError,'every feature gap'):verify_assessment.audit(self.root,render=True)

    def test_unimplemented_cannot_claim_verified(self):
        self.route['gaps'][0]['implementation_status']='verified';self.save()
        with self.assertRaisesRegex(ValueError,'evidence file list'):verify_assessment.audit(self.root,render=True)

    def test_excluded_target_rejected(self):
        self.data['models'][0]['model_id']='openai.gpt-oss-120b';self.save()
        with self.assertRaisesRegex(ValueError,'approved nine'):verify_assessment.audit(self.root,render=True)

    def test_selected_row_must_match(self):
        self.route['route_selection']['selected_candidate_id']='invented-route';self.save()
        verify_assessment.audit(self.root,render=True)
        with self.assertRaisesRegex(ValueError,'missing from evaluated'):advisor.audit(self.root)

    def test_pinned_registry_required(self):
        self.index[0].pop('registry');self.save();verify_assessment.audit(self.root,render=True)
        with self.assertRaisesRegex(ValueError,'pin a local registry'):advisor.audit(self.root)

    def test_historical_replay_not_current_claim(self):
        self.result=engine.evaluate(self.registry,self.req,'2026-12-01');self.save();verify_assessment.audit(self.root,render=True)
        advisor.audit(self.root,historical=True)
        with self.assertRaisesRegex(ValueError,'future-dated'):advisor.audit(self.root)


class AdapterRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Execute the actual dependency-free Route class, not a reimplementation.
        # Full application imports/HTTP behavior remain a separate application check.
        path=engine.DEFAULT_REGISTRY.parent.parent/'assets/python-bedrock/bedrock_json_agent.py'
        tree=ast.parse(path.read_text());node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Route')
        namespace={'dataclass':dataclass,'json':json,'Path':Path,'__file__':str(path)}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
        cls.Route=namespace['Route']

    def test_new_and_legacy_models(self):
        self.assertEqual(self.Route('gpt-6.1-sol','us-east-1','bedrock-mantle','in-region').model,'openai.gpt-6.1-sol')
        self.assertEqual(self.Route('terra','us-east-1','bedrock-runtime','us').model,'us.openai.gpt-5.6-terra')

    def test_bad_route_and_excluded_model(self):
        for args in [('gpt-6.1-sol','us-west-2','bedrock-mantle','in-region'),('gpt-oss-120b','us-east-1','bedrock-mantle','in-region'),('gpt-6.1-sol','us-east-1','bedrock-runtime','global')]:
            with self.assertRaises(ValueError):self.Route(*args)


if __name__=='__main__':unittest.main()
