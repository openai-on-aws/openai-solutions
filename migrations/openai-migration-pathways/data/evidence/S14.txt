

# Route model inference requests across AWS Regions with cross-Region inference
<a name="cross-region-inference"></a>

With cross-Region inference, you can choose a cross-Region inference profile tied to a specific geography (such as US or EU), or a global inference profile. When you choose an inference profile tied to a specific geography, Amazon Bedrock automatically selects a commercial AWS Region within that geography to process your inference request. With global inference profiles, Amazon Bedrock automatically selects a commercial AWS Region to process the request.

Both types of cross-Region inference work through [inference profiles](inference-profiles.md), which define a foundation model (FM) and the AWS Regions to which requests can be routed. Cross-Region inference routes your requests by using compute across different AWS Regions.

To increase throughput for a model, you can purchase [Provisioned Throughput](prov-throughput.md). Inference profiles currently don't support Provisioned Throughput.

To see the Regions and models with which you can use inference profiles to run cross-Region inference, refer to [Supported Regions and models for inference profiles](inference-profiles-support.md).

**Topics**
+ [Choosing between Geographic and Global cross-Region inference](#cross-region-inference-comparison)
+ [General considerations](#cross-region-inference-general-considerations)
+ [Geographic cross-Region inference](geographic-cross-region-inference.md)
+ [Global cross-Region inference](global-cross-region-inference.md)

## Choosing between Geographic and Global cross-Region inference
<a name="cross-region-inference-comparison"></a>

Amazon Bedrock provides two types of cross-Region inference profiles, each designed for different use cases and compliance requirements:


| Feature | Geographic Cross-Region Inference | Global Cross-Region Inference | Recommendation | 
| --- | --- | --- | --- | 
| Data residency | Within geographic boundaries (such as US, EU, and APAC) | Any supported AWS commercial Region worldwide | Choose Geographic for compliance requirements | 
| Request routing | Routed within the geography | Routed worldwide | Choose based on where requests can be processed | 
| Cost | Standard pricing | Approximately 10% savings | Choose Global for cost optimization | 
| SCP requirements | Allow all destination Regions in profile | Allow "aws:RequestedRegion": "unspecified" | Configure based on your organizational policies | 
| Best suited for | Organizations with data residency regulations | Organizations prioritizing cost optimization | Assess your compliance and cost needs | 

Choose Geographic cross-Region inference when you have data residency requirements and need to ensure data processing remains within specific geographic boundaries. Choose Global cross-Region inference when you want cost savings without geographic restrictions.

## General considerations
<a name="cross-region-inference-general-considerations"></a>

Note the following information about cross-Region inference:
+ There's no additional routing cost for using cross-Region inference. The price is calculated based on the Region from which you call an inference profile. For information about pricing, see [Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/).
+ Cross-Region inference can route requests to AWS Regions that are not manually enabled in your AWS account. Manual Region enablement is not required for cross-Region inference to function.
+ All data transmitted during cross-Region operations remains on the AWS network and does not traverse the public internet. Data is encrypted in transit between AWS Regions.
+ CloudTrail logs all cross-Region inference requests in your source Region. Look for the `additionalEventData.inferenceRegion` field to identify where requests were processed.
+ AWS Services powered by Amazon Bedrock may also use CRIS. See service-specific documentation for more details.