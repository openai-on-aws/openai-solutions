"""Create a Project, run inference inside it, and archive it.

A Project is the boundary Bedrock authorizes inference on. IAM grants
`bedrock-mantle:CreateInference` on a **project ARN**, so a project is what separates
one workload from another inside a single AWS account — and because a project carries
AWS tags, it is also what attributes that workload's cost in Cost Explorer.

  A. what exists now   every account starts with a `default` project
  B. create            one POST, with the tags that drive cost attribution
  C. use it            two ways to associate a call with a project
  D. retention         set the project's data retention mode, once
  E. the ARN           what you put in an IAM policy to isolate a workload
  F. archive           tidy up, and see what archiving does

The Projects API lives on the `/v1` router and is not exposed by the OpenAI SDK, so
this recipe signs plain HTTP requests with SigV4. That is more code than the rest of
the cookbook shows, and it is all in one helper you can lift. See README.md.
"""

import json
import os
import urllib.error
import urllib.request

import boto3
import botocore.session
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from openai import OpenAI
from openai.providers import bedrock

from cookbook_utils import mask_account_ids

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-luna")

PROJECT_NAME = "cookbook-support-assistant"

# Tags are the whole point of creating a project rather than using `default`: they are
# what Cost Explorer groups by, so choose keys your finance team already reports on.
PROJECT_TAGS = {
    "Project": "SupportAssistant",
    "Environment": "Sandbox",
    "Owner": "TeamAlpha",
    "CostCenter": "21524",
}

# Set KEEP_PROJECT=1 to leave the project in place after the run — useful if you want to
# look at it in the console or reference its ARN in a policy.
KEEP_PROJECT = os.environ.get("KEEP_PROJECT") == "1"

# The Projects API is on the open-weight /v1 router. The OpenAI-model router,
# /openai/v1, returns 404 for it.
PROJECTS_BASE = f"https://bedrock-mantle.{REGION}.api.aws/v1/organization/projects"

session = botocore.session.get_session()
CREDENTIALS = session.get_credentials().get_frozen_credentials()
ACCOUNT = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]



def projects_api(method: str, path: str = "", body: dict | None = None) -> dict:
    """Call the Projects API with a SigV4-signed request.

    The OpenAI SDK does not expose these operations, so the request is built and
    signed by hand. Everything about it is standard AWS: botocore signs for service
    `bedrock-mantle` using whatever credentials the environment already has.
    """
    url = PROJECTS_BASE + path
    payload = json.dumps(body).encode() if body is not None else None
    request = AWSRequest(
        method=method,
        url=url,
        data=payload,
        headers={"Content-Type": "application/json"} if payload else {},
    )
    SigV4Auth(CREDENTIALS, "bedrock-mantle", REGION).add_auth(request)

    sendable = urllib.request.Request(
        url, data=payload, method=method, headers=dict(request.headers.items())
    )
    with urllib.request.urlopen(sendable, timeout=40) as response:
        return json.loads(response.read().decode())


print(f"Projects on bedrock-mantle  ·  {REGION}")
print("Projects are the resource IAM authorizes inference on, and the unit of")
print("cost attribution. Every call in this cookbook lands in one, named or not.\n")

# --- A. What exists now -----------------------------------------------------

print("=" * 78)
print("A. What is already there")
print("=" * 78)
print("→ request   GET /v1/organization/projects")

existing = projects_api("GET")["data"]
# Only the `default` project is named. Anything else in the account belongs to another
# workload, and this output is the kind of thing a reader pastes into a document.
default = next((p for p in existing if p["id"] == "default"), None)
print("← response")
if default is not None:
    tags = default.get("tags") or {}
    print(f"   default   status {default.get('status', '?')}   {len(tags)} tag(s)")
others = len(existing) - (1 if default else 0)
print(f"   plus {others} other project(s) in this Region, not shown")
print("   Every account starts with `default`, and that is where inference lands when")
print("   you name no project — including every other recipe in this cookbook.\n")

# --- B. Create one ----------------------------------------------------------

print("=" * 78)
print("B. Create a project")
print("=" * 78)
print("→ request   POST /v1/organization/projects")
print(f"   name      {PROJECT_NAME}")
print(f"   tags      {json.dumps(PROJECT_TAGS)}")
print("   why tags  they are what Cost Explorer groups by, so this is the step that")
print("             turns a project into a cost centre rather than just a boundary")

created = projects_api("POST", body={"name": PROJECT_NAME, "tags": PROJECT_TAGS})
project_id = created["id"]
project_arn = created["arn"]

print("← response")
print(f"   id              {project_id}")
print(f"   arn             {mask_account_ids(project_arn)}")
print(f"   status          {created['status']}")
print(f"   object          {created['object']}")
print(f"   data_retention  {created.get('data_retention')}")
print("   The `arn` field is a Bedrock addition to the OpenAI response shape. It is")
print("   what you reference in an IAM policy — see step E.\n")

# --- C. Use it --------------------------------------------------------------

print("=" * 78)
print("C. Associate inference with the project")
print("=" * 78)
print("→ request   two ways to say which project a call belongs to")
print(f"   model     {MODEL_ID}")
print(f"   project   {project_id}")

scoped = OpenAI(provider=bedrock(region=REGION), project=project_id, max_retries=3)
first = scoped.responses.create(
    model=MODEL_ID,
    input="Reply with the single word: scoped.",
    reasoning={"effort": "none"},
    max_output_tokens=16,
    store=False,
)
print("← response")
print(f"   OpenAI(project=...) on the client   {first.output_text.strip()!r}")

