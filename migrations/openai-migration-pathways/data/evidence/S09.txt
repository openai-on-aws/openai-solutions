

# Use the ApplyGuardrail API in your application
<a name="guardrails-use-independent-api"></a>

Guardrails is used to implement safeguards for your generative AI applications that are customized for your use cases and aligned with your responsible AI policies. Guardrails allows you to configure denied topics, filter harmful content, and remove sensitive information. 

You can use the `ApplyGuardrail` API to assess any text using your pre-configured Amazon Bedrock Guardrails, without invoking the foundation models. 

Features of the `ApplyGuardrail` API include:
+ **Content validation** – You can send any text input or output to the `ApplyGuardrail` API to compare it with your defined topic avoidance rules, content filters, PII detectors, and word block lists. You can evaluate user inputs and FM generated outputs independently.
+ **Flexible deployment** – You can integrate the `ApplyGuardrail` API anywhere in your application flow to validate data before processing or serving results to the user. For example, if you are using a RAG application, you can now evaluate the user input before performing the retrieval, instead of waiting until the final response generation.
+ **Decoupled from foundation models** – `ApplyGuardrail` API is decoupled from foundational models. You can now use Guardrails without invoking Foundation Models. You can use the assessment results to design the experience on your generative AI application.

**Topics**
+ [Call ApplyGuardrail in your application flow](#guardrails-use-independent-api-call)
+ [Specify the guardrail to use with ApplyGuardrail](#guardrails-use-indepedent-api-call-configure)
+ [Example use cases of ApplyGuardrail](#guardrails-use-independent-api-call-message)
+ [Return full output in ApplyGuardrail response](#guardrails-use-return-full-assessment)

## Call ApplyGuardrail in your application flow
<a name="guardrails-use-independent-api-call"></a>

The request allows customer to pass all their content that should be guarded using their defined Guardrails. The source field should be set to `INPUT` when the content to evaluated is from a user (typically the input prompt to the LLM). The source should be set to `OUTPUT` when the model output guardrails should be enforced (typically the LLM response). 

## Specify the guardrail to use with ApplyGuardrail
<a name="guardrails-use-indepedent-api-call-configure"></a>

When using `ApplyGuardrail`, you specify the `{{guardrailIdentifier}}` and `{{guardrailVersion}}` of the guardrail that you want to use. You can also enable tracing for the guardrail, which provides information about the content that the guardrail blocks.

------
#### [ ApplyGuardrail API request ]

```
POST /guardrail/{{{guardrailIdentifier}}}/version/{{{guardrailVersion}}}/apply HTTP/1.1
{
    "source": "INPUT" | "OUTPUT",
    "content": [{
        "text": {
            "text": "string",
        }
    }, ]
}
```

------
#### [ ApplyGuardrail API response ]

```
{
    "usage": { 
          "topicPolicyUnits": "integer",
          "contentPolicyUnits": "integer",
          "wordPolicyUnits": "integer",
          "sensitiveInformationPolicyUnits": "integer",
          "sensitiveInformationPolicyFreeUnits": "integer",
          "contextualGroundingPolicyUnits": "integer"
     },
    "action": "GUARDRAIL_INTERVENED" | "NONE",
    "output": [
            // if guardrail intervened and output is masked we return request in same format
            // with masking
            // if guardrail intervened and blocked, output is a single text with canned message
            // if guardrail did not intervene, output is empty array
            {
                "text": "string",
            },
    ],
    "assessments": [{
        "topicPolicy": {
                "topics": [{
                    "name": "string",
                    "type": "DENY",
                    "action": "BLOCKED",
                }]
            },
            "contentPolicy": {
                "filters": [{
                    "type": "INSULTS | HATE | SEXUAL | VIOLENCE | MISCONDUCT |PROMPT_ATTACK",
                    "confidence": "NONE" | "LOW" | "MEDIUM" | "HIGH",
                    "filterStrength": "NONE" | "LOW" | "MEDIUM" | "HIGH",
                "action": "BLOCKED"
                }]
            },
            "wordPolicy": {
                "customWords": [{
                    "match": "string",
                    "action": "BLOCKED"
                }],
                "managedWordLists": [{
                    "match": "string",
                    "type": "PROFANITY",
                    "action": "BLOCKED"
                }]
            },
            "sensitiveInformationPolicy": {
                "piiEntities": [{
                    // for all types see: bedrock/latest/APIReference/API_GuardrailPiiEntityConfig.html#bedrock-Type-GuardrailPiiEntityConfig-type
                    "type": "ADDRESS" | "AGE" | ...,
                    "match": "string",
                    "action": "BLOCKED" | "ANONYMIZED"
                }],
                "regexes": [{
                    "name": "string",
                    "regex": "string",
                    "match": "string",
                    "action": "BLOCKED" | "ANONYMIZED"
                }],
            "contextualGroundingPolicy": {
                 "filters": [{
                   "type": "GROUNDING | RELEVANCE",
                   "threshold": "double",
                   "score": "double",
                   "action": "BLOCKED | NONE"
                 }]
            },
            "invocationMetrics": {
                "guardrailProcessingLatency": "integer",
                "usage": {
                    "topicPolicyUnits": "integer",
                    "contentPolicyUnits": "integer",
                    "wordPolicyUnits": "integer",
                    "sensitiveInformationPolicyUnits": "integer",
                    "sensitiveInformationPolicyFreeUnits": "integer",
                    "contextualGroundingPolicyUnits": "integer"
                },
                "guardrailCoverage": {
                    "textCharacters": {
                        "guarded":"integer",
                        "total": "integer"
                    }
                }
            }
        },
        "guardrailCoverage": {
            "textCharacters": {
                "guarded": "integer",
                "total": "integer"
            }
        }
    ]
}
```

------

## Example use cases of ApplyGuardrail
<a name="guardrails-use-independent-api-call-message"></a>

The outputs of the `ApplyGuardrail` request depends on the action guardrail took on the passed content.
+ If guardrail intervened where the content is only masked, the exact content is returned with masking applied.
+ If guardrail intervened and blocked the request content, the outputs field will be a single text, which is the canned message based on guardrail configuration.
+ If no guardrail action was taken on the request content, the outputs array is empty.

------
#### [ Guardrails takes no action ]

**Request example**

```
{
    "source": "OUTPUT",
    "content": [
        "text": {
            "text": "Hi, my name is Zaid. Which car brand is reliable?"
        }
    ]
}
```

**Response example**

```
{
    "usage": {
        "topicPolicyUnitsProcessed": 1,
        "contentPolicyUnitsProcessed": 1,
        "wordPolicyUnitsProcessed": 0,
        "sensitiveInformationPolicyFreeUnits": 0
    },
    "action": "NONE",
    "outputs": [],
    "assessments": [{}]
}
```

------
#### [ Guardrails blocks content ]

**Response example**

```
{
    "usage": {
        "topicPolicyUnitsProcessed": 1,
        "contentPolicyUnitsProcessed": 1,
        "wordPolicyUnitsProcessed": 0,
        "sensitiveInformationPolicyFreeUnits": 0
    },
    "action": "GUARDRAIL_INTERVENED",
    "outputs": [{
        "text": "Configured guardrail canned message (i.e., can't respond)"
    }],
    "assessments": [{
        "topicPolicy": {
            "topics": [{
                "name": "Cars",
                "type": "DENY",
                "action": "BLOCKED"
            }]
        },
        "sensitiveInformationPolicy": {
            "piiEntities": [{
                "type": "NAME",
                "match": "ZAID",
                "action": "ANONYMIZED"
            }],
            "regexes": []
        }
    }]
}
```

------
#### [ Guardrails masks content ]

**Response example**

Guardrails intervenes by masking the name `ZAID`.

```
{
    "usage": {
        "topicPolicyUnitsProcessed": 1,
        "contentPolicyUnitsProcessed": 1,
        "wordPolicyUnitsProcessed": 0,
        "sensitiveInformationPolicyFreeUnits": 0
    },
    "action": "GUARDRAIL_INTERVENED",
    "outputs": [{
            "text": "Hi, my name is {NAME}. Which car brand is reliable?"
        },
        {
            "text": "Hello {NAME}, ABC Cars are reliable ..."
        }
    ],
    "assessments": [{
        "sensitiveInformationPolicy": {
            "piiEntities": [{
                "type": "NAME",
                "match": "ZAID",
                "action": "ANONYMIZED"
            }],
            "regexes": []
        }
    }]
}
```

------
#### [ AWS CLI example ]

**Input example**

```
aws bedrock-runtime apply-guardrail \
    --cli-input-json '{
        "guardrailIdentifier": "someGuardrailId",
        "guardrailVersion": "DRAFT",
        "source": "INPUT",
        "content": [
            {
                "text": {
                    "text": "How should I invest for my retirement? I want to be able to generate $5,000 a month"
                }
            }
        ]
    }' \
    --region us-east-1 \
    --output json
```

**Output example (blocks content)**

```
{
    "usage": {
        "topicPolicyUnits": 1,
        "contentPolicyUnits": 1,
        "wordPolicyUnits": 1,
        "sensitiveInformationPolicyUnits": 1,
        "sensitiveInformationPolicyFreeUnits": 0
    },
    "action": "GUARDRAIL_INTERVENED",
    "outputs": [
        {
            "text": "I apologize, but I am not able to provide fiduciary advice. ="
        }
    ],
    "assessments": [
        {
            "topicPolicy": {
                "topics": [
                    {
                        "name": "Fiduciary Advice",
                        "type": "DENY",
                        "action": "BLOCKED"
                    }
                ]
            }
        }
    ]
}
```

------

## Return full output in ApplyGuardrail response
<a name="guardrails-use-return-full-assessment"></a>

Content is considered detected if it breaches your guardrail configurations. For example, contextual grounding is considered detected if the grounding or relevance score is less than the corresponding threshold.

By default, the [ApplyGuardrail](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ApplyGuardrail.html) operation only returns detected content in a response. You can specify the `outputScope` field with the `FULL` value to return the full output. In this case, the response will also include non-detected entries for enhanced debugging.

You can configure this same behavior in the `Invoke` and `Converse` operations by setting trace to the enabled full option.

**Note**  
The full output scope doesn't apply to word filters or regex in sensitive information filters. It does apply to all other filtering policies, including sensitive information with filters that can detect personally identifiable information (PII).