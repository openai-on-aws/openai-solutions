#!/usr/bin/env python3
"""Build the reviewed 0.4 catalog from hash-pinned snapshots. No network calls.

Semantic mappings below were reviewed on 2026-10-14. A new snapshot requires
reviewing these mappings and review-lock.json; fetching never updates claims.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REVIEWED = '2026-10-14'
MODELS = [
 ('GPT-6 Astra','gpt-6-astra','AWS-ASTRA'),
 ('GPT-6.1 Sol','gpt-6.1-sol','AWS-61-SOL'),
 ('GPT-6 Sol','gpt-6-sol','AWS-6-SOL'),
 ('GPT-6 Luna','gpt-6-luna','AWS-6-LUNA'),
 ('GPT-5.6 Sol','gpt-5.6-sol','S01'),
 ('GPT-5.6 Terra','gpt-5.6-terra','S02'),
 ('GPT-5.6 Luna','gpt-5.6-luna','S03'),
 ('GPT-5.5','gpt-5.5','AWS-55'),('GPT-5.4','gpt-5.4','AWS-54')]
FEATURES = ['prompt_caching','inline_guardrails','independent_guardrail','streaming',
 'stored_state','client_tools','server_tools','custom_projects','background',
 'cross_region','invocation_logs','single_region','structured_outputs',
 'application_profiles','sigv4','api_key','private_link','image_input','web_search',
 'strict_tool_arguments','file_input','computer_use','client_tool_search',
 'async_tools','websocket_api','mid_turn_steering','reasoning_updates','pro_mode',
 'programmatic_tools','hosted_multi_agent','hosted_file_search','shell_tool',
 'image_generation_tool','remote_mcp']


def clean(text):
 text=re.sub(r'!\[[^\]]*\]\([^)]*icon-(yes|no)\.png\)',lambda m:m[1].upper(),text)
 text=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',text)
 return re.sub(r'<[^>]+>',' ',text)


def section(text, pattern):
 match=re.search(r'^## '+pattern+r'[^\n]*\n([\s\S]*?)(?=^## |\Z)',text,re.M|re.I)
 if not match: raise ValueError('Missing reviewed section '+pattern)
 return match[1]


def claim(status, reason, *sources):
 return dict(status=status,reason=reason,sources=list(sources),reviewed_at=REVIEWED)


def region_rows(text):
 result={'bedrock-runtime': [], 'bedrock-mantle': []}
 ep=None
 for line in text.splitlines():
  if line.startswith('**') and 'endpoint' in line:
   for key in result:
    if key in line: ep=key
  cols=[s.strip().strip('`') for s in line.split('|')[1:-1]]
  if len(cols)==4 and re.match(r'^[a-z]{2}-(?:gov-)?[a-z]+-\d',cols[0]):
   region=cols[0].split()[0]
   flags=[v=='YES' or v.lower()=='supported' for v in cols[1:]]
   if ep is None:raise ValueError('Region without endpoint')
   result[ep].append((region,flags))
 return result


def pricing_rows(text, source):
 current='';parent='';out=[]
 for line in section(text,'Pricing').splitlines():
  if line.startswith('### '):parent=line[4:];current=parent
  elif line.startswith('#### '):current=parent+' / '+line[5:]
  if line.startswith('|') and '$' in line:
   cols=[x.strip() for x in line.split('|')[1:-1]]
   if len(cols)!=5:continue
   values=[float(x.replace('$','').replace(',','')) if x.startswith('$') else None for x in cols[1:]]
   out.append(dict(section=current,inference_option=cols[0],currency='USD',unit='1M tokens',
    input=values[0],cache_write=values[1],cache_read=values[2],output=values[3],
    sources=[source],reviewed_at=REVIEWED))
 return out


def main():
 sources=json.loads((ROOT/'data/sources.json').read_text())
 lock=json.loads((ROOT/'data/review-lock.json').read_text())
 for source in sources:
  digest=hashlib.sha256((ROOT/'data'/source['snapshot_path']).read_bytes()).hexdigest()
  if digest!=lock[source['id']] or digest!=source['sha256']:
   raise ValueError('Snapshot changed; review mappings before promotion: '+source['id'])
 r=dict(schema_version=2,registry_version='0.4.0',snapshot_date=REVIEWED,max_evidence_age_days=30,
  scope='Nine approved OpenAI Bedrock targets. GPT-OSS and Daybreak excluded. Documentation compatibility only.',
  target_policy={'allowed_model_names':[m[0] for m in MODELS],
                 'allowed_base_model_ids':['openai.'+m[1] for m in MODELS],
                 'excluded_families':['gpt-oss','daybreak','cyber']},
  features=[{'id':f,'description':f.replace('_',' ')} for f in FEATURES],sources=sources,models=[],routes=[],
  rules=[{'id':'background-streaming','required_features':['background','streaming'],
   **claim('VERIFY','Simultaneous background and streaming support requires exact contract verification.','S05')},
   {'id':'schema-tools-streaming','required_features':['structured_outputs','strict_tool_arguments','streaming'],
   **claim('VERIFY','Validate simultaneous strict output, strict tools and streaming, including refusals.','S16','OAI-SCHEMA')}],
  data_boundary_sources={'cache':['S07'],'stored_responses':['S05','S13'],'logs':['S15','S17'],
    'abuse_retention':['S21','S13'],'tools':['S11'],'backups':['S13']},
  retention_sources=['S13','S21'],conflicts=[],notes=[
   'OpenAI direct API facts are source context, not Bedrock availability evidence.',
   'Account access, quota, networking, retention configuration and runtime behavior are not tested.',
   'Prices are dated card rows, not quotes. Missing route prices remain unknown.',
   'No model quality or latency ranking is inferred from names or pricing.'])
 for name,slug,source in MODELS:
  text=clean((ROOT/f'data/evidence/{source}.txt').read_text())
  oid='OAI-'+slug.upper();otext=(ROOT/f'data/evidence/{oid}.txt').read_text()
  limits={}
  for key,label in [('context_tokens','Context window'),('max_output_tokens','Max output tokens')]:
   match=re.search(label+r':\*\*\s*([\d,]+)(M)?',text)
   if not match:raise ValueError('Missing model limits '+slug)
   limits[key]=int(match[1].replace(',',''))*(1000000 if match[2] else 1)
  model=dict(name=name,base_model_id='openai.'+slug,openai_model_id=slug,
   lifecycle=claim('YES','AWS model card lists Active; recheck deprecation and model access before deployment.',source),
   limits={**limits,'sources':[source]},pricing=pricing_rows(text,source),
   source_contract={'scope':'direct_openai','sources':[oid,'OAI-DEPRECATIONS'],
    'model_details_excerpt':section(otext,'Model details'),
    'note':'Direct OpenAI details do not establish Bedrock feature parity.'},
   evidence_sources=[source,oid])
  r['models'].append(model)
  regiontext=section(text,'(?:Regional Availability|Supported Regions)')
  regions=region_rows(regiontext)
  # Source/destination rows provide the exact US profile ingress for 6.1 Sol.
  destinations={}
  for line in regiontext.splitlines():
   cols=[c.strip() for c in line.split('|')[1:-1]]
   if len(cols)==2 and re.match(r'^(us|ca)-',cols[0]):
    destinations[cols[0].split()[0]]=re.findall(r'\b[a-z]{2}-(?:gov-)?[a-z]+-\d\b',cols[1])
  if slug=='gpt-6.1-sol':
   # Global source Regions are not enumerated in this card. Carry known source
   # Regions as provisional global candidates rather than borrowing another card.
   regions['bedrock-runtime']=[(x,[False,True,True]) for x in destinations]
  apitext=section(text,'Endpoints and APIs supported')
  api_support={}
  for ep in regions:
   part=re.search(r'\*\*APIs supported on[^\n]*'+ep+r'[^\n]*\n([\s\S]*?)(?=\*\*APIs|\*\*Note|\*\*Tip|\Z)',apitext)
   if not part:raise ValueError('Missing API table '+slug+' '+ep)
   values=re.search(r'^\|\s*(?:NO|YES)\s*\|.*$',part[1],re.M)
   flags=[c.strip()=='YES' for c in values[0].split('|')[1:-1]]
   api_support[ep]=[a for a,yes in zip(['messages','responses','chat_completions','converse','invoke'],flags) if yes]
  programs=section(text,'(?:Programmatic Access|Call the model)')
  supported_ids=set(re.findall(r'(?:(?:us|in|global)\.)?openai\.gpt-[a-z0-9.\-]+',programs))
  supported_ids={x.rstrip('.') for x in supported_ids}
  if 'openai.'+slug not in supported_ids:raise ValueError('Missing base ID '+slug)
  for ep,entries in regions.items():
   groups={}
   for region,flags in entries:
    for i,yes in enumerate(flags):
     if not yes:continue
     mode=['in_region','geographic','global'][i]
     geo='US' if i==0 or region.startswith(('us-','ca-')) else 'IN' if region.startswith('ap-south-') else None
     prefix='' if i==0 else 'global.' if i==2 else 'in.' if geo=='IN' else 'us.'
     mid=prefix+'openai.'+slug
     if mid not in supported_ids:raise ValueError('Unverified profile '+mid)
     key=(mode,geo if i!=2 else 'global',mid,'aws-us-gov' if region.startswith('us-gov-') else 'aws')
     groups.setdefault(key,[]).append(region)
   for (mode,geo,mid,partition),entry_regions in groups.items():
    for api in api_support[ep]:
     route_id=f'{slug}:{ep}:{api}:{mode}:{geo}:{partition}'
     runtime=ep=='bedrock-runtime';response=api=='responses';modern=slug in ['gpt-6-sol','gpt-6-luna','gpt-6.1-sol'];old=slug in ['gpt-5.5','gpt-5.4']
     caps={f:claim('VERIFY','Exact model/API behavior has not been established.',source) for f in FEATURES}
     def setcap(f,status,reason,*extra):caps[f]=claim(status,reason,source,*extra)
     setcap('streaming','YES','Model card and API document streaming.','S05' if response else 'S06')
     setcap('image_input','YES','Model card lists image input.')
     for f in ['stored_state','background','custom_projects','server_tools']:
      yes=response and (f=='stored_state' or not runtime)
      if f=='server_tools' and slug=='gpt-6.1-sol':yes=False
      if f=='custom_projects':yes=not runtime and api in ['responses','chat_completions']
      setcap(f,'YES' if yes else 'NO','Responses state/API and model-specific endpoint restrictions.','S04','S05')
     setcap('custom_projects','NO' if runtime else 'YES','Custom Projects support Responses and Chat Completions on Mantle; Runtime has default project only.','S12')
     setcap('client_tools','YES' if response or api=='converse' else 'VERIFY',
      'Client-executed functions are supported; inspect schema and tool lifecycle.' if response or api=='converse' else 'Verify exact tool contract; direct OpenAI Chat has model-specific restrictions.','S10','OAI-BEDROCK',oid)
     setcap('strict_tool_arguments','VERIFY','Generic strict-tool documentation does not establish every model/API combination.','S16','OAI-TOOLS')
     setcap('file_input','YES' if response else 'VERIFY','Responses supports file input; confirm file formats and payload limits.','OAI-BEDROCK')
     setcap('computer_use','VERIFY','Available on supported models; verify exact tool type and contract. Application executes actions.','OAI-BEDROCK')
     setcap('client_tool_search','YES' if response else 'VERIFY','OpenAI Bedrock guide documents client-side tool_search on Responses.','OAI-BEDROCK')
     for f in ['async_tools','websocket_api','mid_turn_steering','reasoning_updates','pro_mode','programmatic_tools','hosted_multi_agent','hosted_file_search','shell_tool','image_generation_tool','remote_mcp']:
      setcap(f,'NO','OpenAI Bedrock integration guide lists this native capability as unavailable. Application redesign is separate.','OAI-BEDROCK')
     setcap('cross_region','YES' if mode!='in_region' else 'NO','Exact inference mode from model card.','S14')
     setcap('single_region','YES' if mode=='in_region' else 'NO','In-Region and cross-Region modes are distinct.','S14')
     setcap('invocation_logs','YES' if runtime else 'NO','Runtime invocation logging; Mantle telemetry is not payload invocation logging.','S15','S17')
     setcap('application_profiles','YES' if runtime and (api=='converse' or (modern and api=='invoke')) else 'NO','Model/API restriction from model card.','S19')
     setcap('sigv4','YES','Endpoint supports AWS SigV4; refresh credentials for every request attempt.','S04','OAI-BEDROCK')
     setcap('api_key','YES' if api in ['responses','chat_completions'] else 'VERIFY','Verify auth mechanism in the selected SDK; compatibility is not IAM permission.','S04')
     setcap('private_link','YES','AWS documents Runtime and Mantle VPC endpoint services; verify deployment partition, DNS and policy.','S20')
     guard=runtime and (api=='converse' or modern and (slug!='gpt-6.1-sol' or not response))
     setcap('inline_guardrails','YES' if guard else 'NO','Per-model API restrictions; no family-wide Guardrails rule.','S08')
     setcap('independent_guardrail','ORCHESTRATED','Application calls ApplyGuardrail separately; design buffering, IAM, latency and failure policy.','S09')
     schema=modern or runtime and (not old or response)
     setcap('structured_outputs','YES' if schema else 'VERIFY','Exact JSON-schema configuration is documented.' if schema else 'Model/API schema enforcement or parameter contract needs verification.','S16')
     explicit=(modern and api!='converse') or (not old and not modern and response)
     implicit=modern or response
     setcap('prompt_caching','YES' if implicit else 'NO','Caching support is scoped to the model, API and mode.','S07')
     cache=dict(implicit=claim('YES' if implicit else 'NO','Reviewed model/API cache support.',source,'S07'),
      explicit=claim('YES' if explicit else 'NO','Explicit caching is distinct from implicit prefix reuse.',source,'S07'),
      min_prefix_tokens=1024,max_writes=4 if explicit else None,min_ttl_minutes=30 if not old else None,
      max_retention_minutes=None,sources=[source,'S07'])
     if slug=='gpt-6-astra' and runtime:
      # Card omits runtime cache feature; general caching guide includes later models.
      caps['prompt_caching']=claim('VERIFY','Astra Runtime cache scope is not explicit in its model card; generic later-model guidance is insufficient.',source,'S07')
      for k in ['implicit','explicit']:cache[k]=claim('VERIFY','Resolve Astra Runtime cache API scope.',source,'S07')
     setcap('web_search','NO' if runtime or not response or slug=='gpt-6.1-sol' else 'VERIFY',
      'Runtime has no hosted web search; Mantle requires exact model/tool/Region verification.','S11','OAI-BEDROCK')
     interactions=[]
     if schema:
      interactions.append(dict(required_features=['structured_outputs','streaming'],
       **claim('YES' if slug=='gpt-6.1-sol' else 'VERIFY',
        'Streaming and non-streaming schema output explicitly documented.' if slug=='gpt-6.1-sol' else 'Schema contract documents non-streaming or does not establish simultaneous streaming.',source)))
     path='/openai/v1/responses' if response else '/openai/v1/chat/completions' if api=='chat_completions' else '/model/{model_id}/'+api
     base='https://'+ep+'.{region}.'+('amazonaws.com' if runtime else 'api.aws')
     url=base+('/openai/v1' if api in ['responses','chat_completions'] else '')
     route=dict(id=route_id,model_name=name,model_id=mid,base_model_id='openai.'+slug,endpoint=ep,api=api,
      inference_mode=mode,processing_geography=geo,entry_regions=entry_regions,partition=partition,
      base_url_template=url,inference_path=path,sources=[source,'S04'],features=caps,cache=cache,
      limits={**limits,'sources':[source]},interactions=interactions,
      region_constraints={},service_tiers=['standard'],pricing_sources=[source],
      request_contract={'schema_field':{'responses':'text.format','chat_completions':'response_format','invoke':'response_format','converse':'outputConfig.textFormat'}[api],
       'schema_notes':'Validate schema subset, refusals and incomplete output. Converse additionally needs additionalModelRequestFields.text.format.strict=true when documented.',
       'stream_path':path.replace('/converse','/converse-stream').replace('/invoke','/invoke-with-response-stream') if api in ['converse','invoke'] else path,
       'tools_note':caps['client_tools']['reason']})
     if slug in ['gpt-6-astra','gpt-6.1-sol'] and response:
      route['service_tiers'].append('ultrafast')
      if not runtime:route['ultrafast_regions']=['us-east-1']
     for region in entry_regions:
      if mode=='geographic' and region.startswith('ca-'):
       route['region_constraints'][region]=claim('VERIFY','US profile label is insufficient: Canadian source/destination routing must be checked against residency requirements.',source,'S14')
      if slug=='gpt-6.1-sol' and mode=='global':
       route['region_constraints'][region]=claim('VERIFY','Card lists Global profile but does not enumerate its source Regions; verify this entry Region.',source)
     r['routes'].append(route)
  r['conflicts'] += ([{'model':name,'field':'limits','sources':[source,oid],
   'resolution':'Use AWS route limits for Bedrock, preserve OpenAI direct limits separately; confirm exact token accounting before large requests.'}] if slug=='gpt-6.1-sol' else [])
 r['conflicts'] += [
  {'model':'GPT-6 Astra','field':'Mantle Regions','sources':['AWS-ASTRA','OAI-BEDROCK'],'resolution':'AWS model card is the deployment authority; OpenAI guide lists a narrower older example.'},
  {'model':'GPT-5.4 / GPT-5.5','field':'context window','sources':['AWS-54','AWS-55','OAI-BEDROCK'],'resolution':'AWS model cards list 1,050,000; OpenAI Bedrock guide says 1 million. Check exact accounting for requests approaching the limit.'}]
 for source_record in r['sources']:
  used=sorted({f for route in r['routes'] for f,c in route['features'].items() if source_record['id'] in c['sources']})
  source_record['review_status']='claim_scoped_review' if used else 'captured_reference'
  source_record['reviewed_feature_claims']=used
  source_record['review_note']='Review applies to cited claims only, not every statement on the page.'
 (ROOT/'data/capabilities.json').write_text(json.dumps(r,indent=2)+'\n')
 print(f'Built {len(r["models"])} models, {len(r["routes"])} routes, {len(FEATURES)} features, {len(sources)} snapshots.')


if __name__=='__main__':main()
