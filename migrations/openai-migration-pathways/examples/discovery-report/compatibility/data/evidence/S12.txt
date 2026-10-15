

# Projects (OpenAI-compatible)
<a name="projects"></a>

Amazon Bedrock Projects API provides application-level isolation for your generative AI workloads using [OpenAI-compatible APIs](inference-responses-api.md). Projects enable you to organize and manage your AI applications with improved access control, cost tracking, and observability across your organization.

**Tip**  
For new applications, we recommend the `bedrock-runtime` endpoint. If you don't need the Projects API, use [Inference Profiles](inference-profiles-create.md) for isolation, tagging, and cost tracking on `bedrock-runtime`.

**Note**  
Projects can only be used with models that use the OpenAI-compatible APIs against the [bedrock-mantle endpoint](inference-responses-api.md). If you are using the bedrock-runtime endpoint, please use Inference Profiles instead of tagging and observability.

## What is a Project?
<a name="projects-what-is"></a>

A Project is a logical boundary used to isolate workloads such as applications, environments, or experiments within Amazon Bedrock. Projects provide:
+ **Access isolation**: Control who can access specific project resources using [IAM policies for Amazon Bedrock Projects](security-iam-projects.md)
+ **Cost monitoring**: Track spending at the project level using [AWS tags](https://docs.aws.amazon.com/whitepapers/latest/tagging-best-practices/what-are-tags.html) and [AWS Cost Explorer](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-what-is.html)

Projects allow you to manage multiple generative AI workloads in production without creating separate AWS accounts or organizations, reducing operational complexity while maintaining security and governance.

Each AWS account has a default project where all inference requests are associated with. You can create more projects in your account using the Projects API.

**Note**  
Support for Projects differs by endpoint. On the `bedrock-mantle` endpoint, you can create and manage your own projects with the Projects API. On the `bedrock-runtime` endpoint, only the default project is available — you can't create projects there yet. Requests to `bedrock-runtime` resolve to your account's default project, whose ARN is `arn:aws:bedrock:{{region}}:{{account-id}}:project/default`. The default project can't be tagged or deleted, its data retention setting always inherits from the account, and it is never the billing anchor: usage on `bedrock-runtime` is attributed to the inference target, exactly as it is today. For the permissions that reference the default project, see [Prerequisites for running model inference](inference-prereq.md).

## When to Use Projects
<a name="projects-when-to-use"></a>

You should use the Projects API when you need to:
+ **Organize by business structure**: Manage Bedrock usage based on your organizational taxonomy such as business units, teams, applications, or cost centers
+ **Track costs accurately**: Monitor and allocate AI spending to specific teams, projects, or environments
+ **Enforce access policies**: Apply granular IAM permissions to control who can access specific AI workloads
+ **Scale production workloads**: Run multiple production applications with clear operational boundaries and monitoring

## Projects vs. Inference Profiles
<a name="projects-vs-inference-profiles"></a>

Both Projects API and [Inference Profiles](inference-profiles-create.md) provide isolation, tagging, and access control capabilities in Amazon Bedrock, but they differ based on the endpoint you use. If you're using OpenAI-compatible APIs with the [bedrock-mantle](endpoints.md) endpoint, use the Projects API. If you're using the [bedrock-runtime](endpoints.md) endpoint (recommended for new applications), use Inference Profiles. The Chat Completions API is available on both endpoints; the Projects API is only available on `bedrock-mantle`.


| Feature | Projects API | Inference Profiles | 
| --- | --- | --- | 
| Supported APIs | OpenAI-compatible APIs (Responses, Chat Completions) | Native Bedrock APIs (Invoke, Converse), OpenAI-compatible API (Chat Completions) | 
| Endpoint | bedrock-mantle.{region}.api.aws | bedrock-runtime.{region}.amazonaws.com | 
| Use Case | Applications using OpenAI-compatible endpoints | Applications using native Bedrock APIs | 
| Access Control | Project as a resource in IAM policies | IAM policies on inference profile ARN | 
| Cost Tracking | AWS tags on projects | AWS tags on inference profiles | 

## Projects vs. AWS accounts
<a name="projects-vs-aws-accounts"></a>

[AWS Accounts](https://docs.aws.amazon.com/accounts/latest/reference/accounts-welcome.html) and [AWS Organizations](https://docs.aws.amazon.com/controltower/latest/userguide/organizations.html) represent billing and ownership boundaries at the infrastructure level. Projects represent workload and application boundaries within a single account.

Using Projects instead of separate AWS accounts provides:
+ **Faster setup**: Create projects in seconds through API calls.
+ **Reduced complexity**: Manage multiple workloads without account sprawl
+ **Simplified operations**: Centralized management within a single account
+ **Lower overhead**: No need for cross-account IAM roles or resource sharing

## Getting started with Projects
<a name="projects-getting-started"></a>

This page walks you through creating your first project, associating it with inference requests, and managing project resources.

### Prerequisites
<a name="projects-prerequisites"></a>

Before you begin, make sure you have:
+ An AWS account with Amazon Bedrock access
+ IAM permissions to create and manage Bedrock projects
+ Python 3.7 or later installed
+ The OpenAI Python SDK installed: `pip install openai boto3`
+ An [API key](api-keys.md) for Amazon Bedrock authentication

### Step 1: Set Up Your Environment
<a name="projects-setup-environment"></a>

Configure your environment variables with your Amazon Bedrock credentials:

```
export OPENAI_API_KEY="<your-bedrock-key>"
export OPENAI_BASE_URL="https://bedrock-mantle.<your-region>.api.aws/v1"
```

Replace `<your-region>` with your AWS region (e.g., us-east-1, us-west-2).

**Note**  
Amazon Bedrock offers [two types of keys](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-how.html): short-term and long-term. While you can use long-term API keys for exploration of Amazon Bedrock, we recommend short-term keys for applications with greater security requirements. If you use long-term keys with Projects, note that the default policy attached to long term keys only allows you to get and list projects, but not create/update/archive them. If you would like your long-term key to manage projects, then you will have to assign additional IAM policies to your keys to enable these operations.

### Step 2: Discover Available Models
<a name="projects-discover-models"></a>

Use the `list()` API to retrieve a list of models compatible with the Projects API:

```
curl -X GET $OPENAI_BASE_URL/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Step 3: Create Your First Project
<a name="projects-create-first"></a>

Create a project using the Create Project API with tags for cost monitoring and observability. Note that at this time only cURL is supported in the SDK.

```
curl -X POST $OPENAI_BASE_URL/organization/projects \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Project ABC",
    "tags": {
      "Project": "CustomerChatbot",
      "Environment": "Production",
      "Owner": "TeamAlpha",
      "CostCenter": "21524"
    }
  }' -v
```

Response:

```
{
  "arn": "arn:aws:bedrock-mantle:ap-northeast-1:673693429514:project/proj_5d5ykleja6cwpirysbb7",
  "created_at": 1772135628,
  "id": "proj_5d5ykleja6cwpirysbb7",
  "name": "Project ABC",
  "object": "organization.project",
  "status": "active",
  "tags": {
    "Owner": "TeamAlpha",
    "Project": "CustomerChatbot",
    "Environment": "Production",
    "CostCenter": "21524"
  }
}
```

**Important Notes:**
+ The geography parameter in the OpenAI API specification is ignored by Amazon Bedrock.
+ The region is determined by your endpoint configuration.
+ The arn field is specific to Amazon Bedrock and provides the ARN for IAM policy attachment.
+ Tags can be specified during project creation and are returned in all project responses.

### Step 4: Associate Inference Requests with Your Project
<a name="projects-associate-inference"></a>

To associate your project for inference requests, provide the project ID when creating the client:

------
#### [ cURL ]

```
curl -X POST $OPENAI_BASE_URL/responses \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -H "OpenAI-Project: proj_5d5ykleja6cwpirysbb7" \
  -d '{
    "model": "openai.gpt-oss-120b",
    "input": "Explain the benefits of using projects in Amazon Bedrock"
  }'
