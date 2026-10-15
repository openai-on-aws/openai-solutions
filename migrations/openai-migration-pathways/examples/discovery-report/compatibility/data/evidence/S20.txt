

# Use interface VPC endpoints (AWS PrivateLink) to create a private connection between your VPC and Amazon Bedrock
<a name="vpc-interface-endpoints"></a>

You can use AWS PrivateLink to create a private connection between your VPC and Amazon Bedrock. You can access Amazon Bedrock as if it were in your VPC, without the use of an internet gateway, NAT device, VPN connection, or Direct Connect connection. Instances in your VPC don't need public IP addresses to access Amazon Bedrock.

You establish this private connection by creating an *interface endpoint*, powered by AWS PrivateLink. We create an endpoint network interface in each subnet that you enable for the interface endpoint. These are requester-managed network interfaces that serve as the entry point for traffic destined for Amazon Bedrock.

For more information, see [Access AWS services through AWS PrivateLink](https://docs.aws.amazon.com/vpc/latest/privatelink/privatelink-access-aws-services.html) in the *AWS PrivateLink Guide*.

## Considerations for Amazon Bedrock VPC endpoints
<a name="vpc-endpoint-considerations"></a>

Before you set up an interface endpoint for Amazon Bedrock, review [Considerations](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html#considerations-interface-endpoints) in the *AWS PrivateLink Guide*.

Amazon Bedrock supports making the following API calls through VPC endpoints.



| Category | Endpoint suffix | 
| --- | --- | 
| [Amazon Bedrock Control Plane API actions](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_Operations_Amazon_Bedrock.html) | bedrock | 
| [Amazon Bedrock Runtime API actions](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_Operations_Amazon_Bedrock_Runtime.html) | bedrock-runtime | 
| Amazon Bedrock Mantle API actions | bedrock-mantle | 
| [Amazon Bedrock Agents Build-time API actions](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_Operations_Agents_for_Amazon_Bedrock.html) | bedrock-agent | 
| [Amazon Bedrock Agents Runtime API actions](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_Operations_Agents_for_Amazon_Bedrock_Runtime.html) | bedrock-agent-runtime | 

**Availability Zones**

Amazon Bedrock and Amazon Bedrock Agents endpoints are available in multiple Availability Zones.

## Create an interface endpoint for Amazon Bedrock
<a name="vpc-endpoint-create"></a>

You can create an interface endpoint for Amazon Bedrock using either the Amazon VPC console or the AWS Command Line Interface (AWS CLI). For more information, see [Create an interface endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html#create-interface-endpoint-aws) in the *AWS PrivateLink Guide*.

Create an interface endpoint for Amazon Bedrock using any of the following service names:
+ `com.amazonaws.{{region}}.bedrock`
+ `com.amazonaws.{{region}}.bedrock-runtime`
+ `com.amazonaws.{{region}}.bedrock-mantle`
+ `com.amazonaws.{{region}}.bedrock-agent`
+ `com.amazonaws.{{region}}.bedrock-agent-runtime`
+ `com.amazonaws.{{region}}.bedrock-fips`
+ `com.amazonaws.{{region}}.bedrock-runtime-fips`

**Note**  
The FIPS endpoint services (`bedrock-fips` and `bedrock-runtime-fips`) are available in us-east-1, us-east-2, us-west-2, ca-central-1, us-gov-east-1, and us-gov-west-1.

After you create the endpoint, you have the option to enable a private DNS hostname. Enable this setting by selecting Enable Private DNS Name in the VPC console when you create the VPC endpoint.

If you enable private DNS for the interface endpoint, you can make API requests to Amazon Bedrock using its default Regional DNS name. The following examples show the format of the default Regional DNS names.
+ `bedrock.{{region}}.amazonaws.com`
+ `bedrock-runtime.{{region}}.amazonaws.com`
+ `bedrock-mantle.{{region}}.api.aws`
+ `bedrock-agent.{{region}}.amazonaws.com`
+ `bedrock-agent-runtime.{{region}}.amazonaws.com`

## Create an endpoint policy for your interface endpoint
<a name="vpc-endpoint-policy"></a>

An endpoint policy is an IAM resource that you can attach to an interface endpoint. The default endpoint policy allows full access to Amazon Bedrock through the interface endpoint. To control the access allowed to Amazon Bedrock from your VPC, attach a custom endpoint policy to the interface endpoint.

An endpoint policy specifies the following information:
+ The principals that can perform actions (AWS accounts, IAM users, and IAM roles).
+ The actions that can be performed.
+ The resources on which the actions can be performed.

For more information, see [Control access to services using endpoint policies](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-access.html) in the *AWS PrivateLink Guide*.

**Example: VPC endpoint policy for Amazon Bedrock actions**  
The following is an example of a custom endpoint policy. When you attach this resource-based policy to your interface endpoint, it grants access to the listed Amazon Bedrock actions for all principals on all resources.

------
#### [ JSON ]

****  

```
{
   "Version":"2012-10-17",		 	 	 
   "Statement": [
      {
         "Principal": "*",
         "Effect": "Allow",
         "Action": [
            "bedrock:InvokeModel",
            "bedrock:InvokeModelWithResponseStream"
         ],
         "Resource":"*"
      }
   ]
}
```

------

**Example: VPC endpoint policy for Amazon Bedrock Mantle actions**  
The following is an example of a custom endpoint policy. When you attach this resource-based policy to your interface endpoint, it grants access to the listed Amazon Bedrock Mantle actions for all principals on all resources.

```
{
   "Version":"2012-10-17",		 	 	 
   "Statement": [
      {
         "Principal": "*",
         "Effect": "Allow",
         "Action": [
            "bedrock-mantle:CreateInference"
         ],
         "Resource":"*"
      }
   ]
}
```

## Connect to Amazon Bedrock through your VPC endpoint
<a name="vpc-connect"></a>

After you create your VPC endpoint, you can route Amazon Bedrock API calls through it. How you do this depends on whether you enabled private DNS for the endpoint.
+ **Private DNS enabled** – No code changes needed. All Amazon Bedrock API calls from within the VPC automatically route through the endpoint using the standard service DNS names (e.g., `bedrock-runtime.{{region}}.amazonaws.com`).
+ **Private DNS not enabled** – You must explicitly specify the VPC endpoint URL in your API calls, as shown in the following examples.

**AWS CLI**

Use the `--endpoint-url` flag to route requests through your VPC endpoint:

```
aws bedrock-runtime invoke-model \
    --model-id anthropic.claude-sonnet-4-6-v1 \
    --body '{"anthropic_version": "bedrock-2023-05-31", "max_tokens": 1024, "messages": [{"role": "user", "content": "Hello"}]}' \
    --cli-binary-format raw-in-base64-out \
    --endpoint-url https://{{vpce-id}}.bedrock-runtime.{{region}}.vpce.amazonaws.com \
    output.json
```

**Python (boto3)**

Pass the `endpoint_url` parameter when creating the client. This approach works for AWS Lambda functions and any application using the AWS SDK:

```
import boto3

client = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1",
    endpoint_url="https://{{vpce-id}}.bedrock-runtime.us-east-1.vpce.amazonaws.com"
)

response = client.converse(
    modelId="anthropic.claude-sonnet-4-6-v1",
    messages=[{"role": "user", "content": [{"text": "Hello"}]}]
)
```

Replace {{vpce-id}} with your VPC endpoint ID (e.g., `vpce-029dea71225152fde`). You can find this ID in the VPC console under **Endpoints**.