#!/usr/bin/env python3
"""Customer-operated deployment page. AWS CLI and Terraform execute on this host."""
import argparse
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from urllib.request import urlopen, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parent
RUNNERS = []  # Retain child handles while an embedding caller stays alive.
spec = importlib.util.spec_from_file_location('package_verifier', ROOT / 'verify_package.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def need(condition, message):
    if not condition:
        raise ValueError(message)

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')
    path.chmod(0o600)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

class Deployment:
    def __init__(self, package, work):
        self.package, self.work = Path(package).resolve(), Path(work).resolve()
        need(not self.work.exists(), 'Choose a new private run directory; existing state must be preserved.')
        need(not self.work.is_relative_to(self.package), 'Run directory must be outside the sealed package.')
        verifier.verify(self.package)
        self.seal = digest(self.package / 'checksums.sha256')
        self.target = verifier.load(self.package / 'deployment/target.json')
        need(self.target.get('contract') == 'aws-deployment-target-v1', 'Unsupported deployment target')
        self.work.mkdir(mode=0o700, parents=True)
        self.plan = None
        self.consumed = False
        self.last = {}

    def verify(self):
        verifier.verify(self.package)
        need(digest(self.package / 'checksums.sha256') == self.seal, 'Package changed; start a new review.')

    def status(self):
        self.verify()
        validation = verifier.load(self.package / 'validation.json')
        ready = validation['readiness'] in ('build_verified', 'deployment_verified') and not validation['blockers']
        return dict(title='AWS deployment', button='Deploy to AWS' if ready else 'Prepare AWS deployment',
                    ready=ready, blockers=validation['blockers'], readiness=validation['readiness'],
                    target=self.target, result=self.last)

    def run(self, args, cwd=None, timeout=180):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('TF_CLI_ARGS', 'TF_VAR_', 'TF_WORKSPACE'))}
        env.update(AWS_PAGER='', TF_IN_AUTOMATION='1', TF_INPUT='0')
        result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout)
        # Detailed logs can contain provider values. Keep them on the customer host only.
        log = self.work / ('command-' + secrets.token_hex(6) + '.json')
        write(log, dict(command=args, code=result.returncode, stdout=result.stdout, stderr=result.stderr))
        need(result.returncode == 0, f'{args[0]} {args[1]} failed; inspect private log {log.name}')
        return result.stdout

    def aws(self, values, *args):
        return json.loads(self.run(['aws', *args, '--region', values['region'], '--output', 'json']))

    def inputs(self, values):
        need(isinstance(values, dict), 'Inputs must be an object')
        fields = self.target['inputs']
        need(set(values) == {f['name'] for f in fields}, 'Supply exactly the declared inputs')
        for field in fields:
            value = values[field['name']]
            need(value is not None and value != '', 'Missing input: ' + field['label'])
            if field.get('choices'):
                need(value in field['choices'], 'Unsupported choice: ' + field['label'])
        need(re.fullmatch(r'[0-9]{12}', values.get('account_id', '')), 'Account must contain 12 digits')
        need(re.fullmatch(r'[a-z]{2}(?:-[a-z]+)+-\d', values.get('region', '')), 'Invalid Region')
        return values

    def preflight(self, values):
        self.plan = None
        self.verify()
        self.inputs(values)
        checks = []
        def check(name, fn):
            try:
                fn()
                checks.append(dict(name=name, status='passed'))
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                checks.append(dict(name=name, status='blocked', reason=str(exc)))
        def identity():
            actual = self.aws(values, 'sts', 'get-caller-identity')
            need(actual['Account'] == values['account_id'], 'Signed-in AWS account differs from target')
        check('AWS account access', identity)
        if checks[-1]['status'] != 'passed':
            self.last = dict(stage='preflight', checks=checks)
            write(self.work / 'preflight.json', self.last)
            return self.last
        check('Package build readiness', lambda: need(self.status()['ready'], 'Required builds, application ports, or blockers remain'))
        for quota in self.target.get('quotas', []):
            def quota_check(q=quota):
                result = self.aws(values, 'service-quotas', 'get-service-quota', '--service-code', q['service'], '--quota-code', q['code'])
                need(result['Quota']['Value'] >= q['required_total'], 'Quota is below existing usage plus planned demand')
                need(time.time() - q['usage_checked_at'] < 3600, 'Refresh existing quota usage and required total in the package')
            check('Quota: ' + quota['code'], quota_check)
        check('Quota coverage', lambda: need(bool(self.target.get('quotas')), 'Package needs workload-specific quota requirements'))
        for model in self.target.get('models', []):
            def model_check(m=model):
                ident = values[m['input']]
                need(all(x not in ident.lower() for x in ('gpt-oss', 'daybreak', 'cyber')), 'GPT-OSS and Daybreak are excluded')
                need(ident in m['approved_ids'], 'Model ID is not approved by this assessment')
                need(m['endpoint'] in ('bedrock-runtime', 'bedrock-mantle'), 'Unsupported model endpoint')
                need(m.get('route_verified') is True, 'Endpoint and API compatibility remain unverified')
                need(not ident.startswith(('us.', 'in.', 'global.')) and m['endpoint'] == 'bedrock-runtime',
                     'This portal verifier supports foundation-model IDs only; a profile/Mantle route needs an account-specific verifier. Do not substitute a model.')
                result = self.aws(values, 'bedrock', 'get-foundation-model-availability', '--model-id', ident)
                need(result.get('authorizationStatus') == 'AUTHORIZED' and result.get('regionAvailability') == 'AVAILABLE'
                     and result.get('agreementAvailability', {}).get('status') == 'AVAILABLE'
                     and result.get('entitlementAvailability') == 'AVAILABLE', 'Model access is not fully available')
            check('Model access: ' + model['input'], model_check)
        for image in self.target.get('images', []):
            def image_check(i=image):
                uri = values[i]
                match = re.fullmatch(re.escape(values['account_id'] + '.dkr.ecr.' + values['region'] + '.amazonaws.com/') + r'([a-z0-9._/-]+)@(sha256:[a-f0-9]{64})', uri)
                need(match, 'Supply a digest-pinned ECR image in the target account and Region')
                self.aws(values, 'ecr', 'describe-images', '--repository-name', match[1], '--image-ids', 'imageDigest=' + match[2])
            check('Image: ' + image, image_check)
        self.last = dict(stage='preflight', checks=checks)
        write(self.work / 'preflight.json', self.last)
        return self.last

    def make_plan(self, values):
        need(not self.consumed, 'This run has already attempted deployment; review retained state before another run')
        result = self.preflight(values)
        need(all(c['status'] == 'passed' for c in result['checks']), 'Resolve preflight blockers before planning')
        need(self.target.get('execution_reviewed') is True, 'Terraform execution and backend require package review')
        need(bool(self.target.get('health_checks')), 'Define required workload health checks before deployment')
        source = (self.package / self.target['terraform_root']).resolve()
        need(source.is_relative_to(self.package) and source.is_dir(), 'Invalid Terraform directory')
        tf = self.work / 'terraform'
        if not tf.exists():
            shutil.copytree(source, tf)
        variables = dict(self.target.get('variables', {}))
        for field in self.target['inputs']:
            if field.get('terraform_variable'):
                variables[field['terraform_variable']] = values[field['name']]
        write(tf / 'portal.auto.tfvars.json', variables)
        self.run(['terraform', 'init', '-input=false', '-lockfile=readonly'], tf, 600)
        self.run(['terraform', 'validate', '-no-color'], tf)
        saved = tf / 'approved.tfplan'
        self.run(['terraform', 'plan', '-input=false', '-no-color', '-out=' + str(saved)], tf, 900)
        plan_json = json.loads(self.run(['terraform', 'show', '-json', str(saved)], tf))
        changes = [dict(address=r['address'], actions=r['change']['actions']) for r in plan_json.get('resource_changes', [])]
        need(not any('delete' in c['actions'] for c in changes), 'This deployment page does not approve deletion or replacement; use a separate reviewed workflow')
        self.plan = dict(hash=digest(saved), values=values, created=time.time(), changes=changes)
        write(self.work / 'approval-review.json', self.plan)
        self.last = dict(stage='plan', plan=self.plan, message='Review resource actions, target account, and cost assumptions before approving.')
        return self.last

    def apply(self, request):
        need(self.plan is not None and not self.consumed, 'Create and review a fresh plan first')
        self.verify()
        need(self.status()['ready'], 'Package is no longer ready')
        need(request.get('plan_hash') == self.plan['hash'], 'Approval must match the displayed plan')
        need(request.get('account_confirmation') == self.plan['values']['account_id'], 'Type the target account to approve')
        need(time.time() - self.plan['created'] < 900, 'Plan approval expired; rerun preflight and plan')
        saved = self.work / 'terraform/approved.tfplan'
        need(digest(saved) == self.plan['hash'], 'Saved plan changed')
        values = self.plan['values']
        need(self.aws(values, 'sts', 'get-caller-identity')['Account'] == values['account_id'], 'AWS identity changed')
        self.consumed = True
        write(self.work / 'deployment-started.json', dict(plan_hash=self.plan['hash'], started=time.time()))
        try:
            self.run(['terraform', 'apply', '-input=false', '-no-color', str(saved)], saved.parent, 3600)
            health = []
            for item in self.target.get('health_checks', []):
                url = 'https://' + values[item['domain_input']] + item['path']
                need(re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', values[item['domain_input']]), 'Invalid health-check domain')
                need(item['path'].startswith('/') and not item['path'].startswith('//'), 'Invalid health-check path')
                parsed = urlparse(url)
                need(parsed.hostname == values[item['domain_input']] and not parsed.username and not parsed.port, 'Invalid health-check domain')
                ok = False
                for _ in range(6):
                    try:
                        with build_opener(NoRedirect).open(url, timeout=10) as response:
                            ok = response.status == item.get('status', 200)
                    except OSError:
                        pass
                    if ok:
                        break
                    time.sleep(2)
                health.append(dict(url=url, passed=ok))
            self.last = dict(stage='deployed', health=health, healthy=bool(health) and all(h['passed'] for h in health))
        except Exception:
            self.last = dict(stage='deployment_failed', message='Partial resources may exist. Inspect retained state and logs; do not retry blindly.')
            write(self.work / 'deployment-result.json', self.last)
            raise
        write(self.work / 'deployment-result.json', self.last)
        return self.last

def export_page(package, output):
    package, output = Path(package).resolve(), Path(output).resolve()
    verifier.verify(package)
    need(not output.exists(), 'Export directory must be new')
    need(not output.is_relative_to(package), 'Export outside the sealed package')
    validation = verifier.load(package / 'validation.json')
    ready = validation['readiness'] in ('build_verified', 'deployment_verified') and not validation['blockers']
    status = dict(ready=ready, button='Deploy to AWS' if ready else 'Prepare AWS deployment',
                  readiness=validation['readiness'], blockers=validation['blockers'],
                  target=verifier.load(package / 'deployment/target.json'))
    output.mkdir(parents=True)
    page = (ROOT.parent / 'assets/deployment-page.html').read_text()
    embedded = json.dumps(status).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    page = page.replace('<script>', '<script type="application/json" id="package-data">' + embedded + '</script><script>', 1)
    (output / 'deployment.html').write_text(page)
    report = '<!doctype html><html lang="en"><meta charset="utf-8"><title>AWS migration assessment</title><style>body{max-width:1000px;margin:48px auto;padding:24px;font:16px system-ui;color:#172b3a}pre{white-space:pre-wrap;line-height:1.6}a{display:inline-block;padding:16px;background:#0069bd;color:white;border-radius:6px}</style><h1>AWS migration assessment</h1><pre>'
    report += html.escape((package / 'assessment.md').read_text()) + '</pre><a href="deployment.html">' + status['button'] + '</a></html>'
    (output / 'report.html').write_text(report)
    return output / 'report.html'

def serve(deployment, port=0):
    token = secrets.token_urlsafe(32)
    asset = ROOT.parent / 'assets/deployment-page.html'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def reply(self, value, code=200, kind='application/json'):
            data = value if isinstance(value, bytes) else json.dumps(value).encode()
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(data)
        def allowed(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'
        def do_GET(self):
            if not self.allowed():
                return self.reply({'error': 'Invalid host'}, 403)
            if self.path == '/':
                return self.reply(asset.read_bytes(), kind='text/html; charset=utf-8')
            if self.path == '/report':
                return self.reply((ROOT.parent / 'assets/deployment-report.html').read_bytes(), kind='text/html; charset=utf-8')
            if self.path == '/assessment' and self.headers.get('X-Portal-Token') == token:
                try:
                    status = deployment.status()
                    return self.reply(dict(assessment=(deployment.package / 'assessment.md').read_text(),
                                           button=status['button'], readiness=status['readiness']))
                except Exception as exc:
                    return self.reply({'error': str(exc)}, 400)
            if self.path == '/status' and self.headers.get('X-Portal-Token') == token:
                try:
                    return self.reply(deployment.status())
                except Exception as exc:
                    return self.reply({'error': str(exc)}, 400)
            self.reply({'error': 'Not found'}, 404)
        def do_POST(self):
            if not self.allowed() or self.headers.get('X-Portal-Token') != token or self.headers.get('Origin') != f'http://127.0.0.1:{self.server.server_port}':
                return self.reply({'error': 'Invalid session'}, 403)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                need(0 < length < 65536, 'Invalid request size')
                body = json.loads(self.rfile.read(length))
                action = {'/preflight': deployment.preflight, '/plan': deployment.make_plan, '/apply': deployment.apply}.get(self.path)
                need(action, 'Unknown action')
                self.reply(action(body))
            except Exception as exc:
                self.reply({'error': str(exc)}, 400)
    server = HTTPServer(('127.0.0.1', port), Handler)
    report_url = f'http://127.0.0.1:{server.server_port}/report#{token}'
    write(deployment.work / 'session.json', dict(pid=os.getpid(), report_url=report_url,
          package=str(deployment.package), package_seal=deployment.seal))
    print(f'Open http://127.0.0.1:{server.server_port}/#{token}', flush=True)
    print('Retain the private run directory for Terraform state, logs, and deployment receipts.', flush=True)
    server.serve_forever()

def launch(package, work, open_browser=False):
    """Start the customer runner and return only after its authenticated report responds."""
    package, work = Path(package).resolve(), Path(work).resolve()
    need(not work.exists(), 'Choose a new run directory; preserve existing deployment state.')
    verifier.verify(package)
    need((package / 'deployment/target.json').is_file(), 'Package has no deployment target')
    log = tempfile.NamedTemporaryFile(prefix='az2aws-launch-', suffix='.log', delete=False)
    child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), str(package),
                              '--run-directory', str(work)], stdin=subprocess.DEVNULL,
                             stdout=log, stderr=log, start_new_session=True)
    log.close()
    session_path = work / 'session.json'
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            need(child.poll() is None, 'Runner failed to start; inspect ' + log.name)
            if session_path.is_file():
                session = json.loads(session_path.read_text())
                url = session['report_url']
                parsed = urlparse(url)
                from urllib.request import Request
                request = Request(url.split('/report#')[0] + '/assessment',
                                  headers={'X-Portal-Token': parsed.fragment})
                with urlopen(request, timeout=5) as response:
                    need(response.status == 200, 'Report readiness check failed')
                # This customer-private handoff is deliberately outside the shared package.
                handoff = work / 'open-report.html'
                handoff.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Open migration report</title><h1>Migration report</h1><p>The deployment runner is ready on this computer.</p><a href="' + html.escape(url, quote=True) + '">Open report and deployment session</a><p>If the runner has stopped, ask Codex to reopen the deployment report. Keep this file private.</p></html>')
                handoff.chmod(0o600)
                if open_browser:
                    webbrowser.open(url)
                RUNNERS.append(child)
                return dict(report_url=url, handoff=str(handoff), pid=child.pid, run_directory=str(work))
            time.sleep(.1)
        raise ValueError('Runner did not become ready; inspect ' + log.name)
    except Exception:
        child.terminate()
        child.wait(timeout=10)
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--run-directory', type=Path)
    parser.add_argument('--export', type=Path, help='Export a portable report and preparation page without cloud calls')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--launch', action='store_true', help='Start a background runner and return a verified live report URL')
    parser.add_argument('--open', action='store_true', help='Open the live report in this computer’s browser')
    args = parser.parse_args()
    if args.export:
        print(export_page(args.package, args.export))
    else:
        need(args.run_directory, 'Supply --run-directory to start an execution session')
        if args.launch:
            print(json.dumps(launch(args.package, args.run_directory, args.open)))
        else:
            serve(Deployment(args.package, args.run_directory), args.port)
