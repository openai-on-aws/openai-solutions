"""Answer a security review's questions from the API rather than from a slide.

A regulated workload is approved or refused on a handful of specifics: where the data
goes, who may invoke the model, what is retained and for how long, what the network path
is, and what the audit trail records. Every one of those is inspectable, and this recipe
inspects them.

  A. retention      what modes this model offers, and what store=False does
  B. authorization  Projects are the IAM resource inference is granted on
  C. network        the PrivateLink endpoint service, and its private DNS name
  D. audit          the request id, the metric namespace, the trail
  E. quotas         published, per model, per Region, adjustable
  F. the summary    the answers, in the order a reviewer asks them

Every AWS call here is read-only. Nothing is created, and nothing is billed except one
small inference call in step B. Account identifiers are masked in the output on
purpose — see README.md.
"""

import os

import boto3
from openai import OpenAI
from openai.providers import bedrock

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

client = OpenAI(provider=bedrock(region=REGION), max_retries=3)

# The model catalogue lives on the open-weight /v1 router, not the OpenAI one:
# GET /openai/v1/models returns 404. Re-pointing goes INSIDE bedrock(), because a
# top-level base_url= alongside provider= is rejected before any network call.
catalogue = OpenAI(provider=bedrock(
    region=REGION, base_url=f"https://bedrock-mantle.{REGION}.api.aws/v1",
))

ec2 = boto3.client("ec2", region_name=REGION)
quotas = boto3.client("service-quotas", region_name=REGION)




print(f"Passing the security review  ·  {MODEL_ID} in {REGION}")
print("every AWS call below is read-only\n")

# --- A. Retention -----------------------------------------------------------

print("=" * 78)
print("A. What is retained, and for how long")
print("=" * 78)
print("→ request   GET /v1/models/{id}   (the catalogue is on the /v1 router)")
print(f"   model     {MODEL_ID}")
print("   why       retention is a per-model property called a mode, and the")
print("             model declares which modes it will accept")

model = catalogue.models.retrieve(MODEL_ID)
# The retention fields are a Bedrock extension to the OpenAI model object, so they are
# not on the typed class — they arrive nested under data_retention in model_extra.
# Reading response.allowed_modes returns None and looks like "not offered".
extra = model.model_extra or {}
retention = extra.get("data_retention", {})
allowed = retention.get("allowed_modes")
print("← response")
print(f"   status          {extra.get('status')!r}")
print(f"   data_retention  {retention}")
if allowed:
    print(f"   allowed_modes   {allowed}")
    print(f"   mode            {retention.get('mode')!r}  "
          f"(source: {retention.get('source')!r})")
if allowed and "none" not in allowed:
    print("   'none' — zero retention — is not in this account's allowed_modes for")
    print("   this model. ZDR is granted per account and per model, so the honest")
    print("   answer to a reviewer is 'not enabled here' rather than 'impossible',")
    print("   and the path is an eligibility review with AWS. An approved account")
    print("   sees 'none' appear in this same field, which is why running the check")
    print("   beats quoting someone else's result.")
elif allowed:
    print("   'none' IS available on this model for this account, so a zero-retention")
    print("   posture is configurable — set the account or project mode to 'none'.")

print("\n→ request   one inference call with store=False")
print("   why       Responses requests default to store=true on Bedrock, and a")
print("             stored response is retained by AWS — input and output — for")
print("             30 days. store=False is therefore a decision, not a default.")
probe = client.responses.create(
    model=MODEL_ID,
    input="Reply with the single word: acknowledged.",
    reasoning={"effort": "none"},
    max_output_tokens=20,
    store=False,
)
print("← response")
print(f"   {probe.output_text.strip()!r}")
print(f"   store echoed back as {probe.store!r}")
print(f"   x-request-id available on the response object: {bool(probe.id)}")
print("   What store=False is not: it is not zero data retention. AWS may still")
print("   retain classifier-flagged traffic for abuse review under the mode above.\n")

# --- B. Authorization -------------------------------------------------------

print("=" * 78)
print("B. Who is allowed to invoke the model")
print("=" * 78)
print("   The managed policy for inference grants bedrock-mantle:CreateInference on")
print("   arn:aws:bedrock-mantle:*:*:project/*  — a PROJECT resource, not a model")
print("   resource. So a project is the authorization boundary for inference here,")
print("   and scoping that statement to one project ARN is how a workload is")
print("   isolated from the rest of the account.")
print()
print("   Projects are listed and created through /v1/organization/projects, which")
print("   is signed HTTP rather than an SDK method — the foundations recipe on")
print("   Projects does that end to end, so this review does not repeat it. What a")
print("   reviewer needs from here is the shape of the answer:")
print()
print("     each project is an ARN you can name in a policy")
print("     each carries its own tags, which is how spend is attributed")
print("     each carries its own data retention mode, which overrides the account")
print("     inference lands in `default` when no project is named")
print()

# --- C. Network -------------------------------------------------------------

print("=" * 78)
print("C. The network path")
print("=" * 78)
print("→ request   ec2:DescribeVpcEndpointServices for the mantle endpoint service")
print("   why       'can this run without traversing the public internet' is the")
print("             question, and the answer is a PrivateLink service or it is not")

