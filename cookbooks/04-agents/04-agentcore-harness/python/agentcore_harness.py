"""Deploy the agent instead of running it: AgentCore Harness on the Responses API.

The previous recipe wrote the agent loop by hand — call, read tool calls, execute, send
results, repeat, with a ceiling. A **harness** is that loop as managed infrastructure.
You declare the model, the system prompt, the tools and the limits; AgentCore runs the
loop, keeps the session, and streams the result.

  A. the role      what the execution role needs, and why memory is in there
  B. create        one create_harness call, with apiFormat 'responses'
  C. invoke        a session, a message, and a stream of events
  D. what you get  session state and iteration limits you did not build
  E. clean up      the harness and the role are deleted

The parameter that matters for this cookbook is `apiFormat: "responses"`, which is what
routes a harness at a GPT-5.6 model through the OpenAI-compatible surface on
`bedrock-mantle`. See README.md.
"""

import json
import os
import time
import uuid

import boto3
from botocore.exceptions import ClientError

from cookbook_utils import mask_account_ids

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

# Set HARNESS_ARN to invoke an existing harness and skip creation. Creating one needs
# iam:CreateRole and bedrock-agentcore:CreateHarness, which a restricted role will not
# have.
HARNESS_ARN = os.environ.get("HARNESS_ARN")

# A unique suffix per run, because a harness name stays reserved for a while after
# deletion and two people running this in one account should not collide.
HARNESS_NAME = f"cookbook_harness_{uuid.uuid4().hex[:8]}"
ROLE_NAME = "cookbook-disruption-harness-role"

SYSTEM_PROMPT = (
    "You are a disruption manager for an airline. Answer concisely and practically. "
    "When a passenger's requirements cannot be met from what you know, say so plainly "
    "rather than guessing."
)

control = boto3.client("bedrock-agentcore-control", region_name=REGION)
runtime = boto3.client("bedrock-agentcore", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)
ACCOUNT = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]



print(f"AgentCore Harness  ·  {MODEL_ID} in {REGION}")
print("the loop is managed; this file declares the agent and invokes it\n")

# --- A. The execution role --------------------------------------------------

print("=" * 78)
print("A. The execution role")
print("=" * 78)
print("   A harness runs as its own identity, so the role needs two things:")
print("     inference        the AmazonBedrockMantleInferenceAccess managed policy")
print("     session memory   bedrock-agentcore memory actions, as an inline policy")
print()
print("   Both halves are easy to get wrong, in opposite directions. Inference is")
print("   authorized on a PROJECT arn and also needs CallWithBearerToken and")
print("   Marketplace permissions, so a hand-written CreateInference statement on")
print("   '*' is not enough — attach the managed policy. And a harness provisions a")
print("   managed memory for session state which it then reads as this role, so a")
print("   role with inference alone creates fine and fails at invoke time.")

