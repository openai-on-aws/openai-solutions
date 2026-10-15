

# Application inference profiles
<a name="cost-mgmt-application-inference-profiles"></a>

Application inference profiles (AIPs) let you attribute Amazon Bedrock costs by application, team, or workload for the Amazon Bedrock [InvokeModel](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModel.html) and [Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html) APIs on the `bedrock-runtime` endpoint. Each AIP is model-specific and carries cost allocation tags that flow to AWS Cost Explorer and AWS Cost and Usage Reports (both classic CUR and CUR 2.0).

For workloads using Responses and Chat Completions on the `bedrock-mantle` endpoint, use [Projects](cost-mgmt-projects.md) instead.

**Important**  
Application inference profiles aren't supported by the Responses and Chat Completions APIs, on either endpoint. A request to those APIs that names an application inference profile as its inference target is rejected with a 400 error. Use an AIP with the [InvokeModel](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModel.html) and [Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html) APIs, and attribute Responses and Chat Completions usage with [IAM principal attribution](cost-mgmt-iam-principal-tracking.md) or [Per-request metadata tagging](cost-mgmt-request-metadata.md) instead. System, geographic, and global inference profiles work normally with all of these APIs.

## How cost attribution works
<a name="cost-mgmt-aip-how-it-works"></a>

An application inference profile is a resource that references a specific Amazon Bedrock model. You create the profile, attach cost allocation tags, and then use the profile ARN in place of the model ID in your API calls. The profile's tags are attached to the billing record for each request.

The following example shows how to use an application inference profile ARN instead of a model ID when calling the Converse API:

```
import boto3

client = boto3.client("bedrock-runtime")

response = client.converse(
    modelId="arn:aws:bedrock:us-east-1:123456789012:inference-profile/my-team-profile",
    messages=[
        {"role": "user", "content": [{"text": "Hello"}]}
    ]
)
```

For more information on creating profiles, see [Create an application inference profile](inference-profiles-create.md).

**Note**  
Application inference profiles deliver aggregated billed dollars to AWS Cost Explorer and CUR (classic CUR and CUR 2.0). The finest grain is per usage type per day; they do not produce per-request cost. For per-prompt token detail, use [Per-request metadata tagging](cost-mgmt-request-metadata.md) with your [model invocation logs](model-invocation-logging.md).

## Viewing profile costs
<a name="cost-mgmt-aip-viewing-costs"></a>

After creating and tagging your profiles, activate the tags as cost allocation tags in the AWS Billing and Cost Management console:

1. Open the AWS Billing and Cost Management console.

1. In the navigation pane, choose **Cost allocation tags**.

1. Select the tags you applied to your profiles.

1. Choose **Activate**.

Tags can take up to 24 hours to appear in Cost Explorer and CUR after activation. Cost allocation tags are not retroactive. Only costs incurred after activation are tagged. For more information, see [Activating user-defined cost allocation tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/activating-tags.html).

After tag activation, you can analyze Amazon Bedrock costs by application inference profile in the following tools:
+ **AWS Cost Explorer** – Filter by profile tags to view cost trends over time. Group by tag to compare costs across profiles.
+ **AWS Cost and Usage Reports** – Query CUR data for line-item cost breakdowns by profile tag. Tags appear in both classic CUR and CUR 2.0 exports.

## Scaling considerations
<a name="cost-mgmt-aip-scaling"></a>

Each application inference profile is tied to a specific model. This means you need a separate profile for every unique combination of model, team, and tag set. As organizations grow, profile count can increase quickly, especially when new model versions require new profiles.

To reduce profile proliferation:
+ **Recommended:** Use [Projects](cost-mgmt-projects.md) for flexibility and ease when cost tracking.
+ Tag at the team or cost center level rather than per-user.
+ For per-user cost attribution without creating additional profiles, use [IAM principal attribution](cost-mgmt-iam-principal-tracking.md). IAM principal tracking works alongside application inference profiles and attributes costs at the identity level automatically.
+ For per-prompt token detail rather than aggregated dollars, use [Per-request metadata tagging](cost-mgmt-request-metadata.md) with your [model invocation logs](model-invocation-logging.md). It needs no per-model resources.