plain = OpenAI(provider=bedrock(region=REGION), max_retries=3)
second = plain.responses.create(
    model=MODEL_ID,
    input="Reply with the single word: scoped.",
    reasoning={"effort": "none"},
    max_output_tokens=16,
    store=False,
    extra_headers={"OpenAI-Project": project_id},
)
print(f"   OpenAI-Project header per request   {second.output_text.strip()!r}")
print("   Set it on the client when a service belongs to one project, which is the")
print("   usual case. Use the header when one process serves several tenants and")
print("   the project varies per request.\n")

# --- D. Data retention, set once per project --------------------------------

print("=" * 78)
print("D. Data retention, set once for the project")
print("=" * 78)
print("   A project carries its own retention mode, so you set it once here rather")
print("   than on every request. The effective mode for a call is the first")
print("   non-`inherit` value of project → account → the model's own default.")
print()
print("   The four modes:")
print("     inherit              defer to the account, then to the model. The")
print("                          default for a new project — you saw it in step B")
print("     default              the model's own retention policy applies")
print("     provider_data_share  AWS may retain and share with the model provider,")
print("                          which some models require before they can be used")
print("     none                 zero data retention")
print()
print("→ request   POST /v1/organization/projects/{id}")
print('   body      {"data_retention": {"mode": "..."}}')
print("   why       a model declares which modes it accepts in allowed_modes, so a")
print("             mode it does not accept makes that model unavailable")

for mode in ("none", "default"):
    updated = projects_api("POST", f"/{project_id}",
                           body={"data_retention": {"mode": mode}})
    print(f"\n←  project mode set to {mode!r}: {updated.get('data_retention')}")

    # Read the model as this project sees it. The retention fields are a Bedrock
    # addition, so they arrive in model_extra rather than on the typed class.
    catalogue = OpenAI(
        provider=bedrock(region=REGION,
                         base_url=f"https://bedrock-mantle.{REGION}.api.aws/v1"),
        project=project_id,
    )
    model = catalogue.models.retrieve(MODEL_ID)
    extra = model.model_extra or {}
    retention = extra.get("data_retention", {})
    print(f"   {MODEL_ID} is {extra.get('status')!r}")
    print(f"     allowed_modes {retention.get('allowed_modes')}")
    print(f"     effective     {retention.get('mode')!r} (source: "
          f"{retention.get('source')!r})")
    if extra.get("status_reason"):
        print(f"     reason        {extra['status_reason']}")

    try:
        probe = scoped.responses.create(
            model=MODEL_ID,
            input="Reply with the single word: ok.",
            reasoning={"effort": "none"},
            max_output_tokens=16,
            store=False,
        )
        print(f"   inference     200 {probe.output_text.strip()!r}")
    except Exception as blocked:
        print(f"   inference     {type(blocked).__name__}: {str(blocked)[:96]}")

print()
print("   Read allowed_modes rather than assuming: it is per model AND per account.")
print("   On a standard account the GPT-5.6 models offer `default` and")
print("   `provider_data_share`, so a project set to `none` makes them unavailable.")
print()
print("   `none` is reachable, though. Zero data retention is granted per account and")
print("   per model: if you need it, AWS evaluates eligibility, and an approved")
print("   account sees `none` appear in that model's allowed_modes. So the check above")
print("   is also how you confirm whether your account already has it.")
print()
print("   AWS does not share request or response content with OpenAI under")
print("   `default` or `none`.")
print("   Under `default`, classifier-flagged traffic is retained up to 30 days for")
print("   automated abuse detection, and a stored response is kept for 30 days.")
print()
print("   Full reference, including account-level configuration and the SCP condition")
print("   key that enforces a mode across an organisation:")
print("   https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html\n")

# --- E. The ARN is the point ------------------------------------------------

print("=" * 78)
print("E. What the ARN is for")
print("=" * 78)
policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "InferenceInThisProjectOnly",
        "Effect": "Allow",
        "Action": "bedrock-mantle:CreateInference",
        "Resource": project_arn,
    }],
}
print("   An identity holding this policy can run inference in this project and")
print("   nowhere else in the account:")
for line in json.dumps(policy, indent=2).splitlines():
    print(f"     {mask_account_ids(line)}")
print()
print("   That is the difference between a project and a tag. A tag describes a")
print("   resource; a project IS the resource, so it can carry permissions. Two")
print("   teams in one account get a project each, and neither can spend the")
print("   other's quota or read the other's stored responses.\n")

# --- F. Archive -------------------------------------------------------------

print("=" * 78)
print("F. Clean up")
print("=" * 78)
if KEEP_PROJECT:
    print(f"   KEEP_PROJECT=1, so {project_id} is left in place.")
    print("   Archive it later with:")
    print(f"     POST /v1/organization/projects/{project_id}/archive")
else:
    print(f"→ request   POST /v1/organization/projects/{project_id}/archive")
    archived = projects_api("POST", f"/{project_id}/archive")
    print("← response")
    print(f"   status       {archived['status']}")
    print(f"   archived_at  {archived.get('archived_at')}")
    print("   Archiving is the delete: the record stays, so historical cost data")
    print("   keeps its project attribution, and no new inference can be run in it.")

print("\nProjects themselves are free. What they organise is the model usage:")
print("https://aws.amazon.com/bedrock/pricing/")
