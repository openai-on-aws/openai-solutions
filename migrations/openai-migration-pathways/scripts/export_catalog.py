#!/usr/bin/env python3
"""Generate readable catalog and application route data from the reviewed registry."""
import argparse
import json
from pathlib import Path
from evaluate_routes import DEFAULT_REGISTRY, registry_hash, validate_registry


def outputs(r):
    digest=registry_hash(r)
    def table(headers,rows):
        def cell(x):return str(x).replace('|','/').replace('\n',' ')
        return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(cell(v) for v in row)+' |' for row in rows])
    text='# OpenAI Bedrock compatibility catalog\n\n'
    text+=f'Release {r["registry_version"]}. Evidence reviewed {r["snapshot_date"]}. Registry SHA-256: `{digest}`.\n\n'
    text+='Documentation compatibility only. YES does not establish account access or runtime behavior. Evaluate required combinations with evaluate_routes.py. GPT-OSS and Daybreak are excluded.\n\n'
    text+=table(['Model','AWS context tokens','AWS max output','Sources'],[[m['name'],m['limits']['context_tokens'],m['limits']['max_output_tokens'],', '.join(m['evidence_sources'])] for m in r['models']])+'\n\n'
    text+='## Exact route definitions\n\n'
    text+=table(['Model','Endpoint','API','Routing','Partition','Entry Regions','Implicit cache','Explicit cache','Schema','Inline safety'],[[x['model_name'],x['endpoint'],x['api'],x['model_id'],x['partition'],', '.join(x['entry_regions']),x['cache']['implicit']['status'],x['cache']['explicit']['status'],x['features']['structured_outputs']['status'],x['features']['inline_guardrails']['status']] for x in r['routes']])+'\n\n'
    text+='## Documentation differences\n\n'+''.join('- '+c['model']+' / '+c['field']+': '+c['resolution']+' Sources: '+', '.join(c['sources'])+'.\n' for c in r['conflicts'])
    text+='\n## Sources\n\n'+table(['ID','Scope','Retrieved','Official documentation'],[[s['id'],s['scope'],s['checked_at'][:10],s['url']] for s in r['sources']])+'\n'
    routes=[]
    for x in r['routes']:
        if x['api']!='responses':continue
        # Adapter rejects unresolved entry-region routes, including provisional 6.1 global ingress.
        regions=[region for region in x['entry_regions'] if region not in x['region_constraints']]
        if not regions:continue
        routes.append(dict(policy=x['base_model_id'].removeprefix('openai.'),model_id=x['model_id'],
            endpoint=x['endpoint'],inference_scope={'in_region':'in-region','global':'global'}.get(x['inference_mode'],x['model_id'].split('.')[0]),
            entry_regions=regions,base_url_template=x['base_url_template']))
    adapter=dict(registry_version=r['registry_version'],registry_sha256=digest,reviewed_at=r['snapshot_date'],
        scope='Responses transport configuration only; not application or account verification.',routes=routes)
    return {'docs/compatibility-catalog.md':text,'assets/python-bedrock/approved-routes.json':json.dumps(adapter,indent=2)+'\n'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    r=json.loads(DEFAULT_REGISTRY.read_text());validate_registry(r,DEFAULT_REGISTRY.parent)
    for name,text in outputs(r).items():
        path=DEFAULT_REGISTRY.parent.parent/name
        if a.check:
            if path.read_text()!=text:raise ValueError('Generated artifact differs: '+name)
        else:path.write_text(text)
    print('Catalog and adapter exports '+('match.' if a.check else 'updated.'))


if __name__=='__main__':main()
