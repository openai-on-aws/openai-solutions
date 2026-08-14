"""Let Bedrock run the tool: an MCP connector instead of a client-side loop.

In the client-side pattern you receive a `function_call`, execute it, and send the
result back — one round trip per tool call, and your process has to stay alive. Here you
declare an **MCP connector** instead, and Bedrock does the whole loop server-side: it
discovers the tools, decides which to call, invokes them, reads the results and answers.

  A. the tool server   a Lambda speaking JSON-RPC: tools/list and tools/call
  B. deploy            role and function created here, deleted in step E
  C. one request        no loop, no function_call handling, one call
  D. observability      mcp_list_tools and mcp_call items keep the steps visible
  E. clean up           the function and its role are removed

The architectural reason to care: the Lambda can sit in a VPC and reach a private system
that Bedrock cannot reach, without granting Bedrock network access. See README.md.
"""

import io
import json
import os
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from openai import OpenAI
from openai.providers import bedrock

from cookbook_utils import mask_account_ids

# --- Change these -----------------------------------------------------------

REGION = os.environ.get("AWS_REGION", "us-east-1")

# openai.gpt-5.6-luna    openai.gpt-5.6-terra    openai.gpt-5.6-sol
MODEL_ID = os.environ.get("MODEL_ID", "openai.gpt-5.6-terra")

# Point this at an existing MCP connector — a Lambda ARN or an AgentCore Gateway ARN —
# to skip deployment. Creating a function and a role needs iam:CreateRole and
# lambda:CreateFunction, which a restricted role will not have.
CONNECTOR_ARN = os.environ.get("MCP_CONNECTOR_ARN")

FUNCTION_NAME = "cookbook-mcp-inventory-tools"
ROLE_NAME = "cookbook-mcp-inventory-tools-role"

HERE = Path(__file__).resolve().parent

client = OpenAI(provider=bedrock(region=REGION), max_retries=3)
iam = boto3.client("iam", region_name=REGION)
awslambda = boto3.client("lambda", region_name=REGION)



print(f"Server-side tools  ·  {MODEL_ID} in {REGION}")
print("Bedrock runs the tool loop; this process makes exactly one model call\n")

# --- A. The tool server -----------------------------------------------------

print("=" * 78)
print("A. The tool server")
print("=" * 78)
print("   python/mcp_tool_lambda.py implements three JSON-RPC methods:")
print("     initialize   announce the protocol version")
print("     tools/list   how Bedrock discovers what is callable")
print("     tools/call   run one tool and return MCP content parts")
print("   It exposes search_rooms and get_room over a room-inventory dict.")
print("   No credentials are passed to it: Bedrock reuses the identity of whoever")
print("   invoked the model, which is why the function's role has to match the")
print("   caller's permissions rather than carrying its own.\n")

# --- B. Deploy --------------------------------------------------------------

print("=" * 78)
print("B. Deploy the connector")
print("=" * 78)

created_here = CONNECTOR_ARN is None
if created_here:
    print("→ request   iam:CreateRole + lambda:CreateFunction")
    print(f"   function  {FUNCTION_NAME}")
    print("   runtime   python3.12, handler mcp_tool_lambda.lambda_handler")
    print("   note      no function URL and no public access — Bedrock invokes it")
    print("             through the connector, not over the internet")

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": ["lambda.amazonaws.com",
                                      "bedrock.amazonaws.com"]},
            "Action": "sts:AssumeRole",
        }],
    }
    try:
        role = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Cookbook MCP tool function. Deleted by the recipe.",
        )["Role"]
    except ClientError as already_exists:
        if already_exists.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        role = iam.get_role(RoleName=ROLE_NAME)["Role"]
    iam.attach_role_policy(
        RoleName=ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )
    # IAM is eventually consistent: a role attached a moment ago is not always
    # assumable yet, and Lambda reports that as an InvalidParameterValueException.
    time.sleep(12)

    package = io.BytesIO()
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mcp_tool_lambda.py",
                         (HERE / "mcp_tool_lambda.py").read_text())

    try:
        function = awslambda.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.12",
            Role=role["Arn"],
            Handler="mcp_tool_lambda.lambda_handler",
            Code={"ZipFile": package.getvalue()},
            Timeout=30,
            MemorySize=256,
            Description="Cookbook MCP tool server. Deleted by the recipe.",
        )
    except ClientError as already_exists:
        if already_exists.response["Error"]["Code"] != "ResourceConflictException":
            raise
        function = awslambda.get_function(FunctionName=FUNCTION_NAME)["Configuration"]
    CONNECTOR_ARN = function["FunctionArn"]

    awslambda.get_waiter("function_active_v2").wait(FunctionName=FUNCTION_NAME)
    print("← response")
    print(f"   function arn  {mask_account_ids(CONNECTOR_ARN)}")
    print("   state         Active\n")