```

------
#### [ Python ]

```
from openai import OpenAI
client = OpenAI(project="proj_5d5ykleja6cwpirysbb7")
```

------

All inference requests made with this client will be associated with the specified project, ensuring proper isolation, cost tracking, and access control.

### Step 5: Verify Your Project Setup
<a name="projects-verify-setup"></a>

List all projects to verify your project was created successfully:

```
curl -X GET $OPENAI_BASE_URL/organization/projects \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

Response:

```
{
  "data": [
    {
      "arn": "arn:aws:bedrock-mantle:ap-northeast-1:673693429514:project/default",
      "created_at": 1764460800,
      "id": "default",
      "name": "default",
      "object": "organization.project",
      "status": "active",
      "tags": {}
    },
    {
      "arn": "arn:aws:bedrock-mantle:ap-northeast-1:673693429514:project/proj_2z766pfxmkij5vwubv75",
      "created_at": 1771823259,
      "id": "proj_2z766pfxmkij5vwubv75",
      "name": "Project ABC",
      "object": "organization.project",
      "status": "active",
      "tags": {}
    }
  ],
  "first_id": "default",
  "has_more": false,
  "last_id": "proj_znaruqn723npmjqnxqfd",
  "object": "list"
}
```

### Next Steps
<a name="projects-next-steps"></a>

