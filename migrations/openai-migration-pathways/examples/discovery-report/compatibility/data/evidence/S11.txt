

# Web Search
<a name="web-search"></a>

Web Search is a built-in tool that provides web search capability in Amazon Bedrock. When you enable it, supported models can retrieve current information from the web during a request and use it to ground their answers, instead of relying only on the data they were trained on. Responses include citations to the sources the model used. Web Search is hosted and built by AWS. Retrieval from the external web occurs only when both your request and your IAM permissions allow it.

## Data governance
<a name="web-search-data-governance"></a>

To keep retrieval within the AWS boundary while still allowing cached page content, set `external_web_access` to `false`. Search is then served from the Amazon Bedrock web index and Fetch is served from the Amazon Bedrock cache.

The [AmazonBedrockFullAccess](security-iam-awsmanpol.md#security-iam-awsmanpol-AmazonBedrockFullAccess) policy grants Search and Fetch but not `bedrock-websearch:ExternalWebAccess`. Because `external_web_access` defaults to `true`, omitting the parameter with this policy causes each Fetch attempt to fail its backend authorization check before the cache is read. The overall Responses API request can still complete using Search observations, but Fetch contributes no page content. Explicitly setting the parameter to `false` avoids this failure and keeps retrieval within the AWS boundary. Depending on the model you are using, your data is subject to the automated [Amazon Bedrock abuse detection](abuse-detection.md) mechanisms.

## When to use Web Search
<a name="web-search-when-to-use"></a>

Web Search is useful whenever an answer depends on information that is more recent, more specialized, or more authoritative than a model's parametric knowledge. Recency is one common case: current events, recent product releases, prices, or documentation for a new library version. It is equally useful for long-tail or specialized questions where the model's knowledge is thin or imprecise, such as niche APIs, specific configuration values, or domain-specific facts, and for cases where you want a grounded, citable source rather than a recollection.

## How Web Search works
<a name="web-search-how-it-works"></a>

Because the tool runs inside Amazon Bedrock, you do not need to host a search index, manage crawlers, or write the tool-call loop yourself. You add the tool to your Amazon Bedrock inference request, and the model invokes it as needed. Web Search provides current information to the model, enabling the model to return grounded answers with citations.

When Web Search is enabled, the model decides whether a request needs current information. If it does, the model issues one or more search queries to the Web Search tool and receives a set of observations drawn from a web index built and maintained by Amazon. Each observation includes a title, a source URL, and a content snippet. The model then composes an answer grounded in those results and adds citations that point back to the sources.

If the first set of results is not enough to answer the question, the model can reformulate its query using what it found and search again within the same turn. When the results do not support an answer, the model tells you so rather than filling the gap from its training data.

### Search and Fetch operations
<a name="web-search-search-fetch"></a>

Web Search is built from two operations:
+ **Search** – Returns titles, URLs, and snippets from the Amazon Bedrock web index and knowledge graph for high-confidence facts.
+ **Fetch** – Retrieves page content for a specific URL. With `external_web_access` set to `false`, Fetch uses the Amazon Bedrock cache only. With the parameter set to `true` and the required IAM permission granted, Fetch checks the cache first and accesses the external web only on a cache miss.

Search is always served from the Amazon Bedrock web index. The `external_web_access` parameter in the Responses API and the `bedrock-websearch:ExternalWebAccess` IAM permission govern whether Fetch can use the external web after a cache miss. For details, see [Controlling external web access](#web-search-controlling-external).

### Supported models
<a name="web-search-supported-models"></a>

Amazon Bedrock supports Web Search for OpenAI GPT-5.4 and later models in the commercial US Regions, served through the `bedrock-mantle` endpoint using the Responses API. In AWS GovCloud (US), it is supported on `openai.gpt-5.6-terra`, `openai.gpt-5.6-luna`, and `openai.gpt-5.4`. Examples in this guide use `openai.gpt-5.6-terra`. For Web Search pricing, refer to the [Amazon Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/).

**Note**  
Web Search is a server-side tool, so it isn't available when you call the Responses API on the `bedrock-runtime` endpoint. To use it, call the Responses API on `bedrock-mantle`. For the other differences between the two endpoints, see [Using the Responses API on the bedrock-runtime endpoint](inference-responses-api.md#bedrock-mantle-responses-runtime).

### Regional availability
<a name="web-search-regional-availability"></a>

Web Search processes queries in-Region. See current availability below.

#### United States
<a name="web-search-regional-availability-us"></a>


| **Region** | **Region code** | 
| --- | --- | 
| US East (N. Virginia) | us-east-1 | 
| US East (Ohio) | us-east-2 | 
| US West (Oregon) | us-west-2 | 

#### AWS GovCloud (US)
<a name="web-search-regional-availability-govcloud"></a>


| **Region** | **Region code** | 
| --- | --- | 
| AWS GovCloud (US-West) | us-gov-west-1 | 

Web Search is strictly regional. Each Region operates its own search and fetch tier, and queries, fetches, index data, and results are not routed across Regions. A query issued in a given Region stays within that Region's boundary.

## Enable Web Search
<a name="enable-web-search"></a>

To use Web Search, the IAM identity behind your request must be allowed to call the Web Search actions. For the required permissions and example policies, see [Identity and access management for Web Search](security-web-search.md).

### Set your environment
<a name="web-search-set-environment"></a>

Set the following before running the examples:

```
export OPENAI_API_KEY="your-amazon-bedrock-api-key"
export OPENAI_BASE_URL="https://bedrock-mantle.us-west-2.api.aws/openai/v1"
```

### Add the Web Search tool to a request
<a name="web-search-add-tool"></a>

To enable Web Search, add a tool of type `web_search` to the `tools` array in your request. The model uses the tool only when it determines the request needs current information. For runnable examples, see [Code examples](#web-search-code-examples).

### Control search context size
<a name="web-search-context-size"></a>

Use `search_context_size` to control how much context each Search call can return to the model. The supported values are:


| **Value** | **Observation budget** | **When to use** | 
| --- | --- | --- | 
| low | Up to 5 | Smaller context and lower input-token usage for straightforward questions. | 
| medium | Up to 11 | The default. Balances result coverage and input-token usage. | 
| high | Up to 25 | More context for complex or multi-hop questions, with higher potential input-token usage. | 

An observation contains a title, URL, and content snippet. The budget is shared when a Search call contains multiple queries, and the service can return fewer observations than the maximum. Larger settings can increase the model input tokens and associated inference cost. This parameter does not limit how many Search calls the model can make.

```
tools=[{
    "type": "web_search",
    "search_context_size": "low",
    "external_web_access": False,
}]
```

## Controlling external web access
<a name="web-search-controlling-external"></a>

Search is served from the Amazon Bedrock web index. Whether Fetch can retrieve page content from the external web after a cache miss is governed by two controls that work together: the `external_web_access` parameter in the Responses API and the `bedrock-websearch:ExternalWebAccess` IAM permission.

The `external_web_access` parameter defaults to `true`, matching the OpenAI Responses API so that your call does not have to change. The [AmazonBedrockFullAccess](security-iam-awsmanpol.md#security-iam-awsmanpol-AmazonBedrockFullAccess) policy grants the basic Web Search actions — `bedrock-websearch:InvokeSearch` and `bedrock-websearch:InvokeFetch` — but does not grant `bedrock-websearch:ExternalWebAccess`. As a result, a request that leaves `external_web_access` at `true` from an identity that does not hold `ExternalWebAccess` fails the backend authorization check for each Fetch attempt before the cache is read. The caller's Responses API request can still return HTTP `200`: the model can continue using Search observations and return `url_citation` annotations. The model response is not guaranteed to disclose the Fetch failure, and the presence of a citation does not mean the cited page was fetched. The denied `InvokeFetch` call is visible in CloudTrail when Web Search data event logging is enabled. For details, see [Monitor Web Search](monitoring-web-search.md).

Choose one of the following configurations for Fetch.

### Keep requests within the AWS boundary
<a name="web-search-boundary"></a>

Set `"external_web_access": false` on the tool. This does not require the `ExternalWebAccess` permission, retrieval is served entirely from the Amazon Bedrock web index and cache, and your request data does not leave the AWS boundary. Because [AmazonBedrockFullAccess](security-iam-awsmanpol.md#security-iam-awsmanpol-AmazonBedrockFullAccess) grants `InvokeFetch`, cached Fetch continues to work. Set the parameter explicitly; don't rely on omitting the permission while leaving the parameter at its default of `true`, because that configuration causes Fetch attempts to fail.

```
response = client.responses.create(
    model="openai.gpt-5.6-terra",
    input="Summarize recent guidance on AWS Lambda cold starts.",
    tools=[{"type": "web_search", "external_web_access": False}],
)
```

```
curl "https://bedrock-mantle.us-west-2.api.aws/openai/v1/responses" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai.gpt-5.6-terra",
    "input": "Summarize recent guidance on AWS Lambda cold starts.",
    "tools": [{"type": "web_search", "external_web_access": false}]
  }'
```

### Enable external web access
<a name="web-search-enable-external"></a>

Grant `bedrock-websearch:ExternalWebAccess` to the request identity and set `external_web_access` to `true`. The simplest managed-policy path is to attach either `AmazonBedrockExternalWebSearchReadOnly` or `AmazonBedrockExternalWebSearchFullAccess`. The current versions of these policies grant the same three Web Search actions on the same resources, so either policy enables external retrieval. For details, see [Managed policies](security-web-search.md#security-web-search-managed-policies).

With this configuration, Search continues to use the Amazon Bedrock web index. Fetch checks the Amazon Bedrock cache first and retrieves from the external web only when suitable page content is not in the cache. When Fetch reaches the external web, your request data may leave the AWS boundary. External retrieval takes effect only when you both grant the permission and leave the parameter enabled.

**Note**  
Note that setting `external_web_access` to `true` introduces data exfiltration risk. An agent could encode query data into a URL and then attempt to fetch that URL from the external internet. When you work with sensitive data, set `external_web_access` to `false` to prevent data reaching the external internet.

## Using Web Search with Codex
<a name="web-search-codex"></a>

Codex, OpenAI's coding agent, connects to Amazon Bedrock through the `bedrock-mantle` endpoint and can use Web Search on supported models. Web Search is available in the Codex desktop app and the CLI version 0.147.0 or later.

Using Web Search with Codex does not require additional IAM setup beyond the standard Web Search permissions. The IAM identity behind your API key must be allowed to call the Web Search actions `bedrock-websearch:InvokeSearch` and `bedrock-websearch:InvokeFetch`. These actions are granted by the [AmazonBedrockFullAccess](security-iam-awsmanpol.md#security-iam-awsmanpol-AmazonBedrockFullAccess) policy. For the required permissions and example policies, see [Identity and access management for Web Search](security-web-search.md).

On supported Amazon Bedrock models, Codex uses text-only Web Search, returning titles, URLs, and content snippets from the Amazon Bedrock web index and cache. Codex sets `external_web_access` to `false` on each request, so your request data stays within the AWS boundary. For details, see [Controlling external web access](#web-search-controlling-external).

## Code examples
<a name="web-search-code-examples"></a>

### Responses API
<a name="web-search-responses-api-example"></a>

```
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="openai.gpt-5.6-terra",
    input="What are the most significant AWS launches announced this month?",
    tools=[{"type": "web_search", "external_web_access": False}],
)

print(response.output_text)
```

The response includes the grounded answer text together with `url_citation` annotations that point back to the sources:

```
{
  "content": [
    {
      "annotations": [
        {
          "end_index": 573,
          "start_index": 441,
          "title": "Upgrade Amazon EKS clusters with confidence using Kubernetes version rollbacks | AWS News Blog",
          "type": "url_citation",
          "url": "https://aws.amazon.com/blogs/aws/upgrade-amazon-eks-clusters-with-confidence-using-kubernetes-version-rollbacks/"
        },
        {
          "end_index": 1094,
          "start_index": 888,
          "title": "AWS Weekly Roundup: AWS Builder Center at 1 year, Network Scanning in Security Hub, Loom for AWS, and more (July 13, 2026) | AWS News Blog",
          "type": "url_citation",
          "url": "https://aws.amazon.com/blogs/aws/aws-weekly-roundup-aws-builder-center-at-one-year-network-scanning-in-security-hub-loom-for-aws-and-more-july-13-2026/"
        },
        {
          "end_index": 1837,
          "start_index": 1414,
          "title": "AWS Weekly Roundup: One-click Lambda setup prompt, OpenAI GPT-5.6 models on Bedrock, and more (July 20, 2026) | AWS News Blog",
          "type": "url_citation",
          "url": "https://aws.amazon.com/blogs/aws/aws-weekly-roundup-one-click-lambda-setup-prompt-openai-gpt-5-6-models-on-bedrock-and-more-july-20-2026/"
        }
      ],
      "logprobs": [],
      "text": "As of **July 30, 2026**, the most significant AWS launches this month:\n\n1. **Amazon EKS Kubernetes version rollbacks** — EKS now lets admins roll back a Kubernetes version upgrade within **seven days**, effectively adding an “undo” path for cluster upgrades and reducing upgrade risk for large or regulated Kubernetes fleets. It’s available at no additional cost in commercial Regions where EKS is available. ([aws.amazon.com](https://aws.amazon.com/blogs/aws/upgrade-amazon-eks-clusters-with-confidence-using-kubernetes-version-rollbacks/))\n\n2. **AWS Security Hub Network Scanning + Azure support** — Security Hub added active Network Scanning to find resources actually reachable from the public internet, and also expanded unified security management to **Microsoft Azure** resources, making this a notable multi-cloud security/posture-management move. ([aws.amazon.com](https://aws.amazon.com/blogs/aws/aws-weekly-roundup-aws-builder-center-at-one-year-network-scanning-in-security-hub-loom-for-aws-and-more-july-13-2026/))\n\n3. **New frontier models on Amazon Bedrock: Claude Sonnet 5, Claude Opus 5, and OpenAI GPT-5.6 models** — AWS added major new model choices to Bedrock this month: Anthropic’s Claude Sonnet 5 and Claude Opus 5, plus OpenAI GPT-5.6 Sol, Terra, and Luna, expanding Bedrock’s role as a multi-model enterprise AI platform. ([aws.amazon.com](https://aws.amazon.com/blogs/aws/aws-weekly-roundup-one-click-lambda-setup-prompt-openai-gpt-5-6-models-on-bedrock-and-more-july-20-2026/))",
      "type": "output_text"
    }
  ],
  "id": "msg_dcda8e4b477f5a1d96bfbcadefef7a77",
  "phase": "final_answer",
  "role": "assistant",
  "status": "completed",
  "type": "message"
}
```

### Direct HTTPS request
<a name="web-search-direct-https"></a>

If you are not using the OpenAI SDK, send the request directly to the Responses endpoint. The `tools` field carries the Web Search tool.

```
curl "https://bedrock-mantle.us-west-2.api.aws/openai/v1/responses" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai.gpt-5.6-terra",
    "input": "What are the most significant AWS launches announced this month?",
    "tools": [{"type": "web_search", "external_web_access": false}]
  }'
```

### Reading citations from the response
<a name="web-search-reading-citations"></a>

Web Search returns citations as `url_citation` annotations attached to the text. Each annotation carries the source title and URL and the character span in the answer it supports. Retain and display these to end users.

A citation can be based on a Search observation even when Fetch did not retrieve the full page. Don't use the presence of a citation to determine whether content came from the Amazon Bedrock cache or the external web. To audit Fetch outcomes and retrieval sources, use the `fetchedSources` field in CloudTrail. For details, see [Monitor Web Search](monitoring-web-search.md).

```
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="openai.gpt-5.6-terra",
    input="What are the most significant AWS launches announced this month?",
    tools=[{"type": "web_search", "external_web_access": False}],
)

# The grounded answer
print(response.output_text)

# The sources behind it
for item in response.output:
    if item.type == "message":
        for block in item.content:
            if block.type == "output_text":
                for ann in block.annotations:
                    if ann.type == "url_citation":
                        print(f"- {ann.title}: {ann.url}")
```

If you are working with the raw JSON (for example, from a direct HTTPS call), the same data lives at `output[].content[].annotations[]`:

```
jq '.output[] | select(.type=="message") | .content[]
      | select(.type=="output_text") | .annotations[]
      | select(.type=="url_citation") | {title, url, start_index, end_index}' response.json
```

### Streaming responses
<a name="web-search-streaming"></a>

The Responses API streams the answer as it is generated. Text arrives as `response.output_text.delta` events, and each citation arrives as a `response.output_text.annotation.added` event as the model grounds a statement.

```
from openai import OpenAI

client = OpenAI()

stream = client.responses.create(
    model="openai.gpt-5.6-terra",
    input="What are the most significant AWS launches announced this month?",
    tools=[{"type": "web_search", "external_web_access": False}],
    stream=True,
)

for event in stream:
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
    elif event.type == "response.output_text.annotation.added":
        ann = event.annotation
        print(f"\n[source] {ann['title']}: {ann['url']}")
```

Over the wire, the annotation event looks like this:

```
event: response.output_text.annotation.added
data: {"type":"response.output_text.annotation.added","annotation":{"type":"url_citation","title":"News and Updates from the July 2025 Pokémon Presents","url":"https://www.pokemon.com/us/pokemon-news/...","start_index":589,"end_index":698},"annotation_index":2,"content_index":0,"item_id":"msg_...","output_index":1}
```

## Security
<a name="web-search-security-overview"></a>

Web Search on Amazon Bedrock uses AWS Identity and Access Management (IAM) to control who can run searches and fetches and in which Regions. The IAM service prefix for Web Search is `bedrock-websearch`. For the full list of actions, managed policies, condition keys, example policies, and administrator controls for disabling Web Search, see [Identity and access management for Web Search](security-web-search.md).

## Monitoring with CloudTrail
<a name="web-search-monitoring-overview"></a>

Web Search on Amazon Bedrock is integrated with AWS CloudTrail. CloudTrail captures API activity for Web Search as data events, so you can audit who invoked the tool, when, and from where. For the fields captured, how to enable data event logging, and what is intentionally excluded, see [Monitor Web Search](monitoring-web-search.md).

## Data retention
<a name="web-search-data-retention"></a>

This section describes how Web Search tool works and data handling. For more details on how your prompts and model outputs are handled, see [Data retention](data-retention.md).

### How does Web Search work?
<a name="web-search-data-retention-how"></a>

The Web Search tool supports two operations: Search and Fetch. Search returns a ranked list of observations as search results for a model generated query. Each observation includes a title, a source URL, and a content snippet. Search results are retrieved from a Web index built by Amazon that includes publicly available web content, licensed content and structured Amazon Knowledge Graph data. Fetch returns the contents of a specific URL to the model. When `external_web_access` is enabled, live web content can be retrieved for URLs present in Amazon's Web index or the public web. URLs fetched from the public web are written to a Live-Fetch cache where they are retained temporarily to avoid exceeding polite request rates against publisher sites.

By default, Web Search retrieves content entirely from Amazon's Web index and data does not leave the AWS boundary. Web Search can retrieve live content from the web only if you explicitly enable `external_web_access`. This distinction determines most of the retention behavior described in the next sections.

### What Web Search does not retain
<a name="web-search-data-retention-not-retained"></a>

#### Prompts and search queries
<a name="web-search-data-retention-prompts-queries"></a>

Web Search does not persist your prompt. Your prompt input and model generated search queries are not written into durable storage.

#### Search results tied to your account
<a name="web-search-data-retention-results"></a>

Search results include a title, source URL and content snippets. They are not written into durable storage against your account, your request identity, or your prompt text.

### Data sharing
<a name="web-search-data-retention-data-sharing"></a>

Search operations are served from a Web index and cache that is built and operated by Amazon. Your prompts and model generated tool calls are not sent to a third-party search provider.

Depending on the model you use, your request may be subject to automated Amazon Bedrock abuse detection. Retention of prompts and model outputs by Amazon Bedrock is governed separately by your account or project data retention mode. See [Data retention](data-retention.md) for more details.

### External web access
<a name="web-search-data-retention-external"></a>

By default, retrieval is served entirely from Amazon's Web index, and no request data leaves the AWS boundary. Only when you choose to enable external web access by granting `bedrock-websearch:ExternalWebAccess` and set `external_web_access` to `true` can Fetch retrieve content live from the web. See [Controlling external web access](#web-search-controlling-external) for more details.

## Acceptable use
<a name="web-search-acceptable-use"></a>

If you use Web Search on Amazon Bedrock, Amazon Bedrock provides Web Search results (“Search Results”) to supported models, which the model may use to generate its response. You are responsible for your use, and any use by your end users, of model outputs that incorporate Search Results. You must retain and display the source citations and links provided in model outputs in any output you surface to your end users. You may not use Web Search to (a) extract, store, or reproduce content from Search Results in bulk, or (b) build or populate a competing index or database.