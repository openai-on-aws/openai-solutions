

# Data retention
<a name="data-retention"></a>

## Overview
<a name="data-retention-overview"></a>

Amazon Bedrock gives you explicit control over whether the prompts and outputs from your inference requests are retained. You can configure data retention in a given AWS Region at the account level or project level, and the setting is enforced consistently across the Messages, Chat Completions, and Responses APIs. The setting is per-Region: it governs every request in the Region where you set it and does not propagate to other Regions. A Region you have not configured remains at `inherit` and falls back to each model's default.

Your data retention configuration is yours to manage. If your account in a specific Region or project is configured for zero data retention (`data_retention_mode: none`) and you invoke a model that requires retention, Amazon Bedrock will block the request and return an error — you always control your retention policy.

**Important**  
There is no data retention change to Claude models released before Claude Fable 5. We are committed to ensuring you are in full control over when and with whom your data is retained and shared. For a full list of models requiring data retention, see [Amazon Bedrock abuse detection](abuse-detection.html).

## Data retention modes
<a name="data-retention-modes"></a>

Data retention is controlled by a **mode** rather than a simple on/off toggle:


| **Mode** | **Behavior** | 
| --- | --- | 
| none | Zero data retention. No request or response data is written to durable storage by AWS or shared with the model provider. On the Responses API, store defaults to false and store=true is rejected. Background mode is not available. Chat Completions and Messages requests are never retained. | 
| default | Default means the data retention policy of the model applies. There is no change to previous model retention behavior; if ZDR applied previously, then ZDR still applies. Actual retention depends on the model — consult the model's terms for specifics. AWS may retain the data for safety and abuse-prevention purposes. The model provider does not receive it. On the Responses API, `store` defaults to `true` and may be set to either value.Setting `store=false` does not guarantee zero data retention. Some models may still retain data for safety review even when `store=false` — in this case, data is retained but is not retrievable by the customer through `GET /v1/responses/{id}`. If you require guaranteed zero retention, set `data_retention_mode` to `none`. | 
| aws\_review | This mode allows your inputs and outputs to be retained for human review by AWS. Review is carried out by AWS within the AWS boundary — the model provider does not review your content, and your content is not shared with the provider. Some model providers require Amazon to conduct human review as a condition of access to their models, and this mode is required for access to those models. If a model does not require human review, AWS will not review your content.<br />See [Amazon Bedrock abuse detection](abuse-detection.html) and [AWS Service Terms](https://aws.amazon.com/service-terms/). | 
| `provider_data_share`<br />**(legacy)** | **This mode is legacy, and Amazon Bedrock does not share your content with model providers today.** Setting this mode does not cause your inputs or outputs to be shared with a model provider. New configurations should use `aws_review`.<br />**If you are already set to `provider_data_share`, you do not need to change anything** — it sits above `aws_review` in the ordering below, so it continues to satisfy every model that requires human review. See [Amazon Bedrock abuse detection](abuse-detection.html) and [AWS Service Terms](https://aws.amazon.com/service-terms/). | 
| inherit | No opinion at this scope — defer to a broader scope. This is the default for new accounts and projects. | 

**Human review: `aws_review` and legacy `provider_data_share`**  
Some model providers require that inputs and outputs be available for human review as a condition of access to their models. Two modes grant that permission, differing in who performs the review and in whether your content leaves AWS. `aws_review` is the current mechanism; `provider_data_share` is legacy.  


| **Mode** | **Who reviews your content** | **Does your content leave AWS?** | 
| --- | --- | --- | 
| aws\_review | AWS | No | 
| provider\_data\_share (legacy) | No one — provider review is not supported today | No | 
AWS reviews content only for models whose provider requires human review. Sharing content with model providers is not supported today, so `provider_data_share` grants a permission that is not exercised — use `aws_review` instead.

## How modes are ordered
<a name="data-retention-mode-ordering"></a>

Retention modes form an ordered scale, from least to most permissive:

```
none  <  default  <  aws_review  <  provider_data_share
```

A model is available to you when your effective mode is at or above the mode that model requires. A more permissive setting subsumes a less permissive one: if you have authorized AWS to share your content with the model provider, you have also authorized AWS to review it itself.

`inherit` is not part of this ordering — it expresses no opinion at its scope and defers to a broader one. See [How your retention mode is determined](#data-retention-resolution).

**Existing `provider_data_share` configurations keep working**  
If your account or project is already set to `provider_data_share`, you do not need to take any action to continue using models that require `aws_review`, including Claude Fable 5 and Claude Fable 5.1. Because `provider_data_share` is the more permissive setting, it continues to satisfy those models' requirement.  
Moving from `provider_data_share` to `aws_review` is nonetheless worth doing where you can: it states the behavior that actually applies, since content sharing with model providers is not supported today.

**Important**  
Configuring your account or project to `aws_review` does *not* mean all models will start retaining your content for review. Your configured mode sets what you allow — each model independently declares which modes it supports through `allowed_modes`. Most models currently do not require human review. The interaction works as follows:  
If a model's `allowed_modes` includes `none`, we won't persist anything.
If a model's `allowed_modes` includes `default` but not `none`, AWS retains the data — the model provider does not receive it.
If a model's `allowed_modes` includes `aws_review`, AWS retains the data and AWS may review it — the model provider does not receive it. AWS reviews content only for models whose provider requires human review.
If a model's minimum requirement is `aws_review`, the model is available only when your effective mode is `aws_review` or higher. If your effective mode is `none` or `default`, the model will appear as unavailable on the bedrock-mantle endpoint, and requests to it will return a `ValidationException` error on the bedrock-runtime endpoint.
Setting the legacy `provider_data_share` does not cause your content to be shared with a model provider — content sharing is not supported today.

## How your retention mode is determined
<a name="data-retention-resolution"></a>

Data retention is configured at two scopes, with the model's own default as the fallback:
+ **Project** (most specific) — set through `POST /v1/organization/projects/{project_id}`
+ **Account** (at the Region level) — set through `PUT /v1/data_retention`
+ **Model default** (least specific, read-only) — the model's built-in default

The effective mode for any request is determined by taking the first scope whose value is not `inherit`:

```
effective mode = first non-inherit value of (project → account → model default)
```

For example, if your project is set to `inherit` and your account is set to `none`, the effective mode is `none` for all models invoked from that project.

## Configuring data retention
<a name="data-retention-configuration"></a>

### Set account-wide data retention in a specific Region
<a name="data-retention-set-account"></a>

```
curl -X PUT https://bedrock-mantle.us-east-1.api.aws/v1/data_retention \
  -H "x-api-key: $BEDROCK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "mode": "aws_review" }'
```

**Response:**

```
{
  "mode": "aws_review",
  "updated_at": 1733529600
}
```

### Set project-level data retention
<a name="data-retention-set-project"></a>

Projects are specific to the bedrock-mantle endpoint. The Bedrock control plane and Runtime APIs have no project concept, so bedrock-runtime requests cannot be project-scoped.

```
curl https://bedrock-mantle.us-east-1.api.aws/v1/organization/projects/proj_abc123 \
  -H "x-api-key: $BEDROCK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "data_retention": { "mode": "aws_review" } }'
```

To invoke models with your desired data retention mode on a bedrock-runtime endpoint, set your account data retention mode in that Region using the Bedrock Control Plane API.

```
curl -X PUT https://bedrock.us-east-1.amazonaws.com/data-retention \
  -H "Authorization: Bearer $AWS_BEARER_TOKEN_BEDROCK" \
  -H "Content-Type: application/json" \
  -d '{ "mode": "aws_review" }'
```

**Response:**

```
{
  "mode": "aws_review",
  "updated_at": "2026-06-07T20:19:44.723Z"
}
```

### Check your current configuration
<a name="data-retention-check-config"></a>

```
# Account level
curl https://bedrock-mantle.us-east-1.api.aws/v1/data_retention \
  -H "x-api-key: $BEDROCK_API_KEY"

# Project level
curl https://bedrock-mantle.us-east-1.api.aws/v1/organization/projects/proj_abc123 \
  -H "x-api-key: $BEDROCK_API_KEY"
```

To check your current configuration on a bedrock-runtime endpoint, use the Bedrock Control Plane API.

```
# Account level
curl https://bedrock.us-east-1.amazonaws.com/data-retention \
  -H "Authorization: Bearer $AWS_BEARER_TOKEN_BEDROCK"
```

### Check a model's effective mode and allowed modes
<a name="data-retention-check-model"></a>

```
curl https://bedrock-mantle.us-east-1.api.aws/v1/models/anthropic.claude-fable-5 \
  -H "x-api-key: $BEDROCK_API_KEY"
```

**Response:**

```
{
  "id": "anthropic.claude-fable-5",
  "created": 1733443200,
  "owned_by": "system",
  "status": "available",
  "data_retention": {
    "mode": "aws_review",
    "source": "account",
    "allowed_modes": ["aws_review", "provider_data_share"]
  }
}
```

**Note**  
The Bedrock control plane does not expose a per-model retention signal.

## Model availability and data retention
<a name="data-retention-model-availability"></a>

Each model declares the retention modes that satisfy its requirement through `allowed_modes`, which lists every mode at or above the minimum the model needs. If your effective mode sits below what the model requires — see [How modes are ordered](#data-retention-mode-ordering) — the model will appear as `status: "unavailable"` in the models list on the bedrock-mantle endpoint, and requests to it on the bedrock-runtime endpoint will fail with a `ValidationException` error.

**Example:** Claude Fable 5 and Claude Fable 5.1 require human review (`allowed_modes: ["aws_review", "provider_data_share"]`). You must explicitly set your data retention mode to `aws_review`, or to the legacy `provider_data_share`, before you can invoke these models. If your effective mode is `none` or `default`, these models will be unavailable.

By setting `aws_review`, you are explicitly instructing us to retain your inputs and outputs so that AWS can perform the human review the model provider requires as a condition of access. Your content is not shared with the model provider. See [Amazon Bedrock abuse detection](abuse-detection.html) and [AWS Service Terms](https://aws.amazon.com/service-terms/).

**Note**  
At launch, there is no console UI for configuring data retention. Customers must use the API (see "Configuring data retention" above) or the Bedrock SDK.

**Response when a model is unavailable due to retention policy:**

```
{
  "id": "anthropic.claude-fable-5",
  "created": 1733443200,
  "owned_by": "system",
  "status": "unavailable",
  "status_reason": "This model is not available under data retention mode 'default'.",
  "data_retention": {
    "mode": "default",
    "source": "account",
    "allowed_modes": ["aws_review", "provider_data_share"]
  }
}
```

### How to opt in for the bedrock-mantle endpoint
<a name="data-retention-opt-in"></a>

To enable Claude Fable 5 and Claude Fable 5.1 for your account:

```
curl https://bedrock-mantle.us-east-1.api.aws/v1/data_retention \
  -H "x-api-key: $BEDROCK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "mode": "aws_review" }'
```

Or at the project level (if you want to limit human review to a specific project):

```
curl https://bedrock-mantle.us-east-1.api.aws/v1/organization/projects/proj_abc123 \
  -H "x-api-key: $BEDROCK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "data_retention": { "mode": "aws_review" } }'
```

**How to opt in for the bedrock-runtime endpoint using the Bedrock Control Plane API:**

```
curl -X PUT https://bedrock.us-east-1.amazonaws.com/data-retention \
  -H "Authorization: Bearer $AWS_BEARER_TOKEN_BEDROCK" \
  -H "Content-Type: application/json" \
  -d '{ "mode": "aws_review" }'
```

**Mixed-model projects**  
Setting a project to `aws_review` does not mean all model traffic in that project is retained for review. Each model's `allowed_modes` determines what actually happens to your data:  
A model whose `allowed_modes` is `["aws_review", "provider_data_share"]` (for example, Claude Fable 5)—human review is required, so data is retained within the AWS boundary and may be reviewed by AWS on any request. It is not shared with the model provider.
A model whose `allowed_modes` is `["none", "default", "aws_review", "provider_data_share"]` (for example, Claude Opus 4.8)—the model permits `none`, so data is not retained whatever mode you set. A more permissive account or project setting does not cause its content to be retained, reviewed, or shared.

## Zero data retention (ZDR) access
<a name="data-retention-zdr"></a>

Some models require data retention for safety and abuse-prevention purposes. If your organization requires zero data retention for compliance reasons and you need access to these models, contact your AWS account manager to discuss eligibility. ZDR access is evaluated on a per-account, per-model basis in coordination with the model provider.

Accounts approved for ZDR on a specific model will see `"none"` included in that model's `allowed_modes`.

**Anthropic Claude models**  
ZDR eligibility for Claude models is managed by Anthropic. Contact your Anthropic account representative for support.

## Enforcing retention policy with IAM
<a name="data-retention-iam"></a>

You can enforce a data retention policy across your organization using IAM policies or Service Control Policies (SCPs). The write actions publish a `bedrock-mantle:DataRetentionMode` condition key that lets you restrict which modes can be set.

**Example SCP — require zero data retention across the organization:**

```
{
    "Effect": "Deny",
    "Action": [
        "bedrock-mantle:PutAccountDataRetention",
        "bedrock-mantle:CreateProject",
        "bedrock-mantle:UpdateProject"
    ],
    "Resource": "*",
    "Condition": {
        "StringNotEquals": {
            "bedrock-mantle:DataRetentionMode": "none"
        }
    }
}
```

**Bedrock Control Plane:**

```
{
    "Effect": "Deny",
    "Action": [
        "bedrock:PutAccountDataRetention"
    ],
    "Resource": "*",
    "Condition": {
        "StringNotEquals": {
            "bedrock:DataRetentionMode": "none"
        }
    }
}
```

This prevents anyone in the organization from setting data retention to anything other than `none`, ensuring no inference data is ever retained.

**Example SCP — permit AWS retention but not human review:**

```
{
    "Effect": "Deny",
    "Action": [
        "bedrock-mantle:PutAccountDataRetention",
        "bedrock-mantle:CreateProject",
        "bedrock-mantle:UpdateProject"
    ],
    "Resource": "*",
    "Condition": {
        "ForAnyValue:StringEquals": {
            "bedrock-mantle:DataRetentionMode": [
                "aws_review",
                "provider_data_share"
            ]
        }
    }
}
```

Use this when your organization accepts retention for abuse detection but cannot permit human review of its content. Models that require human review will appear as `status: "unavailable"` on the bedrock-mantle endpoint, and requests to them on the bedrock-runtime endpoint will fail with a `ValidationException` error.

## What data is retained and for how long
<a name="data-retention-what-is-retained"></a>

For models requiring `aws_review` (currently Claude Fable 5 and Claude Fable 5.1): user prompts and completions are retained within the AWS boundary for up to 30 days and may be reviewed by AWS to meet the human review requirement the model provider imposes as a condition of access. Your content is not shared with the model provider.

For the legacy `provider_data_share` mode: Amazon Bedrock does not share your content with model providers today, so this mode results in the same handling as `aws_review` — retained within the AWS boundary for up to 30 days, and reviewed by AWS only where the model requires it.

For models under `default` mode: data may be retained for abuse detection purposes — see [Amazon Bedrock abuse detection](abuse-detection.html) for required retention details. For retention beyond abuse detection (for example, Responses API with `store=true`), consult the model's documentation and terms.

If cross-region inference is enabled for these models, retained inputs and outputs are stored in destination Regions (that is, the Region where your inference request is processed).

See [Anthropic Terms of Service](https://aws.amazon.com/legal/bedrock/third-party-models/) for model-specific data handling details.

## IAM actions reference
<a name="data-retention-iam-reference"></a>


| **Route** | **IAM action** | 
| --- | --- | 
| GET /v1/models | bedrock-mantle:ListModels | 
| GET /v1/models/{model} | bedrock-mantle:GetModel | 
| GET /v1/data\_retention | bedrock-mantle:GetAccountDataRetention | 
| PUT /v1/data\_retention | bedrock-mantle:PutAccountDataRetention | 
| GET /v1/organization/projects/{project\_id} | bedrock-mantle:GetProject | 
| POST /v1/organization/projects/{project\_id} | bedrock-mantle:UpdateProject | 


| **Route** | **IAM action** | 
| --- | --- | 
| GET /data-retention | bedrock:GetAccountDataRetention | 
| PUT /data-retention | bedrock:PutAccountDataRetention | 