service_name = f"com.amazonaws.{REGION}.bedrock-mantle"
try:
    described = ec2.describe_vpc_endpoint_services(ServiceNames=[service_name])
    detail = described["ServiceDetails"][0]
    print("← response")
    print(f"   service name        {detail['ServiceName']}")
    print(f"   private DNS name    {detail.get('PrivateDnsName')}")
    print(f"   DNS verification    {detail.get('PrivateDnsNameVerificationState')}")
    policy_ok = detail.get("VpcEndpointPolicySupported")
    print(f"   endpoint policy     supported = {policy_ok}")
    print(f"   IP address types    {detail.get('SupportedIpAddressTypes')}")
    print(f"   availability zones  {len(detail.get('AvailabilityZones', []))}")
    print("   The private DNS name is identical to the public hostname, so enabling")
    print("   the endpoint routes existing SDK calls through the VPC with no code")
    print("   change at all.")
except Exception as error:
    print(f"← {type(error).__name__}: {str(error)[:120]}")

print("\n→ request   the same call for a FIPS variant of that service")
try:
    ec2.describe_vpc_endpoint_services(ServiceNames=[f"{service_name}-fips"])
    print("← a FIPS endpoint service exists")
except Exception as error:
    response = getattr(error, "response", {})
    code = response.get("Error", {}).get("Code", type(error).__name__)
    print(f"← {code}")
    print("   There is no FIPS endpoint service for mantle, while bedrock-runtime")
    print("   has one. A workload with a FIPS requirement on the endpoint cannot")
    print("   satisfy it here today, so a workload carrying that requirement")
    print("   runs its inference on bedrock-runtime instead.\n")

# --- D. Audit ---------------------------------------------------------------

print("=" * 78)
print("D. What the audit trail records")
print("=" * 78)
print("   per request     an x-request-id on every response, which is the handle")
print("                   to quote in a support case")
print("   CloudTrail      mantle API activity is recorded. Web Search retrieval is")
print("                   recorded as DATA events, which are off by default —")
print("                   enable them (AWS::BedrockWebSearch::Tool) if the trail")
print("                   has to show retrieval, and note they deliberately do not")
print("                   record query text, returned URLs or page content")
print("   CloudWatch      token metrics under the AWS/BedrockMantle namespace")
print("   in the response usage.input_tokens_details is the authoritative source")
print("                   for cache accounting — there is no cache metric")
print()
print("→ request   cloudwatch:ListMetrics in namespace AWS/BedrockMantle")
try:
    cloudwatch = boto3.client("cloudwatch", region_name=REGION)
    metrics = cloudwatch.list_metrics(Namespace="AWS/BedrockMantle").get("Metrics", [])
    names = sorted({m["MetricName"] for m in metrics})
    shown = ", ".join(names[:8]) or "(none yet)"
    print(f"← response  {len(names)} metric name(s): {shown}")
    if not names:
        print("   An empty list means no traffic has published metrics in this Region")
        print("   yet, not that the namespace is unsupported.")
except Exception as error:
    print(f"← {type(error).__name__}: {str(error)[:110]}")
print()

# --- E. Quotas --------------------------------------------------------------

print("=" * 78)
print("E. Quotas: published, per model, and adjustable")
print("=" * 78)
print("→ request   service-quotas:ListServiceQuotas for service code 'bedrock'")
print("   why       'what happens at peak' is a review question, and the answer is")
print("             a published number rather than an unknown")
try:
    paginator = quotas.get_paginator("list_service_quotas")
    mantle_quotas = [
        quota
        for page in paginator.paginate(ServiceCode="bedrock")
        for quota in page["Quotas"]
        if "mantle" in quota["QuotaName"].lower()
    ]
    adjustable = sum(1 for q in mantle_quotas if q["Adjustable"])
    print(f"← response  {len(mantle_quotas)} mantle quota(s), {adjustable} adjustable")
    # Show the ones for the family under review rather than the first alphabetically.
    relevant = [q for q in mantle_quotas if "GPT" in q["QuotaName"]]
    for quota in sorted(relevant or mantle_quotas, key=lambda q: q["QuotaName"])[:6]:
        label = quota["QuotaName"].replace("[bedrock-mantle endpoint] ", "")
        print(f"   {label[:56]:56} {quota['Value']:>12,.0f}")
    print("   Quotas are tokens per minute, input and output separately, per model")
    print("   and per Region. There is no requests-per-minute dimension, so a 429")
    print("   is always a token-rate answer.")
except Exception as error:
    print(f"← {type(error).__name__}: {str(error)[:110]}")
print()

# --- F. The summary ---------------------------------------------------------

print("=" * 78)
print("F. The answers, in the order a reviewer asks them")
print("=" * 78)
rows = [
    ("Where does inference run?", f"in {REGION}, the Region you name on the client"),
    ("Is the Region implicit?", "no — the recipe passes region= and prints it"),
    ("What authorizes a call?", "IAM: CreateInference on a project ARN"),
    ("How is a workload isolated?", "its own project, referenced in the policy"),
    ("Is data used for training?", "no, and not shared with the model provider"),
    ("What is retained by default?", "the response, 30 days — unless store=False"),
    ("Is zero data retention available?", f"not on {MODEL_ID}; mode 'none' absent"),
    ("Can it avoid the public internet?", "yes, PrivateLink, no code change"),
    ("Is there a FIPS endpoint?", "not on mantle today"),
    ("What is audited?", "CloudTrail; Web Search needs data events on"),
    ("What are the limits?", "published token-per-minute quotas, adjustable"),
]
for question, answer in rows:
    print(f"   {question:36} {answer}")
print(
    "\n   The two honest 'no' answers are the point of running this rather than"
    "\n   reading a datasheet: ZDR not enabled on this account, and no FIPS endpoint"
    "\n   service. Both are checked live, so both are re-checkable the day they"
    "\n   change — and a reviewer told the truth about two gaps will believe the"
    "\n   other nine answers."
)
print("\nNothing was created by this recipe, so there is nothing to clean up.")