else:
    shown = mask_account_ids(CONNECTOR_ARN)
    print(f"   using the connector in MCP_CONNECTOR_ARN: {shown}\n")

# --- C. One request ---------------------------------------------------------

MCP_TOOL = {
    "type": "mcp",
    "server_label": "marisol_inventory",
    "connector_id": CONNECTOR_ARN,
    "server_description": "Room inventory for Marisol Hotels",
    "require_approval": "never",   # the only accepted value
}

question = ("A guest needs an accessible room in Lisbon tonight, and a fallback in "
            "Porto if there is nothing suitable. What are the options and rates?")

print("=" * 78)
print("C. One request, and Bedrock runs the loop")
print("=" * 78)
print("→ request")
print(f"   model             {MODEL_ID}")
print("   tools             [{type: mcp, server_label, connector_id,")
print("                       require_approval: 'never'}]")
print("   require_approval  'never' is the only accepted value")
print(f"   input             {question[:62]}…")
print("   what is absent    any function_call handling. There is no loop in this")
print("                     file: one create() call returns the finished answer.")

try:
    response = client.responses.create(
        model=MODEL_ID,
        instructions=(
            "You help a hotel group's reservations desk. Use the inventory tools to "
            "check what is available before answering, and quote rates exactly "
            "as returned. If nothing suitable is free, say so."
        ),
        input=question,
        tools=[MCP_TOOL],
        max_output_tokens=1200,
        store=False,
    )
except Exception as failure:
    print(f"← {type(failure).__name__}: {mask_account_ids(str(failure))[:200]}")
    response = None

# --- D. Observability -------------------------------------------------------

if response is not None:
    print("← response")
    item_types = [item.type for item in response.output]
    print(f"   output item types: {item_types}")

    for item in response.output:
        if item.type == "mcp_list_tools":
            names = [tool.get("name") if isinstance(tool, dict) else tool.name
                     for tool in (item.tools or [])]
            print(f"   mcp_list_tools   discovered: {names}")
        elif item.type == "mcp_call":
            arguments = getattr(item, "arguments", "")
            print(f"   mcp_call         {getattr(item, 'name', '?')}({arguments})")
            output = getattr(item, "output", None)
            if output:
                print(f"                    → {str(output)[:88]}")
            if getattr(item, "error", None):
                print(f"                    error: {item.error}")

    print("\n   the answer:")
    for line in response.output_text.strip().splitlines():
        if line.strip():
            print(f"     {line.strip()[:90]}")
    usage = response.usage
    print(f"\n   {usage.input_tokens} in / {usage.output_tokens} out")
    print("   Tool definitions and tool results are billed as tokens; there is no")
    print("   per-call fee on top. The definitions enter context on every request")
    print("   that carries the connector, exactly as a client-side tool does.\n")

# --- E. Clean up ------------------------------------------------------------

print("=" * 78)
print("E. Clean up")
print("=" * 78)
if created_here:
    awslambda.delete_function(FunctionName=FUNCTION_NAME)
    iam.detach_role_policy(
        RoleName=ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )
    iam.delete_role(RoleName=ROLE_NAME)
    print(f"   deleted function {FUNCTION_NAME}")
    print(f"   deleted role     {ROLE_NAME}")
    print("   CloudWatch log group /aws/lambda/" + FUNCTION_NAME + " survives and")
    print("   retains logs — delete it too if you want nothing left behind")
else:
    print("   the connector was supplied, so nothing is deleted")
print("\nLambda invocations and tokens are both billed:")
print("https://aws.amazon.com/bedrock/pricing/")
