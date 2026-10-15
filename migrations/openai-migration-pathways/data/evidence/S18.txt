

# Monitor `bedrock-mantle` API calls using CloudTrail
<a name="logging-cloudtrail-mantle"></a>

The `bedrock-mantle.{{region}}.api.aws` endpoint integrates with AWS CloudTrail. CloudTrail records calls to the `bedrock-mantle` API operations as events, including calls from the AWS Management Console, the AWS CLI, the OpenAI SDK, the Anthropic SDK, and direct HTTPS calls. Events have an `eventSource` of `bedrock-mantle.amazonaws.com`.

If your application calls inference through `bedrock-runtime.{{region}}.amazonaws.com`, see [Monitor Amazon Bedrock API calls using CloudTrail](logging-using-cloudtrail.md) instead.

For background on CloudTrail itself, see the [AWS CloudTrail User Guide](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-user-guide.html).

## Management events
<a name="mantle-cloudtrail-management-events"></a>

Management events are logged by default to your CloudTrail **Event history** at no additional cost. `bedrock-mantle` logs the following operations as management events. The `requestParameters` field of each event also contains `callWithBearerToken` (and `bearerTokenType` when applicable), which are added by the service for every event.


**Models**  

| Event name | HTTP route | Additional request parameters | 
| --- | --- | --- | 
| ListModels | GET /v1/models | none | 
| GetModel | GET /v1/models/{model} | model | 


**Fine-tuning**  

| Event name | HTTP route | Additional request parameters | 
| --- | --- | --- | 
| ListFineTuningJobs | GET /v1/fine\_tuning/jobs | none | 
| CreateFineTuningJob | POST /v1/fine\_tuning/jobs | model, trainingFile, validationFile, metadata, method (structured object including type and, for reinforcement runs, grader.lambda.function) | 
| GetFineTuningJob | GET /v1/fine\_tuning/jobs/{id}, /events, /checkpoints | fineTuningJob | 
| CancelFineTuningJob | POST /v1/fine\_tuning/jobs/{id}/cancel | fineTuningJob | 


**Projects**  

| Event name | HTTP route | Additional request parameters | 
| --- | --- | --- | 
| ListProjects | GET /v1/organization/projects | none | 
| CreateProject | POST /v1/organization/projects | name, tags, data\_retention\_mode | 
| GetProject | GET /v1/organization/projects/{project\_id} | project\_id | 
| UpdateProject | POST /v1/organization/projects/{project\_id} | project\_id, name, add\_tags, remove\_tag\_keys, tags, data\_retention\_mode | 
| ArchiveProject | POST /v1/organization/projects/{project\_id}/archive | project\_id | 

In a request body, the project data-retention mode is the `mode` field of a `data_retention` object. CloudTrail records it as the flat `data_retention_mode` key shown in the preceding table. `CreateProject` records this key on every call, including calls that omit `data_retention`, in which case the recorded value is `inherit`. `UpdateProject` records it only when the request sets `data_retention`, which that operation requires you to set on its own, so `data_retention_mode` never appears in the same `UpdateProject` event as `name`, `tags`, `add_tags`, or `remove_tag_keys`.

## Data events
<a name="mantle-cloudtrail-data-events"></a>

Data events are not logged by default and incur additional CloudTrail charges. `bedrock-mantle` logs the following operations as data events. To capture them, configure advanced event selectors on your trail or event data store as described in [Logging data events](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/logging-data-events-with-cloudtrail.html).


**Inference**  

| Event name | HTTP route | Additional request parameters | 
| --- | --- | --- | 
| CreateInference | POST /v1/responses | model, previousResponse, stream, service\_tier, metadata | 
| CreateInference | POST /v1/responses/compact | model, previous\_response\_id | 
| CreateInference | POST /v1/chat/completions | model, stream, service\_tier, metadata | 
| CreateInference | POST /v1/embeddings | model | 
| CreateInference | POST /anthropic/v1/messages | model, stream, max\_tokens | 
| GetInference | GET /v1/responses/{response\_id} | response, stream | 
| CancelInference | POST /v1/responses/{response\_id}/cancel | response | 
| DeleteInference | DELETE /v1/responses/{response\_id} | response | 
| CountTokens | POST /anthropic/v1/messages/count\_tokens | model | 


**Files**  

| Event name | HTTP route | Additional request parameters | 
| --- | --- | --- | 
| ListFiles | GET /v1/files | limit, order, purpose, after | 
| CreateFile | POST /v1/files | purpose, filename, bytes | 
| GetFile | GET /v1/files/{file\_id}, /content | file | 
| DeleteFile | DELETE /v1/files/{file\_id} | file | 

