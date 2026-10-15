

# Amazon Bedrock abuse detection
<a name="abuse-detection"></a>

You are responsible for your (and your end users') data input into, and content generated using, Amazon Bedrock. As part of providing the Service, Amazon Bedrock may use automated abuse detection mechanisms to detect activity that violates our, or third-party model providers', terms of service or use policies. In certain limited circumstances described below, we may also store or review model inputs or outputs. Amazon Bedrock uses a zero operator access (ZOA) data security model, subject to the model-specific abuse and CSAM detection detailed below.

## Model-specific abuse detection
<a name="abuse-detection-model-specific"></a>

For abuse detection purposes related to the following models, we will store inputs and outputs as follows:
+ For all OpenAI models other than GPT OSS Safeguard 120B, GPT OSS Safeguard 20B, gpt-oss-120b, and gpt-oss-20b, classifier-flagged traffic will be retained for up to 30 days for automated offline abuse detection. Eligible customers may request full ZDR through their AWS account team.
+ For Anthropic Claude Fable 5 and Claude Fable 5.1, all traffic will be retained for up to 30 days for automated offline abuse detection. Classifier-flagged traffic will be subject to potential human review performed by AWS.
  + Customers that are eligible for the Enterprise Frontier Safeguards program will receive ZDR through December 31, 2026. After ZDR ends, all traffic will be retained for up to 30 days for automated offline abuse detection. The Enterprise Frontier Safeguards program plans to enable customer-managed encryption keys and bring your own bucket for storage for automated offline abuse detection.

Retained inputs and outputs are stored and processed by AWS and are not shared with third-party model providers. For more information on data retention and related controls, see [Data retention](data-retention.md). If cross-region inference is enabled for these models, retained inputs and outputs are stored in destination regions (i.e., the region where your inference request is processed).

## Child sexual abuse material ("CSAM")
<a name="abuse-detection-csam"></a>

To help stop the dissemination of child sexual abuse material ("CSAM"), Amazon Bedrock uses automated abuse detection mechanisms to detect apparent CSAM. If Amazon Bedrock detects apparent CSAM in your image inputs or outputs, Amazon Bedrock may block the request and return a `ValidationException` (HTTP 400) error in the API response. Amazon Bedrock may store and review the flagged input or output exclusively to determine if it is CSAM and may also file a report with the National Center for Missing and Exploited Children (NCMEC) or a relevant authority. You might be required by applicable laws to take additional actions, and you are responsible for those actions.

## General information
<a name="abuse-detection-general"></a>

If an abuse detection mechanism identifies potential violations, we may request information about your use of Amazon Bedrock and compliance with relevant terms and policies. These requests are sent to the email address associated with your AWS account, so ensure that your account contact information is current and monitored. AWS may suspend your access to any model or Amazon Bedrock if you fail to comply with applicable terms or policies or are non-responsive.

Contact your AWS account team or AWS Support if you have additional questions.