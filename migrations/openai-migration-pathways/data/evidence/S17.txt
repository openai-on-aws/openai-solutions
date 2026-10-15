

# Monitor `bedrock-mantle` inference using CloudWatch metrics
<a name="monitoring-mantle-metrics"></a>

The Amazon Bedrock OpenAI-compatible endpoint (`bedrock-mantle.{{region}}.api.aws`) publishes customer-facing metrics to Amazon CloudWatch under the `AWS/BedrockMantle` namespace. Use these metrics to monitor inference volume, token consumption, and error rates across your AWS account, projects, and models.

If your application calls inference through `bedrock-runtime.{{region}}.amazonaws.com` using [Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html), [ConverseStream](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseStream.html), [InvokeModel](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModel.html), or [InvokeModelWithResponseStream](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModelWithResponseStream.html), see [Amazon Bedrock runtime metrics](monitoring-runtime-metrics.md#runtime-cloudwatch-metrics) instead. `bedrock-mantle` metrics cover only inference issued through the Responses API, Chat Completions API, and Anthropic Messages API on the `bedrock-mantle` endpoint.

`bedrock-mantle` publishes metrics at four levels of granularity. Each level uses a different combination of CloudWatch dimensions, described in [Dimensions](#mantle-metrics-dimensions). All metrics are scoped to your AWS account.

## Inference metrics
<a name="mantle-inference-metrics"></a>


**Inference metrics**  

| Metric name | Unit | Description | 
| --- | --- | --- | 
| Inferences | Count | Total number of completed inference requests across the Responses, Chat Completions, and Messages APIs. Published at Account, Project, Model, and Project\+Model levels. | 
| InferenceClientErrors | Count | Number of inference requests that were accepted for processing and later failed with a client-side error. This metric doesn't include requests rejected before processing, including quota-related HTTP 429 responses. To monitor throttling, track HTTP 429 responses in your application. Published at Account, Project, Model, and Project\+Model levels. | 

## Token metrics
<a name="mantle-token-metrics"></a>


**Token metrics**  

| Metric name | Unit | Description | 
| --- | --- | --- | 
| TotalInputTokens | Count | Aggregate billable input tokens processed within the publish interval. Published at Account, Project, and Model levels. Use for sums and rate calculations. | 
| TotalOutputTokens | Count | Aggregate billable output tokens generated within the publish interval. Published at Account, Project, and Model levels. | 
| InputTokens | Count | Per-inference billable input tokens. Each completed inference emits one datum. Published at the Project\+Model level only. Use this when you need percentile statistics (p50/p90/p99) of per-request token counts. | 
| OutputTokens | Count | Per-inference billable output tokens. Each completed inference emits one datum. Published at the Project\+Model level only. | 

## Dimensions
<a name="mantle-metrics-dimensions"></a>


**Dimensions**  

| Dimension name | Values | Applies to | 
| --- | --- | --- | 
| Project | The project ID associated with the inference request. | Project, Project\+Model | 
| Model | The model identifier (for example, anthropic.claude-opus-4-7). | Model, Project\+Model | 

Account-level metrics are scoped to your AWS account and have no additional dimensions. Each level of granularity emits independently, so a single inference contributes to all four levels when both the project and the model can be resolved.

## Choosing the right granularity level
<a name="mantle-metrics-granularity"></a>
+ **Account level** – overall usage, error rate, and aggregate token volume. Suitable for high-level dashboards and account-wide alarms. Not suitable for cost analysis, because pricing varies by model.
+ **Project level** – per-project rollups for chargeback and team-level dashboards.
+ **Model level** – per-model usage and error rates, suitable for migrating dashboards built against the existing `bedrock-runtime` `ModelId` dimension.
+ **Project\+Model level** – primary level for cost analysis, and percentile latency and token analysis. Use this when you need both project attribution and model attribution on the same datum.

## Differences from `bedrock-runtime` metrics
<a name="mantle-metrics-differences"></a>
+ **Separate namespace.** `bedrock-mantle` metrics publish to `AWS/BedrockMantle`. Existing dashboards and alarms built against `AWS/Bedrock` will not pick up `bedrock-mantle` traffic.
+ **Naming.** `bedrock-mantle` uses `Inferences` rather than `Invocations`, `TotalInputTokens` and `TotalOutputTokens` rather than `InputTokenCount` and `OutputTokenCount`, and `InferenceClientErrors` rather than `InvocationClientErrors`.
+ **Project dimension.** `bedrock-mantle` metrics carry a `Project` dimension that `bedrock-runtime` metrics do not, enabling per-project cost attribution.
+ **Cross-region inference.** `bedrock-mantle` is in-region only. Metrics are emitted in the Region that handled the request and are not aggregated across Regions the way cross-Region inference (CRIS) traffic is on `bedrock-runtime`.
+ **Latency metrics.** `InvocationLatency` and `TimeToFirstToken` equivalents are not yet published by `bedrock-mantle`.

## Viewing `bedrock-mantle` metrics
<a name="mantle-metrics-viewing"></a>

To view `bedrock-mantle` metrics in the CloudWatch console:

1. Open the CloudWatch console.

1. In the navigation pane, choose **Metrics**, **All metrics**.

1. Choose the `AWS/BedrockMantle` namespace.

1. Select a granularity level by choosing the dimension set that matches your query (for example, `Project, Model` for project-and-model breakdowns).

You must have appropriate CloudWatch permissions to read `bedrock-mantle` metrics. For more information, see [Authentication and access control for Amazon CloudWatch](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/auth-and-access-control-cw.html) in the *Amazon CloudWatch User Guide*.