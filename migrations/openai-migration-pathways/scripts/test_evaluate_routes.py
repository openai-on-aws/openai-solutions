"""Synthetic rule tests plus separately identified reviewed-catalog regressions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import evaluate_routes as engine

DATE='2026-10-14'


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.r=json.loads(engine.DEFAULT_REGISTRY.read_text())
        route=copy.deepcopy(next(x for x in self.r['routes'] if x['model_name']=='GPT-6 Sol' and x['api']=='responses' and x['endpoint']=='bedrock-runtime' and x['inference_mode']=='geographic'))
        route['entry_regions']=['us-east-1'];route['region_constraints']={};route['interactions']=[]
        for c in route['features'].values():c.update(status='YES',reason='Synthetic capability fixture')
        for c in route['cache'].values():
            if isinstance(c,dict):c.update(status='YES')
        self.r['routes']=[route];self.route=route
        self.req={'geography':'US','entry_regions':['us-east-1'],'required_features':[]}

    def run_case(self,**changes):
        req={**self.req,**changes};return engine.evaluate(self.r,req,DATE)['results'][0]

    def test_required_subset(self):
        self.route['features']['streaming']['status']='NO'
        self.assertEqual(self.run_case()['status'],'YES')
        self.assertEqual(self.run_case(required_features=['streaming'])['status'],'NO')

    def test_no_union_across_apis(self):
        b=copy.deepcopy(self.route);b['id']+='other';b['api']='chat_completions'
        self.route['features']['streaming']['status']='NO';b['features']['client_tools']['status']='NO'
        self.r['routes'].append(b)
        result=engine.evaluate(self.r,{**self.req,'required_features':['streaming','client_tools']},DATE)
        self.assertEqual(result['summary']['NO'],2)

    def test_unknown_is_not_no(self):
        self.route['features']['streaming']['status']='VERIFY'
        self.assertEqual(self.run_case(required_features=['streaming'])['status'],'VERIFY')

    def test_stale_claim_without_stale_snapshot(self):
        self.route['features']['streaming']['reviewed_at']='2026-01-01'
        self.assertEqual(self.run_case(required_features=['streaming'])['status'],'VERIFY')

    def test_stale_and_future_sources(self):
        for value in ['2026-01-01','2027-01-01']:
            for s in self.r['sources']:s['checked_at']=value
            self.assertEqual(self.run_case()['status'],'VERIFY')

    def test_unknown_residency(self):self.assertEqual(self.run_case(geography=None)['status'],'VERIFY')
    def test_entry_is_not_processing(self):self.assertEqual(self.run_case(geography='EU')['status'],'NO')
    def test_single_region_excludes_geographic(self):self.assertEqual(self.run_case(single_region='us-east-1')['status'],'NO')
    def test_nonprocessing_boundary(self):self.assertEqual(self.run_case(residency_scopes=['cache','logs'])['status'],'VERIFY')

    def test_retention_conflicts(self):
        self.assertEqual(self.run_case(retention_mode='none',required_features=['background'])['status'],'NO')
        self.assertEqual(self.run_case(retention_mode='none',store=False)['status'],'VERIFY')
        self.assertEqual(self.run_case(store=False,required_features=['stored_state'])['status'],'NO')

    def test_orchestration_requires_acceptance(self):
        self.route['features']['independent_guardrail']['status']='ORCHESTRATED'
        self.assertEqual(self.run_case(required_features=['independent_guardrail'],allow_orchestration=True)['status'],'ORCHESTRATED')
        self.assertEqual(self.run_case(required_features=['independent_guardrail'],allow_orchestration=False)['status'],'NO')

    def test_cache_limits_are_per_route(self):
        self.route['cache']['min_prefix_tokens']=4096
        self.assertEqual(self.run_case(required_features=['prompt_caching'],cache={'prefix_tokens':2048})['status'],'NO')
        self.assertEqual(self.run_case(required_features=['prompt_caching'],cache={'prefix_tokens':4096})['status'],'YES')

    def test_implicit_does_not_satisfy_explicit(self):
        self.route['cache']['explicit']['status']='NO'
        self.assertEqual(self.run_case(required_features=['prompt_caching'],cache={'mode':'explicit','prefix_tokens':4096})['status'],'NO')
        self.assertEqual(self.run_case(required_features=['prompt_caching'],cache={'mode':'implicit','prefix_tokens':4096})['status'],'YES')

    def test_cache_deletion_guarantee(self):
        for limit,state in [(15,'NO'),(30,'VERIFY')]:
            self.assertEqual(self.run_case(required_features=['prompt_caching'],cache={'prefix_tokens':4096,'max_retention_minutes':limit})['status'],state)

    def test_limits_and_tiers(self):
        self.assertEqual(self.run_case(context_tokens=2000000)['status'],'NO')
        self.assertEqual(self.run_case(service_tier='ultrafast')['status'],'NO')

    def test_preference_does_not_override_blocker(self):
        b=copy.deepcopy(self.route);b['id']+='blocked';b['api']='chat_completions';b['features']['streaming']['status']='NO'
        self.r['routes'].append(b)
        result=engine.evaluate(self.r,{**self.req,'required_features':['streaming'],'preferred_apis':['chat_completions']},DATE)
        self.assertEqual(result['results'][0]['status'],'YES')

    def test_unknown_model_is_not_substituted(self):
        for model in ['GPT-4.1','gpt-oss-120b','GPT-5.6 Cyber']:
            result=engine.evaluate(self.r,{**self.req,'models':[model]},DATE)
            self.assertEqual(result['results'],[])

    def test_bad_inputs(self):
        for change in [{'required_features':['typo']},{'unknown':True},{'store':'false'},
                       {'cache':{'prefix_tokens':-1}},{'max_output_tokens':float('nan')},
                       {'models':'GPT-6 Sol'},{'required_features':['streaming','streaming']},
                       {'single_region':True},{'required_features':['prompt_caching'],'cache':{'breakpoints':1.5}}]:
            with self.assertRaises(ValueError):self.run_case(**change)

    def test_snapshot_hash_checked(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for s in self.r['sources']:
                path=root/s['snapshot_path'];path.parent.mkdir(exist_ok=True);path.write_text('changed')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):engine.validate_registry(self.r,root)

    def test_official_host_validation(self):
        self.r['sources'][0]['url']='https://docs.aws.amazon.com.attacker.test/page'
        with self.assertRaisesRegex(ValueError,'Non-official'):engine.validate_registry(self.r)

    def test_direct_openai_cannot_prove_bedrock(self):
        self.route['features']['streaming']['sources']=['OAI-GPT-6-SOL']
        with self.assertRaisesRegex(ValueError,'Direct OpenAI'):engine.validate_registry(self.r)

    def test_result_pins_registry(self):
        before=engine.registry_hash(self.r);self.route['features']['streaming']['status']='NO'
        self.assertNotEqual(before,engine.registry_hash(self.r))


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.r=json.loads(engine.DEFAULT_REGISTRY.read_text())

    def test_nine_models_and_snapshots(self):
        engine.validate_registry(self.r,engine.DEFAULT_REGISTRY.parent)
        self.assertEqual(len(self.r['models']),9)
        self.assertFalse(any(x in m['base_model_id'] for x in ['oss','daybreak','cyber'] for m in self.r['models']))
        self.assertEqual(set(self.r['target_policy']['allowed_model_names']),{r['model_name'] for r in self.r['routes']})

    def evaluate(self,**kw):
        return engine.evaluate(self.r,{'geography':'US','entry_regions':['us-east-1'],**kw},DATE)

    def test_new_cache_inline_combination(self):
        r=self.evaluate(models=['GPT-6.1 Sol'],apis=['chat_completions'],endpoints=['bedrock-runtime'],required_features=['prompt_caching','inline_guardrails'],cache={'mode':'explicit','prefix_tokens':2048})
        self.assertGreater(r['summary']['YES'],0)

    def test_old_explicit_cache_rejected(self):
        r=self.evaluate(models=['GPT-5.5'],required_features=['prompt_caching'],cache={'mode':'explicit','prefix_tokens':2048})
        self.assertEqual(r['summary']['YES'],0)

    def test_schema_streaming_specificity(self):
        a=self.evaluate(models=['GPT-6.1 Sol'],apis=['responses'],required_features=['structured_outputs','streaming'])
        b=self.evaluate(models=['GPT-6 Sol'],apis=['responses'],required_features=['structured_outputs','streaming'])
        self.assertGreater(a['summary']['YES'],0);self.assertEqual(b['summary']['YES'],0)

    def test_native_tool_gaps(self):
        r=self.evaluate(required_features=['hosted_file_search','remote_mcp'])
        self.assertEqual(r['summary']['NO'],len(r['results']))

    def test_govcloud_not_implicit(self):
        r=engine.evaluate(self.r,{'geography':'US','entry_regions':['us-gov-west-1']},DATE)
        self.assertEqual(r['results'],[])

    def test_mantle_chat_projects_and_networking(self):
        r=self.evaluate(endpoints=['bedrock-mantle'],apis=['chat_completions'],required_features=['custom_projects','private_link'])
        self.assertGreater(r['summary']['YES'],0)

    def test_exports_match(self):
        import export_catalog
        for name,text in export_catalog.outputs(self.r).items():
            self.assertEqual((engine.DEFAULT_REGISTRY.parent.parent/name).read_text(),text)


if __name__=='__main__':unittest.main()
