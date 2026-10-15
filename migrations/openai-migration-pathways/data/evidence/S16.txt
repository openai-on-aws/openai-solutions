

# Get validated JSON results from models
<a name="structured-output"></a>

Structured outputs is a capability on Amazon Bedrock that ensures model responses conform to user-defined JSON schemas and tool definitions, reducing the need for custom parsing and validation mechanisms in production AI deployments.

## Benefits
<a name="structured-output-benefits"></a>

Structured outputs addresses critical challenges in production AI applications:
+ **Ensures schema compliance** – Eliminates error rates and retry loops from prompt-based approaches
+ **Reduced development complexity** – Removes the need for custom parsing and validation logic
+ **Lower operational costs** – Reduces failed requests and retries
+ **Production reliability** – Enables confident deployment of AI applications requiring predictable, machine-readable outputs

## How it works
<a name="structured-output-how-it-works"></a>

Structured outputs constrains model responses to follow a specific schema, ensuring valid, parseable output for downstream processing. You can use structured outputs through two complementary mechanisms:

### JSON Schema output format
<a name="structured-output-json-schema"></a>

For InvokeModel API with Anthropic Claude models, use the `output_config.format` request field. With open weight models, use the `response_format` request field. For Converse APIs, use the `outputConfig.textFormat` request field. The model's response will conform to the specified JSON schema.

### Strict tool use
<a name="structured-output-strict-tool-use"></a>

Add the `strict: true` flag to tool definitions to enable schema validation on tool names and inputs. The model's tool calls will then follow the defined tool input schema.

