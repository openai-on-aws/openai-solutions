

# Monitor model invocation using CloudWatch Logs and Amazon S3
<a name="model-invocation-logging"></a>

You can use model invocation logging to collect invocation logs, model input data, and model output data for all invocations in your AWS account used in Amazon Bedrock in a Region.

With invocation logging, you can collect the full request data, response data, and metadata associated with supported calls performed in your account in a Region. Logging can be configured to provide the destination resources where the log data will be published. Supported destinations include Amazon CloudWatch Logs and Amazon Simple Storage Service (Amazon S3). Only destinations from the same account and Region are supported.

Model invocation logging is disabled by default. After model invocation logging is enabled, logs are stored until the logging configuration is deleted.

The following operations can log model invocations.
+ [Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
+ [ConverseStream](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseStream.html)
+ [InvokeModel](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModel.html)
+ [InvokeModelWithResponseStream](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModelWithResponseStream.html)

**Note**  
Model invocation logging is only supported for calls made through the `bedrock-runtime` endpoint. This includes the OpenAI-compatible Responses and Chat Completions APIs on that endpoint. Calls made through other endpoints, such as the same APIs on `bedrock-mantle`, are not currently captured by invocation logging.

When [using the Converse API](conversation-inference-call.md), any image or document data that you pass is logged in Amazon S3 (if you have [enabled](#model-invocation-logging-console) delivery and image logging in Amazon S3).

Before you can enable invocation logging, you need to set up an Amazon S3 or CloudWatch Logs destination. You can enable invocation logging through either the console or the API.

**Topics**
+ [Set up an Amazon S3 destination](#setup-s3-destination)
+ [Set up an CloudWatch Logs destination](#setup-cloudwatch-logs-destination)
+ [Model invocation logging using the console](#model-invocation-logging-console)
+ [Model invocation logging using the API](#using-apis-logging)
+ [Log entry format](#model-invocation-log-format)

## Set up an Amazon S3 destination
<a name="setup-s3-destination"></a>

**Note**  
When using Amazon S3 as a logging destination, the bucket must be in the same AWS account and AWS Region as the one where you're creating the model invocation logging configuration.

You can set up an S3 destination for logging in Amazon Bedrock with these steps:

1. Create an S3 bucket where the logs will be delivered.

1. Add a bucket policy to it like the one below (Replace values for {{accountId}}, {{region}}, {{bucketName}}, and optionally {{prefix}}):
**Note**  
A bucket policy is automatically attached to the bucket on your behalf when you configure logging with the permissions `S3:GetBucketPolicy` and `S3:PutBucketPolicy`.

------
#### [ JSON ]

****  

   ```
   {
       "Version":"2012-10-17",		 	 	 
       "Statement": [
           {
               "Sid": "AmazonBedrockLogsWrite",
               "Effect": "Allow",
               "Principal": {
                   "Service": "bedrock.amazonaws.com"
               },
               "Action": [
                   "s3:PutObject"
               ],
               "Resource": [
                   "arn:aws:s3:::{{bucketName}}/{{prefix}}/AWSLogs/{{123456789012}}/BedrockModelInvocationLogs/*"
               ],
               "Condition": {
                   "StringEquals": {
                       "aws:SourceAccount": "{{123456789012}}"
                   },
                   "ArnLike": {
                       "aws:SourceArn": "arn:aws:bedrock:{{us-east-1}}:{{123456789012}}:*"
                   }
               }
           }
       ]
   }
   ```

------

1. (Optional) If configuring SSE-KMS on the bucket, add the following policy on the KMS key:

   ```
   {
       "Effect": "Allow",
       "Principal": {
           "Service": "bedrock.amazonaws.com"
       },
       "Action": "kms:GenerateDataKey",
       "Resource": "*",
       "Condition": {
           "StringEquals": {
             "aws:SourceAccount": "{{accountId}}" 
           },
           "ArnLike": {
              "aws:SourceArn": "arn:aws:bedrock:{{region}}:{{accountId}}:*"
           }
       }
   }
   ```

For more information on S3 SSE-KMS configurations, see [Specifying KMS Encryption](https://docs.aws.amazon.com/AmazonS3/latest/userguide/specifying-kms-encryption.html).

**Note**  
The bucket ACL must be disabled in order for the bucket policy to take effect. For more information, see [Disabling ACLs for all new buckets and enforcing Object Ownership](AmazonS3/latest/userguide/ensure-object-ownership.html).

## Set up an CloudWatch Logs destination
<a name="setup-cloudwatch-logs-destination"></a>

You can set up a Amazon CloudWatch Logs destination for logging in Amazon Bedrock with the following steps:

1. Create a CloudWatch log group where the logs will be published.

1. Create an IAM role with the following permissions for CloudWatch Logs.

   **Trusted entity**:

------
#### [ JSON ]

****  

   ```
   {
       "Version":"2012-10-17",		 	 	 
       "Statement": [
           {
               "Effect": "Allow",
               "Principal": {
                   "Service": "bedrock.amazonaws.com"
               },
               "Action": "sts:AssumeRole",
               "Condition": {
                   "StringEquals": {
                       "aws:SourceAccount": "{{123456789012}}"
                   },
                   "ArnLike": {
                       "aws:SourceArn": "arn:aws:bedrock:{{us-east-1}}:{{123456789012}}:*"
                   }
               }
           }
       ]
   }
   ```

------

   **Role policy**:

------
#### [ JSON ]

****  

   ```
   {
       "Version":"2012-10-17",		 	 	 
       "Statement": [
           {
               "Effect": "Allow",
               "Action": [
                   "logs:CreateLogStream",
                   "logs:PutLogEvents"
               ],
               "Resource": "arn:aws:logs:{{us-east-1}}:{{123456789012}}:log-group:{{logGroupName}}:log-stream:aws/bedrock/modelinvocations"
           }
       ]
   }
   ```

------

For more information on setting up SSE for CloudWatch Logs, see [Encrypt log data in CloudWatch Logs using AWS Key Management Service](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/encrypt-log-data-kms.html).

## Model invocation logging using the console
<a name="model-invocation-logging-console"></a>

**To enable model invocation logging**

Sign in to the AWS Management Console with an IAM identity that has permissions to use the Amazon Bedrock console. Then, open the Amazon Bedrock console at [https://console.aws.amazon.com/bedrock](https://console.aws.amazon.com/bedrock).

1. From the left navigation pane, select **Settings**.

1. In the **Model invocation logging** page, select **Model invocation logging**. Additional configuration settings for logging will appear.

1. Select the modalities of the data requests and responses that you want to publish to the logs. You can select any combination of the following output options:
   + Text
   + Image
   + Embedding
   + Video
**Note**  
Data will be logged for *all* models that support the modalities (whether as input or output) that you choose. For example, if you select **Image**, model invocation will be logged for all models that support image input, image output, or both.

1. Select where to publish the logs:
   + Amazon S3 only
   + CloudWatch Logs only
   + Both Amazon S3 and CloudWatch Logs 

**Logging destinations**  
Amazon S3 and CloudWatch Logs destinations are supported for invocation logs, and small input and output data. For large input and output data or binary image outputs, only Amazon S3 is supported. The following details summarize how the data will be represented in the target location.
+ **S3 destination** — Gzipped JSON files, each containing a batch of invocation log records, are delivered to the specified S3 bucket. Similar to a CloudWatch Logs event, each record will contain the invocation metadata, and input and output JSON bodies of up to 100 KB in size. Binary data or JSON bodies larger than 100 KB will be uploaded as individual objects in the specified Amazon S3 bucket under the data prefix. The data can be queried using Amazon S3 Select and Amazon Athena, and can be catalogued for ETL using AWS Glue. The data can be loaded into OpenSearch service, or be processed by any Amazon EventBridge targets. 
+ **CloudWatch Logs destination** — JSON invocation log events are delivered to a specified log group in CloudWatch Logs. The log event contains the invocation metadata, and input and output JSON bodies of up to 100 KB in size. If an Amazon S3 location for large data delivery is provided, binary data or JSON bodies larger than 100 KB will be uploaded to the Amazon S3 bucket under the data prefix instead. data can be queried using CloudWatch Logs Insights, and can be further streamed to various services in real-time using CloudWatch Logs.

## Model invocation logging using the API
<a name="using-apis-logging"></a>

Model invocation logging can be configured using the following APIs:
+ [PutModelInvocationLoggingConfiguration](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_PutModelInvocationLoggingConfiguration.html)
+ [GetModelInvocationLoggingConfiguration](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetModelInvocationLoggingConfiguration.html)
+ [DeleteModelInvocationLoggingConfiguration](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_DeleteModelInvocationLoggingConfiguration.html)

## Log entry format
<a name="model-invocation-log-format"></a>

Each invocation log entry is a JSON object with the following structure. The format is the same for both CloudWatch Logs and Amazon S3 destinations.

```
{
    "schemaType": "ModelInvocationLog",
    "schemaVersion": "1.0",
    "timestamp": "2024-01-15T12:00:00Z",
    "accountId": "123456789012",
    "region": "us-east-1",
    "requestId": "abcd1234-5678-efgh-ijkl-mnopqrstuvwx",
    "operation": "Converse",
    "modelId": "anthropic.claude-sonnet-4-20250514-v1:0",
    "identity": {
        "arn": "arn:aws:sts::123456789012:assumed-role/MyRole/session-name"
    },
    "requestMetadata": {
        "team": "orchestrator",
        "environment": "production"
    },
    "input": {
        "inputContentType": "application/json",
        "inputBodyJson": { },
        "inputTokenCount": 25
    },
    "output": {
        "outputContentType": "application/json",
        "outputBodyJson": { },
        "outputTokenCount": 150
    }
}
```

The following table describes the fields in a log entry:



| Field | Description | 
| --- | --- | 
| schemaType | The type of log record. Always ModelInvocationLog. | 
| schemaVersion | The version of the log schema. | 
| timestamp | The time the invocation was made, in ISO 8601 format. | 
| accountId | The AWS account ID that made the invocation. | 
| region | The AWS Region where the invocation was made. | 
| requestId | The unique identifier for the request. | 
| operation | The API operation called (for example, Converse, InvokeModel). | 
| modelId | The model ID or inference profile ID used for the invocation. | 
| identity.arn | The AWS STS or IAM ARN of the principal that made the request, including the role name and the session or user name. Captured automatically. | 
| requestMetadata | An optional JSON object of key-value tags supplied by the caller. Present only when the caller provides request metadata. For details, see [Per-request metadata tagging](cost-mgmt-request-metadata.md). | 
| input.inputBodyJson | The request body sent to the model (up to 100 KB). Larger bodies are stored as separate objects in Amazon S3. | 
| input.inputTokenCount | The number of input tokens in the request. | 
| output.outputBodyJson | The response body from the model (up to 100 KB). Larger bodies are stored as separate objects in Amazon S3. | 
| output.outputTokenCount | The number of output tokens in the response. | 

**Note**  
Every field in the record is populated by Amazon Bedrock automatically, with one exception: `requestMetadata` is the only field supplied by the caller. For details, see [Per-request metadata tagging](cost-mgmt-request-metadata.md).

To break down token usage by IAM principal without using request metadata, group on `identity.arn`. The following CloudWatch Logs Insights query lists callers by their total input tokens:

```
fields identity.arn as principal,
       input.inputTokenCount as inTokens,
       output.outputTokenCount as outTokens
| stats sum(inTokens) as totalInput,
        sum(outTokens) as totalOutput,
        count() as calls
        by principal
| sort totalInput desc
```

**Note**  
Binary data (such as images) and JSON bodies larger than 100 KB are not included inline in the log entry. Instead, they are stored as separate objects in the Amazon S3 bucket under the data prefix, and the log entry contains a reference to the Amazon S3 location.