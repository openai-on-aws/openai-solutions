

# Responses API
<a name="inference-responses-api"></a>

Amazon Bedrock provides the OpenAI Responses API on both the `bedrock-runtime` and `bedrock-mantle` endpoints. Use `bedrock-runtime` for new applications. Use `bedrock-mantle` only when a model or capability that you require isn't available on `bedrock-runtime`.


| **Endpoint** | **Base URL** | **When to use** | 
| --- | --- | --- | 
| bedrock-runtime (recommended) | https://bedrock-runtime.{region}.amazonaws.com/openai/v1 | New applications and migrations when the required model and Responses API features are supported. | 
| bedrock-mantle (compatibility) | https://bedrock-mantle.{region}.api.aws/v1 | Existing applications and workloads that require Mantle-only support, such as Responses API access to GPT OSS models, background inference, or server-side tools. | 

**Note**  
On `bedrock-mantle`, the path prefix varies by model. Most models are served under `/v1`, as shown in the preceding table, but some are served under `/openai/v1` instead. A request that uses the wrong prefix for a model is rejected with `model `<model-id>` isn't supported on this route`. To confirm the base URL for a specific model, see the **Programmatic Access** table on its card in [Models at a glance](model-cards.md).

The two endpoints don't have identical feature support. Requests on `bedrock-runtime` are always synchronous, server-side tools aren't available, and only the default project is supported. For the full comparison, see [Inference endpoints supported by Amazon Bedrock](endpoints.md), and for the details of each difference, see [Using the Responses API on the bedrock-runtime endpoint](#bedrock-mantle-responses-runtime).

**Important**  
When using the OpenAI SDK with Amazon Bedrock, you must point it to the Amazon Bedrock endpoint, not the OpenAI endpoint. Set the following environment variables, choosing the base URL for the endpoint you want:  

```
# bedrock-runtime (recommended)
OPENAI_BASE_URL="https://bedrock-runtime.<your-region>.amazonaws.com/openai/v1"

# bedrock-mantle
OPENAI_BASE_URL="https://bedrock-mantle.<your-region>.api.aws/v1"

OPENAI_API_KEY="<your Bedrock API key>"
```
Do not use your OpenAI API key or the OpenAI base URL (`https://api.openai.com/v1`). Those connect to OpenAI directly, not to Amazon Bedrock. To create a Amazon Bedrock API key, see [API keys](api-keys.md).

Key benefits include:
+ **Asynchronous inference** – Support for long-running inference workloads through the Responses API. Available on `bedrock-mantle` only.
+ **Stateful conversation management** – Automatically rebuild context without manually passing conversation history with each request
+ **Simplified tool use** – Streamlined integration for agentic workflows
+ **Flexible response modes** – Support for both streaming and non-streaming responses
+ **Easy migration** – Compatible with existing OpenAI SDK codebases

Each endpoint is governed by its own set of quotas. For Responses traffic on `bedrock-runtime`, the model's tokens-per-minute and tokens-per-day quotas apply, and they're shared with the other inference APIs on that endpoint — see [Quotas for the bedrock-runtime endpoint](quotas-runtime.md). For `bedrock-mantle`, see [Quotas for the bedrock-mantle endpoint](quotas-mantle.md).

## Supported Regions and Endpoints
<a name="bedrock-mantle-supported"></a>

On the `bedrock-runtime` endpoint, the Responses API is available in every AWS Region where that endpoint is available, including the AWS GovCloud (US) Regions. For the list, see [Regional availability by endpoints](endpoints-region-availability.md). Which models support the API on each endpoint is listed in [Endpoint availability](models-endpoint-availability.md).

The `bedrock-mantle` endpoint is available in a subset of those AWS Regions. For the Regions that support each endpoint, see [Regional availability by endpoints](endpoints-region-availability.md). For the base URL to use with a Region, see [Inference endpoints supported by Amazon Bedrock](endpoints.md).

## Prerequisites
<a name="bedrock-mantle-prereq"></a>

Before using OpenAI APIs, make sure you have the following:
+ **Authentication** – You can authenticate using:
  + Amazon Bedrock API key (required for OpenAI SDK)
  + AWS credentials (supported for HTTP requests)
+ **OpenAI SDK** (optional) – Install the OpenAI Python SDK if using SDK-based requests.
+ **Environment variables** – Set the following environment variables:
  + `OPENAI_API_KEY` – Set to your Amazon Bedrock API key
  + `OPENAI_BASE_URL` – Set to the Amazon Bedrock endpoint for your region (for example, `https://bedrock-runtime.us-east-1.amazonaws.com/openai/v1` or `https://bedrock-mantle.us-east-1.api.aws/v1`)
+ **Permissions** – The actions you need depend on the endpoint. On `bedrock-mantle`, inference authorizes `bedrock-mantle:CreateInference`. On `bedrock-runtime`, it authorizes `bedrock:InvokeModel` on both the inference target and your account's default project, and managing stored responses authorizes `bedrock:GetInvoke`, `bedrock:CancelInvoke`, and `bedrock:DeleteInvoke` on that project. For policy examples, see [Prerequisites for running model inference](inference-prereq.md).

## Choose a model
<a name="bedrock-mantle-models"></a>

Model and API support differs between endpoints. For `bedrock-runtime`, choose a model whose model card lists the Responses API as supported on that endpoint. Requests for the closed-weight OpenAI GPT models must name a system-defined inference profile, such as `us.openai.gpt-5.6-sol` or `global.openai.gpt-5.6-sol`, rather than the foundation model ID.

**Important**  
`bedrock-runtime` doesn't implement the OpenAI-compatible `GET /models` operation, so `client.models.list()` and `GET /openai/v1/models` don't work on that endpoint. Use the Amazon Bedrock control-plane [ListFoundationModels](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_ListFoundationModels.html) and [ListInferenceProfiles](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_ListInferenceProfiles.html) operations, and see the model cards in [Models at a glance](model-cards.md) for endpoint-specific API support and inference profile IDs. For examples, see [Get list of models](models-get-info.md).

**Note**  
GPT OSS models support Chat Completions, Converse, and Invoke on `bedrock-runtime`, but they don't support the Responses API there. To use both Responses and Chat Completions entirely on `bedrock-runtime`, choose a model that lists both APIs as supported on that endpoint. To use the Responses API with GPT OSS, use `bedrock-mantle`.

### List models on bedrock-mantle
<a name="bedrock-mantle-models-list"></a>

The OpenAI-compatible Models API is available on `bedrock-mantle`. For complete API details, see the [OpenAI Models documentation](https://developers.openai.com/api/reference/resources/models). To list models on that endpoint, choose the tab for your preferred method, and then follow the steps:

------
#### [ OpenAI SDK (Python) ]

```
# List all available models using the OpenAI SDK
# Requires OPENAI_API_KEY and OPENAI_BASE_URL environment variables

from openai import OpenAI

client = OpenAI()

models = client.models.list()

for model in models.data:
    print(model.id)
```

------
#### [ HTTP request ]

Make a GET request to `/v1/models`:

```
# List all available models
# Requires OPENAI_API_KEY and OPENAI_BASE_URL environment variables

curl -X GET $OPENAI_BASE_URL/models \
   -H "Authorization: Bearer $OPENAI_API_KEY"
```

------

## Migrate from bedrock-mantle to bedrock-runtime
<a name="inference-responses-migrate-runtime"></a>

Before moving a Responses API workload, confirm that its model and required features are supported on `bedrock-runtime`. Then make the following changes:


| **Setting** | **bedrock-mantle** | **bedrock-runtime** | 
| --- | --- | --- | 
| Base URL | https://bedrock-mantle.{region}.api.aws/v1 | https://bedrock-runtime.{region}.amazonaws.com/openai/v1 | 
| Model value | Model ID, such as openai.gpt-5.6-sol | Runtime model or system inference profile ID, such as global.openai.gpt-5.6-sol | 
| Model discovery | GET /models or client.models.list() | ListFoundationModels, ListInferenceProfiles, and model cards | 
| Project | Default or customer-created project | Default project only | 

Test requests that use background processing, server-side tools, application inference profiles, or model inheritance through `previous_response_id`, because those behaviors differ on `bedrock-runtime`. For the complete list, see [Using the Responses API on the bedrock-runtime endpoint](#bedrock-mantle-responses-runtime).

## Responses API
<a name="bedrock-mantle-responses"></a>

The Responses API provides stateful conversation management with support for streaming and multi-turn interactions. The `bedrock-mantle` endpoint also supports background processing. For complete API details, see the [OpenAI Responses documentation](https://developers.openai.com/api/reference/resources/responses).

**Note**  
Not all models support the Responses API on both endpoints. Check the endpoint-specific API table on the model card before choosing a model. The compatibility table in [API compatibility](models-api-compatibility.md) summarizes model capabilities across endpoints, but doesn't imply that an API is available on every endpoint.

### How the Responses API stores conversation state
<a name="bedrock-mantle-responses-state"></a>

The Responses API can use stored state to enable multi-turn conversations and let you reference previous turns through the `previous_response_id` parameter. Storage is enabled by default but can be disabled per request through the `store` parameter. Stored responses are scoped by Project. A response from one Project cannot be used as the previous response or read in a second Project. For more information about Projects, see [Projects (OpenAI-compatible)](projects.md).
+ When `store` is `true` (the default), Amazon Bedrock retains the response, including the input and output, for 30 days. During this window you can chain follow-up requests by passing `previous_response_id` and retrieve the response with `GET /v1/responses/{id}` on `bedrock-mantle`, or `GET /openai/v1/responses/{id}` on `bedrock-runtime`. After 30 days, the response is automatically deleted and is no longer retrievable.
+ When `store` is `false`, Amazon Bedrock does not retain any data from the request or response. The `previous_response_id` parameter cannot be used to continue the conversation.

The default value is `true` to match the OpenAI Responses API specification. Customers who do not want Amazon Bedrock to retain conversation data should explicitly set `store` to `false` on every request, or set the account's data retention mode to `none`, which rejects an explicit `store=true` outright. For more information, see [Data retention](data-retention.md).

Stored data is encrypted at rest and scoped to the calling AWS account's Project resource. The data is stored solely to service your requests and is not used or retained for any other purpose. On `bedrock-mantle`, it is kept in the AWS Region the request was sent to. On `bedrock-runtime`, a request that uses [cross-Region inference](cross-region-inference.md) can be processed in another AWS Region, and the response is stored in the Region that processed it — so a request that uses a global inference profile can store data in any commercial Region that profile routes to. If you have data residency requirements, use a geographic inference profile rather than a global one.

### Basic request
<a name="bedrock-mantle-responses-create"></a>

To create a response, choose an example for your endpoint. The `bedrock-runtime` examples use a global system inference profile. Use a geographic profile instead if you have data residency requirements.

------
#### [ bedrock-runtime: OpenAI SDK (Python) ]

```
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="global.openai.gpt-5.6-sol",
    input="Can you explain the features of Amazon Bedrock?"
)
print(response)
```

------
#### [ bedrock-runtime: HTTP request ]

Make a POST request to `/openai/v1/responses`:

```
curl -X POST "$OPENAI_BASE_URL/responses" \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENAI_API_KEY" \
   -d '{
    "model": "global.openai.gpt-5.6-sol",
    "input": "Can you explain the features of Amazon Bedrock?"
}'
```

------
#### [ bedrock-mantle: OpenAI SDK (Python) ]

```
# Create a basic response using the OpenAI SDK
# Requires OPENAI_API_KEY and OPENAI_BASE_URL environment variables

from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="openai.gpt-oss-120b",
    input=[
        {"role": "user", "content": "Hello! How can you help me today?"}
    ]
)

print(response)
```

------
#### [ bedrock-mantle: HTTP request ]

Make a POST request to `/v1/responses`:

```
# Create a basic response
# Requires OPENAI_API_KEY and OPENAI_BASE_URL environment variables

curl -X POST $OPENAI_BASE_URL/responses \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENAI_API_KEY" \
   -d '{
    "model": "openai.gpt-oss-120b",
    "input": [
        {"role": "user", "content": "Hello! How can you help me today?"}
    ]
}'
```

------

### Stream responses
<a name="bedrock-mantle-responses-streaming"></a>

To receive response events incrementally, choose an example for your endpoint.

------
#### [ bedrock-runtime: OpenAI SDK (Python) ]

```
from openai import OpenAI

client = OpenAI()

stream = client.responses.create(
    model="global.openai.gpt-5.6-sol",
    input="Tell me a story",
    stream=True
)

for event in stream:
    print(event)
```

------
#### [ bedrock-runtime: HTTP request ]

Make a POST request to `/openai/v1/responses` with `stream` set to `true`:

```
curl -X POST "$OPENAI_BASE_URL/responses" \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENAI_API_KEY" \
   -d '{
    "model": "global.openai.gpt-5.6-sol",
    "input": "Tell me a story",
    "stream": true
}'
```

------
#### [ bedrock-mantle: OpenAI SDK (Python) ]

```
# Stream response events incrementally using the OpenAI SDK
# Requires OPENAI_API_KEY and OPENAI_BASE_URL environment variables

from openai import OpenAI

client = OpenAI()

stream = client.responses.create(
    model="openai.gpt-oss-120b",
    input=[{"role": "user", "content": "Tell me a story"}],
    stream=True
)

for event in stream:
    print(event)
```

------
#### [ bedrock-mantle: HTTP request ]

Make a POST request to `/v1/responses` with `stream` set to `true`:

```
# Stream response events incrementally
# Requires OPENAI_API_KEY and OPENAI_BASE_URL environment variables

curl -X POST $OPENAI_BASE_URL/responses \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $OPENAI_API_KEY" \
   -d '{
    "model": "openai.gpt-oss-120b",
    "input": [
        {"role": "user", "content": "Tell me a story"}
    ],
    "stream": true
}'
```

------

### Using the Responses API on the bedrock-runtime endpoint
<a name="bedrock-mantle-responses-runtime"></a>

The Responses API on `bedrock-runtime` uses the same request and response format as on `bedrock-mantle`, so the OpenAI SDK works against either one. What changes is the base URL, the model IDs, the permissions, and a small number of behaviors described in this section.

**Base URL and paths**

Set your base URL to `https://bedrock-runtime.{{region}}.amazonaws.com/openai/v1`. The API is served on the following paths:
+ `POST /openai/v1/responses` – create a response.
+ `GET /openai/v1/responses/{id}` – retrieve a stored response.
+ `POST /openai/v1/responses/{id}/cancel` – cancel a response that is still in progress.
+ `DELETE /openai/v1/responses/{id}` – delete a stored response.

**Model IDs**

Name a cross-Region inference profile as the model, not a foundation model ID. The OpenAI GPT models use the `us.` and `global.` profiles in the commercial Regions and the `us-gov.` profiles in the AWS GovCloud (US) Regions — for example, `us.openai.gpt-5.6-sol`. In-Region inference isn't available for these models on this endpoint. For the profile ID of each model, see its model card in [Models at a glance](model-cards.md), and for how routing works, see [Route model inference requests across AWS Regions with cross-Region inference](cross-region-inference.md).

**Permissions**

Creating a response authorizes two resources: `bedrock:InvokeModel` (or `bedrock:InvokeModelWithResponseStream`) on the inference target, as any inference request does, and `bedrock:InvokeModel` on your account's default project. Retrieving, canceling, and deleting a stored response authorize `bedrock:GetInvoke`, `bedrock:CancelInvoke`, and `bedrock:DeleteInvoke` respectively, each on the project. Individual response IDs are not IAM resources.

Two condition keys let a policy on either resource constrain the other. The inference-target authorization carries `bedrock:ProjectArn`, and the project authorization carries `bedrock:ModelArn`, valued at the inference profile or foundation model your request named — never the destination models that a cross-Region profile routes to. For policy examples, see [Prerequisites for running model inference](inference-prereq.md).

**Behavior differences**
+ **Requests are always synchronous.** `background=true` is rejected with a 400 error. The `store` parameter is unaffected and keeps its default of `true`, so stored, multi-turn conversations work normally.
+ **`model` is required on every request**, including one that supplies `previous_response_id`. This differs from the OpenAI Responses API specification and from `bedrock-mantle`, where the model can be omitted and inherited from the previous response. The model is part of what the request is authorized against, so it has to be named in the request itself.
+ **Server-side tool use and pre-configured tools aren't available**, including [web search](web-search.md). Client-side tool use works on both endpoints.
+ **Only the default project is supported.** The `OpenAI-Project` header is accepted only as `default` or as your own default project ARN; any other value is rejected. See [Projects (OpenAI-compatible)](projects.md).
+ **Application inference profiles aren't supported.** A request that names one as its inference target is rejected with a 400 error. System, geographic, and global inference profiles work normally.
+ **[Guardrails](guardrails.md) are supported.** Set the `X-Amzn-Bedrock-GuardrailIdentifier` and `X-Amzn-Bedrock-GuardrailVersion` request headers. With the OpenAI SDK, pass these values through `extra_headers`. For more information, see [Test your guardrail](guardrails-test.md).
+ **A stored response belongs to the AWS Region that served it.** Retrieving, canceling, or deleting it, and continuing the conversation with `previous_response_id`, are all handled by that Region. A response ID that can't be found — because it never existed, belongs to another account, or was never stored — returns the same 404 error in every case.

**Monitoring and cost**

Because every request is synchronous, CloudWatch metrics and model invocation logging work for the Responses API the same way they do for the other inference APIs on this endpoint, including for streaming requests. Usage is attributed to the inference target, exactly as it is for Converse and InvokeModel — the default project is never the billing anchor. See [Track usage and costs in Amazon Bedrock](cost-management.md).