These mechanisms can be used independently or together in the same request. Refer to [Bedrock API documentation](https://docs.aws.amazon.com/bedrock/latest/APIReference/welcome.html) for more details.

### Request workflow
<a name="structured-output-request-workflow"></a>

The following describes how Amazon Bedrock processes requests with structured outputs:

1. **Initial request** – You include either a JSON schema through the `outputConfig.textFormat`, `output_config.format`, or `response_format` parameter or a tool definition with the `strict: true` flag in your inference request.

1. **Schema validation** – Amazon Bedrock validates the JSON schema format against the supported JSON Schema Draft 2020-12 subset. If the schema contains unsupported features, Amazon Bedrock returns a 400 error immediately.

1. **First-time compilation** – For new schemas, Amazon Bedrock compiles the grammar, which may take up to a few minutes.

1. **Caching** – Successfully compiled grammars are cached for 24 hours from first access. Cached grammars are encrypted with AWS-managed keys.

1. **Subsequent requests** – Identical schemas from the same account use cached grammars, resulting in inference latency comparable to standard requests with minimal overhead.

1. **Response** – You receive standard inference responses with strict schema compliance.

## Supported JSON Schema features
<a name="structured-output-supported-schema-features"></a>

The following JSON Schema Draft 2020-12 features are supported:
+ All basic types: `object`, `array`, `string`, `integer`, `number`, `boolean`, `null`
+ `enum` (strings, numbers, booleans, or nulls only)
+ `const`, `anyOf`, `allOf` (with limitations)
+ `$ref`, `$def`, and `definitions` (internal references only)
+ String formats: `date-time`, `time`, `date`, `duration`, `email`, `hostname`, `uri`, `ipv4`, `ipv6`, `uuid`
+ Array `minItems` (only values 0 and 1)

The following features are *not* supported:
+ Recursive schemas
+ External `$ref` references
+ Numerical constraints (`minimum`, `maximum`, `multipleOf`)
+ String constraints (`minLength`, `maxLength`)
+ `additionalProperties` set to anything other than `false`

## Supported APIs or features
<a name="structured-output-supported-apis"></a>

You can use structured outputs across the following Amazon Bedrock features:


| **API or feature** | **Supported** | **Notes** | 
| --- | --- | --- | 
| [Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html) and [ConverseStream](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseStream.html) APIs | Yes | Conversational inference. | 
| [InvokeModel](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModel.html) and [InvokeModelWithResponseStream](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModelWithResponseStream.html) APIs | Yes | Single-turn inference. | 
| Cross-Region inference | Yes | Works without any additional setup. | 
| Batch inference | Yes | Works without any additional setup. | 
| Anthropic Messages API on the bedrock-mantle endpoint (https://bedrock-mantle.{region}.api.aws/anthropic/v1/messages) | No | The output\_config.format parameter is rejected with a 400 error. To use structured outputs with Anthropic Claude models, send the request through the Converse API or the InvokeModel API on the bedrock-runtime endpoint. | 

**Note**  
Structured outputs is incompatible with citations for Anthropic models. If you enable citations while using structured outputs, the model will return a 400 error.

**Important**  
Some Geographic cross-Region inference profiles don't support structured outputs for every model. For example, structured outputs aren't supported for Claude Haiku 4.5 through the India (`in.anthropic`) inference profile. Check the [model card](model-cards.md) for model-specific limitations.

## Supported models
<a name="structured-output-supported-models"></a>

To see which models support structured outputs, please go to [models at a glance](model-cards.md) and select the model you are interested in.

## Example requests
<a name="structured-output-examples"></a>

### JSON Schema output format
<a name="structured-output-json-schema-examples"></a>

The following examples show how to use JSON Schema output format with structured outputs.

#### Converse API
<a name="json-schema-converse"></a>

##### View example
<a name="w2aac15c15c39c15b3b5b3b1"></a>

```
{
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "text": "Given the following unstructured data, extract it into the provided structure."
        },
        {
          "text": "..."
        }
      ]
    }
  ],
  "outputConfig": {
    "textFormat": {
      "type": "json_schema",
      "structure": {
        "jsonSchema": {
          "schema": "{\"type\": \"object\", \"properties\": {\"title\": {\"type\": \"string\", \"description\": \"title\"}, \"summary\": {\"type\": \"string\", \"description\": \"summary\"}, \"next_steps\": {\"type\": \"string\", \"description\": \"next steps\"}}, \"required\": [\"title\", \"summary\", \"next_steps\"], \"additionalProperties\": false}",
          "name": "data_extraction",
          "description": "Extract structured data from unstructured text"
        }
      }
    }
  }
}
```

#### InvokeModel (Anthropic Claude)
<a name="json-schema-invokemodel-claude"></a>

##### View example
<a name="w2aac15c15c39c15b3b7b3b1"></a>

```
{
  "anthropic_version": "bedrock-2023-05-31",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Given the following unstructured data, extract it into the provided structure."
        },
        {
          "type": "text",
          "text": "..."
        }
      ]
    }
  ],
  "max_tokens": 3000,
  "temperature": 1.0,
  "output_config": {
    "format": {
      "type": "json_schema",
      "schema": {
        "type": "object",
        "properties": {
          "title": {
            "type": "string",
            "description": "title"
          },
          "summary": {
            "type": "string",
            "description": "summary"
          },
          "next_steps": {
            "type": "string",
            "description": "next steps"
          }
        },
        "required": [
          "title",
          "summary",
          "next_steps"
        ],
        "additionalProperties": false
      }
    }
  }
}
```

#### InvokeModel (Open-weight models)
<a name="json-schema-invokemodel-openweight"></a>

##### View example
<a name="w2aac15c15c39c15b3b9b3b1"></a>

```
{
  "messages": [
    {
      "role": "user",
      "content": "Given the following unstructured data, extract it into the provided structure."
    },
    {
      "role": "user",
      "content": "..."
    }
  ],
  "inferenceConfig": {
    "maxTokens": 3000,
    "temperature": 1.0
  },
  "response_format": {
    "json_schema": {
      "name": "summarizer",
      "schema": {
        "type": "object",
        "properties": {
          "title": {
            "type": "string",
            "description": "title"
          },
          "summary": {
            "type": "string",
            "description": "summary"
          },
          "next_steps": {
            "type": "string",
            "description": "next steps"
          }
        },
        "required": [
          "title",
          "summary",
          "next_steps"
        ],
        "additionalProperties": false
      }
    },
    "type": "json_schema"
  }
}
```

### Strict tool use
<a name="structured-output-strict-tool-examples"></a>

The following examples show how to use the strict field with tool use.

#### Converse API
<a name="strict-tool-converse"></a>

##### View example
<a name="w2aac15c15c39c15b5b5b3b1"></a>

```
{
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "text": "What's the weather like in New York?"
        }
      ]
    }
  ],
  "toolConfig": {
    "tools": [
      {
        "toolSpec": {
          "name": "get_weather",
          "description": "Get the current weather for a specified location",
          "strict": true,
          "inputSchema": {
            "json": {
              "type": "object",
              "properties": {
                "location": {
                  "type": "string",
                  "description": "The city and state, e.g. San Francisco, CA"
                },
                "unit": {
                  "type": "string",
                  "enum": [
                    "fahrenheit",
                    "celsius"
                  ],
                  "description": "The temperature unit to use"
                }
              },
              "required": [
                "location",
                "unit"
              ]
            }
          }
        }
      }
    ]
  }
}
```

#### InvokeModel (Anthropic Claude)
<a name="strict-tool-invokemodel-claude"></a>

##### View example
<a name="w2aac15c15c39c15b5b7b3b1"></a>

```
{
  "anthropic_version": "bedrock-2023-05-31",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "What's the weather like in San Francisco?"
        }
      ]
    }
  ],
  "max_tokens": 3000,
  "temperature": 1.0,
  "tools": [
    {
      "name": "get_weather",
      "description": "Get the current weather for a specified location",
      "strict": true,
      "input_schema": {
        "type": "object",
        "properties": {
          "location": {
            "type": "string",
            "description": "The city and state, e.g. San Francisco, CA"
          },
          "unit": {
            "type": "string",
            "enum": [
              "fahrenheit",
              "celsius"
            ],
            "description": "The temperature unit to use"
          }
        },
        "required": [
          "location",
          "unit"
        ],
        "additionalProperties": false
      }
    }
  ]
}
```

#### InvokeModel (Open-weight models)
<a name="strict-tool-invokemodel-openweight"></a>

##### View example
<a name="w2aac15c15c39c15b5b9b3b1"></a>

```
{
  "messages": [
    {
      "role": "user",
      "content": "What's the weather like in San Francisco?"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Get the current weather for a specified location",
        "strict": true,
        "parameters": {
          "type": "object",
          "properties": {
            "location": {
              "type": "string",
              "description": "The city and state, e.g. San Francisco, CA"
            },
            "unit": {
              "type": "string",
              "enum": [
                "fahrenheit",
                "celsius"
              ],
              "description": "The temperature unit to use"
            }
          },
          "required": [
            "location",
            "unit"
          ]
        }
      }
    }
  ],
  "tool_choice": "auto",
  "max_tokens": 2000,
  "temperature": 1.0
}
```