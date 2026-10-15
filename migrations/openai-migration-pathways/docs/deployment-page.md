# Deployment page

The plugin can deliver a customer-operated deployment page with a sealed assessment. Start it from the installed plugin root:

```sh
python3 -B scripts/deployment_portal.py /absolute/path/package --run-directory /absolute/path/new-private-run --launch --open
```

The launcher starts a background runner, verifies the authenticated report endpoint, and opens the report in the customer's browser. Its final button enters the live deployment session directly. Without `--open`, the launcher returns the verified report URL for Codex to hand off. A private `open-report.html` link is also stored in the run directory. The report checks session availability before navigation; invalid sessions show a recovery message and disable the button. Refreshing either page preserves the session in browser session storage.

The runner uses standard Python, the customer's configured AWS CLI credentials, and Terraform on the same host. Bindings are loopback only. Run the launcher on the customer's browser host. A remote customer runner needs an approved authenticated tunnel; a localhost URL from the publisher's machine cannot serve a customer's browser. The plugin does not provision hosting or install an OS URL handler. Starting the launcher performs package checks only, with no cloud calls.

Codex should launch this report as part of an explicitly requested live deployment handoff, rather than asking the customer to start a separate runner. For a shared static archive, retain the offline export. Browsers cannot start arbitrary local processes from HTML alone, so the live runner must remain running while the report is used. The session receipt records its PID for the operator to stop after use; retain all deployment state and logs.

The page displays target inputs, resources, cost assumptions, package blockers, preflight results and saved-plan resource actions. Credentials stay on the runner. Clicking the access consent enables read-only AWS checks and Terraform planning. Apply requires the saved plan hash and typed target account, expires after 15 minutes, and cannot be repeated within a run. Changed package bytes invalidate the session. Terraform deletion and replacement plans require a separate workflow.

Retain the private run directory: it contains Terraform state, plan, logs and receipts, potentially including sensitive provider values. Never include it in a shared assessment archive. A failed apply may leave resources; reconcile retained state before another deployment. Use a reviewed remote state backend with locking for team operations. The portal does not automatically roll back or destroy resources.

## Package contract

Before sealing, create `deployment/target.json` with:

- `contract`: `aws-deployment-target-v1`.
- `terraform_root`: package-relative directory containing the reviewed root module and provider lockfile. Remote backend configuration and allowed AWS account/Region must be enforced by that module.
- `execution_reviewed`: true only after reviewing providers, modules, provisioners, account restrictions, backend and all required workload implementation. False permits preparation but blocks planning.
- `inputs`: list of `{name, label, default, terraform_variable}`. Names include `account_id` and `region`. Optional `choices` limits accepted values; `type: json` supports structured workload inputs. Use image digest, domain and model fields as needed, mapped to actual root-module variables. Never accept secrets here.
- `variables`: other reviewed non-secret Terraform input values.
- `resources`: readable list of planned resources; actual actions are subsequently shown from the Terraform plan.
- `cost`: `{currency, monthly_low, monthly_high, assumptions, source}`. Use null bounds when sizing or rates are unknown. Record rate date, traffic, token, storage and availability assumptions. The portal displays this estimate; it does not invent a quote or query live pricing.
- `quotas`: `{service, code, required_total, usage_checked_at}` entries. Total includes existing consumption plus incremental demand; usage time is UTC epoch seconds and must be less than one hour old. Empty coverage blocks planning. Refresh usage from authorized inventory and reseal before launching a new session.
- `models`: `{input, approved_ids, endpoint, route_verified}` entries. Only verified foundation-model IDs can pass the bundled availability query. Inference-profile IDs and Mantle routes are explicitly blocked by the generic verifier until an account-specific verifier is provided; never substitute another model.
- `images`: input names containing target-account ECR digest references.
- `health_checks`: `{domain_input, path, status}` entries. HTTPS only, no redirects. Define checks for the required workload routes; a successful HTTP check is narrower than complete application acceptance testing.

The package must pass its existing verifier and have `build_verified` or `deployment_verified` readiness with no outstanding blockers to offer deployment. The sample remains in preparation mode. The runner rechecks identity before applying the exact saved plan. AWS permission checks and Terraform planning cannot guarantee every apply-time permission or quota will succeed.

## Report entry point

Generate a portable report with a final button and an offline preparation page:

```sh
python3 -B scripts/deployment_portal.py /absolute/path/package --export /absolute/path/new-report-directory
```

The exported `report.html` links to `deployment.html`. It displays the sealed assessment and missing inputs without credentials or a server. Execution controls explain how to start the customer runner; the live session provides checks, planning and approval. Static HTML cannot itself run Terraform.

Add a final **Prepare AWS deployment** link to the generated HTML report. Once a runner session is started, point it to the printed session URL; this capability URL must stay with its customer/operator. A static shared report should link to the deployment instructions, not an expiring session or the publisher's machine. Use **Deploy to AWS** only when package build readiness and blockers permit it; the page still requires preflight and plan approval.

## Design

Use a quiet white/blue page with system fonts, clearly numbered sections and plain status messages. Target inputs sit beside resources and cost. Approval is a separate bordered section below the plan. All controls have visible keyboard focus, and status updates use live regions. There are no remote fonts, trackers or browser credential fields.

References: [Terraform saved plans](https://developer.hashicorp.com/terraform/cli/commands/apply), [Bedrock model availability](https://docs.aws.amazon.com/cli/latest/reference/bedrock/get-foundation-model-availability.html).
