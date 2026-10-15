#!/usr/bin/env python3
"""Evaluate exact Bedrock routes using reviewed evidence. Offline; no model/cloud calls."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_REGISTRY=Path(__file__).resolve().parents[1]/'data/capabilities.json'
STATES={'YES','NO','VERIFY','ORCHESTRATED'}
HOSTS={'docs.aws.amazon.com','aws.amazon.com','developers.openai.com','platform.openai.com','learn.chatgpt.com'}


def require(ok, message):
    if not ok:raise ValueError(message)


def combine(states):
    return next((s for s in ('NO','VERIFY','ORCHESTRATED') if s in states),'YES')


def registry_hash(registry):
    return hashlib.sha256(json.dumps(registry,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def validate_registry(registry, root=None):
    require(registry.get('schema_version')==2,'Unsupported registry schema; use the matching historical release for v1')
    features={f['id'] for f in registry['features']}
    require(len(features)==len(registry['features']),'Duplicate feature')
    sources={s['id']:s for s in registry['sources']}
    require(len(sources)==len(registry['sources']),'Duplicate source')
    for s in sources.values():
        for field in ('url','retrieved_url'):
            p=urlparse(s[field]);require(p.scheme=='https' and p.hostname in HOSTS and not p.username,'Non-official evidence URL')
        date.fromisoformat(s['checked_at'][:10])
        require(s['scope'] in {'direct_openai','bedrock'},'Unknown evidence scope')
        if root:
            p=(root/s['snapshot_path']).resolve()
            require(p.is_relative_to(root.resolve()),'Evidence path escapes registry directory')
            require(hashlib.sha256(p.read_bytes()).hexdigest()==s['sha256'],'Evidence hash mismatch')
    models={m['base_model_id']:m for m in registry['models']}
    require(len(models)==len(registry['models']),'Duplicate model')
    allowed=set(registry['target_policy']['allowed_base_model_ids'])
    require(set(models)==allowed,'Model inventory differs from approved target policy')
    def check_claim(c):
        require(c['status'] in STATES,'Invalid capability state')
        require(bool(c.get('reason')) and c.get('sources') and set(c['sources'])<=sources.keys(),'Missing claim explanation/evidence')
        require(any(sources[i]['scope']=='bedrock' for i in c['sources']),'Direct OpenAI support does not establish Bedrock support')
        date.fromisoformat(c['reviewed_at'])
    ids=set()
    for route in registry['routes']:
        require(route['id'] not in ids,'Duplicate route');ids.add(route['id'])
        require(route['base_model_id'] in allowed,'Unapproved target model')
        require(route['model_name'] in registry['target_policy']['allowed_model_names'],'Unapproved target name')
        require(route['model_id'] in {route['base_model_id']}|{p+'.'+route['base_model_id'] for p in ['us','in','global']},'Unknown model/profile ID')
        require(not any(x in route['model_id'].lower() for x in registry['target_policy']['excluded_families']),'Excluded target family')
        require(route['entry_regions'] and len(set(route['entry_regions']))==len(route['entry_regions']),'Missing/duplicate entry Regions')
        require(route['sources'] and set(route['sources'])<=sources.keys(),'Missing route evidence')
        require(set(route['features'])==features,'Incomplete feature catalog')
        for c in route['features'].values():check_claim(c)
        for c in route['interactions']:
            require(set(c['required_features'])<=features,'Unknown interaction feature');check_claim(c)
        for c in route['region_constraints'].values():check_claim(c)
        for k in ['implicit','explicit']:check_claim(route['cache'][k])
        require(route['inference_mode'] in {'in_region','geographic','global'},'Invalid routing mode')
        require(route['partition'] in {'aws','aws-us-gov'},'Invalid partition')
    for rule in registry['rules']:check_claim(rule)


def validate_requirements(req, features):
    require(isinstance(req,dict),'Requirements must be an object')
    allowed={'id','required_features','models','endpoints','apis','entry_regions','geography','single_region',
     'allow_orchestration','residency_scopes','retention_mode','store','cache','external_web_access','assumptions',
     'source_model','source_api','partition','service_tier','context_tokens','max_output_tokens',
     'preferred_features','preferred_models','preferred_apis','preferred_endpoints'}
    require(not set(req)-allowed,'Unknown requirement keys: '+', '.join(sorted(set(req)-allowed)))
    for k in ['required_features','models','endpoints','apis','entry_regions','residency_scopes','assumptions',
              'preferred_features','preferred_models','preferred_apis','preferred_endpoints']:
        if k in req:require(isinstance(req[k],list) and all(isinstance(v,str) and v for v in req[k]) and len(req[k])==len(set(req[k])),k+' must contain unique strings')
    for k in ['required_features','preferred_features']:require(set(req.get(k,[]))<=features,'Unknown feature')
    for k in ['store','allow_orchestration','external_web_access']:
        if k in req:require(isinstance(req[k],bool),k+' must be boolean')
    require(req.get('retention_mode','unknown') in {'unknown','none','default','aws_review','provider_data_share'},'Unknown retention mode')
    require(req.get('geography') in {None,'US','IN','EU','UK','CA','APAC','unrestricted'},'Unknown geography')
    require(req.get('partition','aws') in {'aws','aws-us-gov'},'Unknown partition')
    require(req.get('service_tier','standard') in {'standard','ultrafast','priority','flex','reserved'},'Unknown service tier')
    require(set(req.get('residency_scopes',[]))<={'processing','cache','stored_responses','logs','abuse_retention','tools','backups'},'Unknown residency scope')
    if 'single_region' in req:require(isinstance(req['single_region'],str) and bool(req['single_region']),'single_region must be a Region string')
    cache=req.get('cache',{})
    require(isinstance(cache,dict) and not set(cache)-{'mode','prefix_tokens','breakpoints','max_retention_minutes'},'Unknown cache requirement')
    require(cache.get('mode','either') in {'either','implicit','explicit','application_response'},'Unknown cache mode')
    for obj,keys in [(req,['context_tokens','max_output_tokens']),(cache,['prefix_tokens','breakpoints','max_retention_minutes'])]:
        for k in keys:
            if k in obj:require(type(obj[k]) in {int,float} and math.isfinite(obj[k]) and obj[k]>=0,'Invalid numeric requirement '+k)
    if 'breakpoints' in cache:require(type(cache['breakpoints']) is int,'breakpoints must be an integer')
    require(not cache or cache.get('mode')=='application_response' or 'prompt_caching' in req.get('required_features',[]),'Cache controls require prompt_caching as a required feature')


def evaluate(registry, requirements, as_of=None):
    today=date.fromisoformat(as_of) if as_of else datetime.now(timezone.utc).date()
    features={f['id'] for f in registry['features']}
    validate_requirements(requirements,features)
    req=requirements;required=set(req.get('required_features',[]));cache=req.get('cache',{})
    sources={s['id']:s for s in registry['sources']};models={m['base_model_id']:m for m in registry['models']}
    results=[]
    for route in registry['routes']:
        if req.get('models') and not set(req['models']).intersection({route['model_name'],route['model_id'],route['base_model_id']}):continue
        if route['partition']!=req.get('partition','aws'):continue
        for region in route['entry_regions']:
            if req.get('entry_regions') and region not in req['entry_regions']:continue
            checks=[]
            def check(status,reason,refs=(),feature=None):
                item={'status':status,'reason':reason,'sources':list(refs)}
                if feature:item['feature']=feature
                checks.append(item)
            def apply(c,feature=None):
                check(c['status'],c['reason'],c['sources'],feature)
                age=(today-date.fromisoformat(c['reviewed_at'])).days
                if age<0 or age>registry['max_evidence_age_days']:check('VERIFY','Claim review is stale or future-dated.',c['sources'],feature)
            for plural,singular in [('endpoints','endpoint'),('apis','api')]:
                if req.get(plural) and route[singular] not in req[plural]:check('NO',singular+' is outside allowed values')
            for f in sorted(required):apply(route['features'][f],f)
            geo=req.get('geography');mode=route['inference_mode'];served=route['processing_geography']
            if geo and geo!='unrestricted':
                check('YES' if served==geo else 'NO',f'Documented processing scope: {served}; required: {geo}',route['sources'])
                if region in route['region_constraints']:apply(route['region_constraints'][region])
            if req.get('single_region'):
                check('YES' if mode=='in_region' and region==req['single_region'] else 'NO','Strict single-Region processing requirement',route['sources'])
            if not geo and not req.get('single_region'):check('VERIFY','Residency unresolved; unrestricted routing is not assumed')
            # Availability uncertainty matters even without a residency constraint.
            if region in route['region_constraints'] and 'entry Region' in route['region_constraints'][region]['reason']:apply(route['region_constraints'][region])
            for scope in req.get('residency_scopes',[]):
                if scope!='processing':check('VERIFY','Verify '+scope+' location/configuration end to end',registry['data_boundary_sources'][scope])
            retention=registry['retention_sources']
            if req.get('retention_mode')=='none':
                check('VERIFY','Confirm account/model zero-retention eligibility and effective settings',retention)
                if {'background','stored_state'}&required or req.get('store') is True:check('NO','Zero retention conflicts with background or stored state/store=true',retention)
                if 'prompt_caching' in required:check('VERIFY','Establish cache treatment under zero-retention policy',retention+route['cache']['sources'])
            if req.get('store') is False:
                if 'stored_state' in required:check('NO','store=false cannot provide stored response continuation',retention)
                if 'background' in required:check('VERIFY','Verify background and store=false interaction',retention)
            for rule in registry['rules']+route['interactions']:
                if set(rule['required_features'])<=required:apply(rule)
            if 'prompt_caching' in required:
                limits=route['cache'];cmode=cache.get('mode','either')
                if cmode in ['implicit','explicit']:apply(limits[cmode],'prompt_caching')
                elif cmode=='either':
                    # Apply the chosen mode claim as well so an old review cannot appear current.
                    best=min([limits['implicit'],limits['explicit']],key=lambda c:{'YES':0,'ORCHESTRATED':1,'VERIFY':2,'NO':3}[c['status']]);apply(best,'prompt_caching')
                if 'prefix_tokens' not in cache:check('VERIFY','Confirm reusable prompt prefix length',limits['sources'])
                elif cache['prefix_tokens']<limits['min_prefix_tokens']:check('NO','Prompt prefix does not meet this route cache minimum',limits['sources'])
                if limits['max_writes'] is not None and cache.get('breakpoints',1)>limits['max_writes']:check('NO','Too many cache writes/breakpoints for this route',limits['sources'])
                if cmode=='explicit' and cache.get('breakpoints')==0:check('NO','Explicit mode without breakpoints does not cache',limits['sources'])
                if 'max_retention_minutes' in cache:
                    minimum=limits['min_ttl_minutes']
                    check('NO' if minimum is not None and cache['max_retention_minutes']<minimum else 'VERIFY','Cache TTL is not a maximum deletion guarantee',limits['sources'])
            if cache.get('mode')=='application_response':check('VERIFY','Whole-response caching needs application correctness, authorization and invalidation design')
            if 'independent_guardrail' in required and req.get('allow_orchestration') is not True:
                check('NO' if req.get('allow_orchestration') is False else 'VERIFY','Separate Guardrail orchestration is disallowed or not yet accepted',route['features']['independent_guardrail']['sources'])
            if 'server_tools' in required:check('VERIFY','Identify and verify the exact hosted tool and its permissions',route['features']['server_tools']['sources'])
            if 'web_search' in required and req.get('external_web_access') is not False:check('VERIFY','Clarify external tool data boundary and IAM enforcement',route['features']['web_search']['sources'])
            tier=req.get('service_tier','standard')
            if tier not in route['service_tiers']:check('NO','Service tier not documented for this route/API',route['sources'])
            if tier=='ultrafast' and 'ultrafast_regions' in route and region not in route['ultrafast_regions']:check('NO','Ultrafast unavailable in this Mantle Region',route['sources'])
            for field,limit in [('context_tokens','context_tokens'),('max_output_tokens','max_output_tokens')]:
                if field in req and req[field]>route['limits'][limit]:check('NO',field+' exceeds the documented route limit',route['limits']['sources'])
            refs=set(route['sources'])
            for c in checks:refs.update(c['sources'])
            for ident in sorted(refs):
                age=(today-date.fromisoformat(sources[ident]['checked_at'][:10])).days
                if age<0 or age>registry['max_evidence_age_days']:check('VERIFY',f'Evidence {ident} is stale or future-dated; refresh and review',[ident])
            exact={k:route[k] for k in ['model_name','model_id','endpoint','api','inference_mode','inference_path','partition']}
            exact.update(region=region,processing_geography=served,base_url=route['base_url_template'].format(region=region))
            exact['inference_path']=exact['inference_path'].format(model_id=route['model_id'])
            matches=[]
            for f in req.get('preferred_features',[]):
                c=route['features'][f]
                if c['status']=='YES' and 0<=(today-date.fromisoformat(c['reviewed_at'])).days<=registry['max_evidence_age_days'] and all(0<=(today-date.fromisoformat(sources[i]['checked_at'][:10])).days<=registry['max_evidence_age_days'] for i in c['sources']):matches.append(f)
            for key,value in [('preferred_models',route['model_name']),('preferred_apis',route['api']),('preferred_endpoints',route['endpoint'])]:
                if value in req.get(key,[]):matches.append(value)
            results.append({'route_id':route['id']+':'+region,'route':exact,'status':combine([c['status'] for c in checks]),
                'checks':checks,'preference_matches':matches,'account_access':'not_tested','runtime_behavior':'not_tested',
                'quality_latency':'not_measured','pricing':{'sources':route['pricing_sources'],'rows':models[route['base_model_id']]['pricing'],
                'note':'Model-card rate rows; match inference option, partition, tier and context before estimating. Missing rates remain unknown.'}})
    results.sort(key=lambda r:({'YES':0,'ORCHESTRATED':1,'VERIFY':2,'NO':3}[r['status']],-len(r['preference_matches']),r['route_id']))
    return {'schema_version':2,'evaluated_at':today.isoformat(),'registry_version':registry['registry_version'],
      'registry_sha256':registry_hash(registry),'registry_snapshot':registry['snapshot_date'],'scope':registry['scope'],
      'requirements':req,'summary':{s:sum(r['status']==s for r in results) for s in ['YES','ORCHESTRATED','VERIFY','NO']},
      'selection_policy':'Hard compatibility first, then explicit preference matches. Ties are alphabetical, not a quality/cost recommendation.',
      'no_candidates_reason':None if results else 'No candidates in the approved catalog for these model/Region/partition filters. Do not infer global unavailability or substitute excluded models.',
      'results':results}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('requirements',type=Path);p.add_argument('--registry',type=Path,default=DEFAULT_REGISTRY)
    p.add_argument('--as-of',help='Historical reproduction date; never proof of current evidence')
    p.add_argument('--output',type=Path)
    a=p.parse_args();registry=json.loads(a.registry.read_text());validate_registry(registry,a.registry.parent)
    result=evaluate(registry,json.loads(a.requirements.read_text()),a.as_of)
    text=json.dumps(result,indent=2)+'\n'
    if a.output:a.output.write_text(text);print(json.dumps(result['summary']))
    else:print(text,end='')


if __name__=='__main__':main()