Now that you've created your first project, you can:
+ **Configure access control**: Attach IAM policies to restrict project access
+ **Set up cost tracking**: Add AWS tags for cost allocation
+ **Enable monitoring**: Configure CloudWatch metrics and alarms
+ **Create additional projects**: Organize workloads by team, environment, or application

## Working with Projects
<a name="projects-working-with"></a>

This page provides detailed information about managing projects throughout their lifecycle.

### Creating Projects
<a name="projects-creating"></a>

#### Basic Project Creation
<a name="projects-basic-creation"></a>

Create a project with a name, description, and tags:

```
curl -X POST $OPENAI_BASE_URL/organization/projects \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Development Environment",
    "tags": {
      "Project": "InternalTools",
      "Environment": "Development",
      "Owner": "TeamAlpha",
      "CostCenter": "30156"
    }
  }'
```

You can have up to 1000 projects per account.

#### Recommended Naming Conventions
<a name="projects-naming-conventions"></a>

Use clear, descriptive names that reflect your organizational structure:
+ **By application**: CustomerChatbot-Prod, InternalSearch-Dev
+ **By team**: TeamAlpha-Production, DataScience-Experiments
+ **By environment**: Production-WebApp, Staging-MobileApp
+ **By cost center**: CostCenter-2152-Production

### Listing Projects
<a name="projects-listing"></a>

#### List All Projects
<a name="projects-list-all"></a>

Retrieve all projects in your account:

```
curl -X GET $OPENAI_BASE_URL/organization/projects \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Retrieving Project Details
<a name="projects-retrieving-details"></a>

Get detailed information about a specific project:

```
curl -X GET $OPENAI_BASE_URL/organization/projects/proj_5d5ykleja6cwpirysbb7 \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Updating Projects
<a name="projects-updating"></a>

Modify project properties such as name:

```
curl -X POST $OPENAI_BASE_URL/organization/projects/proj_5d5ykleja6cwpirysbb7 \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Chatbot v2"
  }'
```

### Managing Project Tags
<a name="projects-managing-tags"></a>

Add new tags or update existing tag values:

```
curl -X POST $OPENAI_BASE_URL/organization/projects/proj_5d5ykleja6cwpirysbb7 \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "add_tags": {
      "Application": "WebApp",
      "Version": "2.0",
      "Team": "Engineering"
    }
  }'
```

Remove specific tags by their keys:

```
curl -X POST $OPENAI_BASE_URL/organization/projects/proj_5d5ykleja6cwpirysbb7 \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "remove_tag_keys": ["Version", "OldTagKey"]
  }'
```

**Important Notes**  
**No full replacement**: There is no operation to replace the entire tag set at once. You must explicitly specify which tags to add and which to remove.
**Error handling**: Implement proper error handling and verification

### Archiving Projects
<a name="projects-archiving"></a>

Archive projects that are no longer in use:

```
curl -X POST $OPENAI_BASE_URL/organization/projects/proj_abc123/archive \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json"
```

**Important**  
Archived projects cannot be used for new inference requests, but historical data and metrics remain accessible for up to 30 days.

### Using Projects with Different APIs
<a name="projects-using-apis"></a>

------
#### [ Responses API ]

```
from openai import OpenAI

client = OpenAI(project="proj_abc123")

response = client.responses.create(
    model="openai.gpt-oss-120b",
    input="What are the key features of Amazon Bedrock?"
)
print(response)
```

------
#### [ Chat Completions API ]

```
from openai import OpenAI

client = OpenAI(project="proj_abc123")

response = client.chat.completions.create(
    model="openai.gpt-oss-120b",
    messages=[
        {"role": "user", "content": "Explain how projects improve security"}
    ]
)

print(response.choices[0].message.content)
```

------

### Best Practices
<a name="projects-best-practices"></a>

#### Recommended Project Structure
<a name="projects-recommended-structure"></a>

**One project per application**: Create separate projects for each distinct application or service.

```
├── CustomerChatbot-Production
├── CustomerChatbot-Staging
├── CustomerChatbot-Development
├── InternalSearch-Production
└── InternalSearch-Development
```
+ **Separate environments**: Use different projects for development, staging, and production environments.
+ **Experiment isolation**: Create dedicated projects for experiments and proof-of-concepts.

#### Project Lifecycle Management
<a name="projects-lifecycle-management"></a>
+ **Create projects early**: Set up projects before deploying applications
+ **Use consistent naming**: Follow organizational naming conventions
+ **Document project purpose**: Include clear descriptions
+ **Regular audits**: Periodically review and archive unused projects
+ **Monitor usage**: Track project metrics to identify optimization opportunities