if HARNESS_ARN is None:
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }
    # Inference comes from the managed policy rather than a hand-written statement:
    # CreateInference is authorized on a PROJECT arn and the call also needs
    # CallWithBearerToken and Marketplace permissions, which the managed policy
    # carries. Writing those four statements by hand is how you end up with a 401.
    INFERENCE_POLICY = ("arn:aws:iam::aws:policy/"
                        "AmazonBedrockMantleInferenceAccess")
    permissions = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "SessionMemory",
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:CreateEvent",
                           "bedrock-agentcore:ListEvents",
                           "bedrock-agentcore:GetEvent",
                           "bedrock-agentcore:ListActors",
                           "bedrock-agentcore:ListSessions",
                           "bedrock-agentcore:RetrieveMemoryRecords",
                           "bedrock-agentcore:GetMemory",
                           "bedrock-agentcore:GetMemoryRecord",
                           "bedrock-agentcore:ListMemoryRecords"],
                "Resource": f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:memory/*",
            },
        ],
    }
    try:
        role = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Cookbook AgentCore harness. Deleted by the recipe.",
        )["Role"]
    except ClientError as conflict:
        if conflict.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        role = iam.get_role(RoleName=ROLE_NAME)["Role"]
    iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=INFERENCE_POLICY)
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="harness-session-memory",
        PolicyDocument=json.dumps(permissions),
    )
    # IAM is eventually consistent; a freshly attached policy is not always usable yet.
    time.sleep(12)
    print(f"\n   role ready: {mask_account_ids(role['Arn'])}\n")

# --- B. Create the harness --------------------------------------------------

print("=" * 78)
print("B. The agent as a declaration")
print("=" * 78)

harness_id = None
if HARNESS_ARN is None:
    print("→ request   bedrock-agentcore:CreateHarness")
    print(f"   model.bedrockModelConfig.modelId     {MODEL_ID}")
    print("   model.bedrockModelConfig.apiFormat   'responses'   ← routes the harness")
    print("                                        through the OpenAI-compatible")
    print("                                        surface on bedrock-mantle")
    print("   systemPrompt                         the disruption-manager brief")
    print("   maxIterations                        4     the ceiling you would have")
    print("                                              written by hand")
    print("   timeoutSeconds                       120")

    created = control.create_harness(
        harnessName=HARNESS_NAME,
        executionRoleArn=role["Arn"],
        model={"bedrockModelConfig": {
            "modelId": MODEL_ID,
            "apiFormat": "responses",
            "maxTokens": 800,
        }},
        systemPrompt=[{"text": SYSTEM_PROMPT}],
        maxIterations=4,
        timeoutSeconds=120,
    )["harness"]
    harness_id = created["harnessId"]

    for _ in range(60):
        harness = control.get_harness(harnessId=harness_id)["harness"]
        if harness.get("status") != "CREATING":
            break
        time.sleep(5)

    HARNESS_ARN = harness["arn"]
    print("← response")
    print(f"   status          {harness.get('status')}")
    print(f"   version         {harness.get('harnessVersion')}")
    print(f"   arn             {mask_account_ids(HARNESS_ARN)}")
    print(f"   allowedTools    {harness.get('allowedTools')}")
    print(f"   truncation      {harness.get('truncation', {}).get('strategy')}")
    print("   Note the last two: the service filled in a tool allow-list and a")
    print("   conversation truncation strategy that you did not have to write.")
    memory = harness.get("memory", {})
    if memory:
        print("   memory          provisioned for you — this is what the role's")
        print("                   SessionMemory statement is for\n")
else:
    print(f"   invoking the harness in HARNESS_ARN: {mask_account_ids(HARNESS_ARN)}\n")

# --- C. Invoke it -----------------------------------------------------------

print("=" * 78)
print("C. Invoke it")
print("=" * 78)
session_id = str(uuid.uuid4())
question = ("Flight AE414 Lisbon to Dublin is cancelled. A passenger has a hospital "
            "appointment in Dublin at 18:00 the same day. What do you need to know "
            "to rebook them, and what would you check first?")
print("→ request   bedrock-agentcore:InvokeHarness")
print(f"   runtimeSessionId  {session_id[:8]}…   the session the harness keeps for you")
print("   messages          [{role: user, content: [{text: …}]}]")
print(f"   input             {question[:60]}…")
print("   note              no tools, no loop, no retry logic in this file\n")

answer_parts: list[str] = []
event_counts: dict[str, int] = {}
try:
    response = runtime.invoke_harness(
        harnessArn=HARNESS_ARN,
        runtimeSessionId=session_id,
        messages=[{"role": "user", "content": [{"text": question}]}],
    )
    for event in response["stream"]:
        for name, payload in event.items():
            event_counts[name] = event_counts.get(name, 0) + 1
            text = None
            if isinstance(payload, dict):
                delta = payload.get("delta") or {}
                text = delta.get("text") or payload.get("text")
            if text:
                answer_parts.append(text)
    print("← response  (streamed)")
    print(f"   event types: {event_counts}")
    if answer_parts:
        answer = "".join(answer_parts).strip()
        for line in answer.splitlines()[:12]:
            if line.strip():
                print(f"   {line.strip()[:88]}")
except Exception as failure:
    print(f"← {type(failure).__name__}: {mask_account_ids(str(failure))[:600]}")

# --- D. What the harness gave you ------------------------------------------

print("\n" + "=" * 78)
print("D. What you did not write")
print("=" * 78)
print(
    "   the loop            iterate until the model stops asking, up to maxIterations\n"
    "   the session         runtimeSessionId, backed by a managed memory\n"
    "   truncation          a sliding window over the conversation as it grows\n"
    "   streaming           an event stream rather than a blocking call\n"
    "   the tool contract   agentcore_gateway, remote_mcp, code interpreter and\n"
    "                       browser are declared the same way the model is\n"
    "\n"
    "   What you keep deciding: the model and its API format, the system prompt, the\n"
    "   iteration ceiling, the timeout, and which tools the agent may use."
)

# --- E. Clean up ------------------------------------------------------------

print("\n" + "=" * 78)
print("E. Clean up")
print("=" * 78)
if harness_id is not None:
    control.delete_harness(harnessId=harness_id)
    print(f"   deleted harness {HARNESS_NAME}")
    # The role carries a cookbook-specific name, so the recipe owns it either way —
    # a role left behind by an interrupted earlier run should go too.
    iam.delete_role_policy(RoleName=ROLE_NAME, PolicyName="harness-session-memory")
    iam.detach_role_policy(RoleName=ROLE_NAME, PolicyArn=INFERENCE_POLICY)
    iam.delete_role(RoleName=ROLE_NAME)
    print(f"   deleted role    {ROLE_NAME}")
    print("   the managed memory the harness provisioned goes with it")
else:
    print("   the harness was supplied, so nothing is deleted")
print("\nAgentCore and model tokens are billed separately:")
print("https://aws.amazon.com/bedrock/pricing/")