**Note**  
Customer-supplied `metadata` on `CreateInference` calls is logged verbatim in CloudTrail. Do not include secrets, credentials, or other sensitive values in `metadata` if you are capturing data events.

## Configuring data event capture
<a name="mantle-cloudtrail-configuring"></a>

The following example configures a trail to capture `bedrock-mantle` data events associated with a project:

```
aws cloudtrail put-event-selectors \
    --trail-name <trailName> \
    --advanced-event-selectors '[
      {
        "Name": "Log Bedrock Mantle project data events",
        "FieldSelectors": [
          { "Field": "eventCategory", "Equals": ["Data"] },
          { "Field": "resources.type", "Equals": ["AWS::BedrockMantle::Project"] }
        ]
      }
    ]'
```

You can additionally filter by `eventName` and `resources.ARN`. For details on advanced event selectors, see [AdvancedFieldSelector](https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_AdvancedFieldSelector.html).

## Resource types
<a name="mantle-cloudtrail-resource-types"></a>

Use `AWS::BedrockMantle::Project` as the `resources.type` field selector when you configure CloudTrail data event capture for `bedrock-mantle`.

The `resources` array in a delivered event references the following resource type, which is also the only value that the `resources.type` field selector supports for `bedrock-mantle`:
+ `AWS::BedrockMantle::Project`

## Example log entry
<a name="mantle-cloudtrail-example"></a>

The following example is a `CreateInference` data event. The `eventType` value `AwsApiCall` indicates that the event records an API call; it doesn't classify the event as a management event. The `eventCategory` value `Data` and the `managementEvent` value `false` identify it as a data event.

```
{
    "eventVersion": "1.08",
    "userIdentity": {
        "type": "IAMUser",
        "principalId": "AROAICFHPEXAMPLE",
        "arn": "arn:aws:iam::111122223333:user/userxyz",
        "accountId": "111122223333",
        "accessKeyId": "AKIAIOSFODNN7EXAMPLE",
        "userName": "userxyz"
    },
    "eventTime": "2026-05-30T14:32:11Z",
    "eventSource": "bedrock-mantle.amazonaws.com",
    "eventName": "CreateInference",
    "awsRegion": "us-east-1",
    "sourceIPAddress": "192.0.2.0",
    "userAgent": "OpenAI/Python 1.50.0",
    "requestParameters": {
        "model": "anthropic.claude-opus-4-7",
        "stream": true,
        "service_tier": "default",
        "metadata": {"team": "platform"},
        "callWithBearerToken": true,
        "bearerTokenType": "ABSK"
    },
    "responseElements": null,
    "requestID": "a1b2c3d4-5678-90ab-cdef-EXAMPLE22222",
    "eventID": "a1b2c3d4-5678-90ab-cdef-EXAMPLE11111",
    "readOnly": false,
    "eventType": "AwsApiCall",
    "managementEvent": false,
    "recipientAccountId": "111122223333",
    "eventCategory": "Data",
    "resources": [
        {
            "accountId": "111122223333",
            "type": "AWS::BedrockMantle::Project",
            "ARN": "arn:aws:bedrock-mantle:us-east-1:111122223333:project/proj_abc123"
        }
    ],
    "tlsDetails": {
        "tlsVersion": "TLSv1.3",
        "cipherSuite": "TLS_AES_128_GCM_SHA256",
        "clientProvidedHostHeader": "bedrock-mantle.us-east-1.api.aws"
    }
}
```

## Differences from `bedrock-runtime` CloudTrail logging
<a name="mantle-cloudtrail-differences"></a>
+ **Inference is a data event on `bedrock-mantle`, a management event on `bedrock-runtime`.** The `bedrock-runtime` endpoint logs [Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html), [ConverseStream](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseStream.html), [InvokeModel](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModel.html), and [InvokeModelWithResponseStream](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModelWithResponseStream.html) as management events at no additional cost. The `bedrock-mantle` endpoint logs `CreateInference` and the other inference operations as data events, which incur CloudTrail data event charges. If you require an audit trail of inference calls on `bedrock-mantle`, you must explicitly enable data event capture on your trail or event data store.
+ **Different event source and resource types.** `bedrock-mantle` events use an `eventSource` of `bedrock-mantle.amazonaws.com` and reference `AWS::BedrockMantle::*` resource types. CloudTrail Lake queries, Athena views, and detective controls that filter on `bedrock.amazonaws.com` or `bedrock-runtime.amazonaws.com` will not capture `bedrock-mantle` activity.