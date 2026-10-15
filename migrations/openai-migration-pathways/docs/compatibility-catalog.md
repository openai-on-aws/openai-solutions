# OpenAI Bedrock compatibility catalog

Release 0.4.0. Evidence reviewed 2026-10-14. Registry SHA-256: `7701d7caa84d06371879651c0827939ac0e7ebd151c4a8c83b6ea1c2d2f9846f`.

Documentation compatibility only. YES does not establish account access or runtime behavior. Evaluate required combinations with evaluate_routes.py. GPT-OSS and Daybreak are excluded.

| Model | AWS context tokens | AWS max output | Sources |
| --- | --- | --- | --- |
| GPT-6 Astra | 1050000 | 128000 | AWS-ASTRA, OAI-GPT-6-ASTRA |
| GPT-6.1 Sol | 1000000 | 131072 | AWS-61-SOL, OAI-GPT-6.1-SOL |
| GPT-6 Sol | 1050000 | 128000 | AWS-6-SOL, OAI-GPT-6-SOL |
| GPT-6 Luna | 1050000 | 128000 | AWS-6-LUNA, OAI-GPT-6-LUNA |
| GPT-5.6 Sol | 1050000 | 128000 | S01, OAI-GPT-5.6-SOL |
| GPT-5.6 Terra | 1050000 | 128000 | S02, OAI-GPT-5.6-TERRA |
| GPT-5.6 Luna | 1050000 | 128000 | S03, OAI-GPT-5.6-LUNA |
| GPT-5.5 | 1050000 | 128000 | AWS-55, OAI-GPT-5.5 |
| GPT-5.4 | 1050000 | 128000 | AWS-54, OAI-GPT-5.4 |

## Exact route definitions

| Model | Endpoint | API | Routing | Partition | Entry Regions | Implicit cache | Explicit cache | Schema | Inline safety |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GPT-6 Astra | bedrock-runtime | responses | us.openai.gpt-6-astra | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | VERIFY | VERIFY | YES | NO |
| GPT-6 Astra | bedrock-runtime | chat_completions | us.openai.gpt-6-astra | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | VERIFY | VERIFY | YES | NO |
| GPT-6 Astra | bedrock-runtime | converse | us.openai.gpt-6-astra | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | VERIFY | VERIFY | YES | YES |
| GPT-6 Astra | bedrock-runtime | responses | global.openai.gpt-6-astra | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-north-1, eu-west-1, eu-west-2, eu-west-3, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-southeast-1, ap-southeast-2, sa-east-1 | VERIFY | VERIFY | YES | NO |
| GPT-6 Astra | bedrock-runtime | chat_completions | global.openai.gpt-6-astra | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-north-1, eu-west-1, eu-west-2, eu-west-3, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-southeast-1, ap-southeast-2, sa-east-1 | VERIFY | VERIFY | YES | NO |
| GPT-6 Astra | bedrock-runtime | converse | global.openai.gpt-6-astra | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-north-1, eu-west-1, eu-west-2, eu-west-3, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-southeast-1, ap-southeast-2, sa-east-1 | VERIFY | VERIFY | YES | YES |
| GPT-6 Astra | bedrock-mantle | responses | openai.gpt-6-astra | aws | us-east-1, us-west-2 | YES | YES | VERIFY | NO |
| GPT-6 Astra | bedrock-mantle | chat_completions | openai.gpt-6-astra | aws | us-east-1, us-west-2 | NO | NO | VERIFY | NO |
| GPT-6.1 Sol | bedrock-runtime | responses | us.openai.gpt-6.1-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | NO |
| GPT-6.1 Sol | bedrock-runtime | chat_completions | us.openai.gpt-6.1-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | YES |
| GPT-6.1 Sol | bedrock-runtime | converse | us.openai.gpt-6.1-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | NO | YES | YES |
| GPT-6.1 Sol | bedrock-runtime | invoke | us.openai.gpt-6.1-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | YES |
| GPT-6.1 Sol | bedrock-runtime | responses | global.openai.gpt-6.1-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | NO |
| GPT-6.1 Sol | bedrock-runtime | chat_completions | global.openai.gpt-6.1-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | YES |
| GPT-6.1 Sol | bedrock-runtime | converse | global.openai.gpt-6.1-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | NO | YES | YES |
| GPT-6.1 Sol | bedrock-runtime | invoke | global.openai.gpt-6.1-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | YES |
| GPT-6.1 Sol | bedrock-mantle | responses | openai.gpt-6.1-sol | aws | us-east-1 | YES | YES | YES | NO |
| GPT-6.1 Sol | bedrock-mantle | chat_completions | openai.gpt-6.1-sol | aws | us-east-1 | YES | YES | YES | NO |
| GPT-6 Sol | bedrock-runtime | responses | us.openai.gpt-6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | YES |
| GPT-6 Sol | bedrock-runtime | chat_completions | us.openai.gpt-6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | YES |
| GPT-6 Sol | bedrock-runtime | converse | us.openai.gpt-6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | NO | YES | YES |
| GPT-6 Sol | bedrock-runtime | invoke | us.openai.gpt-6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | YES |
| GPT-6 Sol | bedrock-runtime | responses | global.openai.gpt-6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, af-south-1, sa-east-1, mx-central-1 | YES | YES | YES | YES |
| GPT-6 Sol | bedrock-runtime | chat_completions | global.openai.gpt-6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, af-south-1, sa-east-1, mx-central-1 | YES | YES | YES | YES |
| GPT-6 Sol | bedrock-runtime | converse | global.openai.gpt-6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, af-south-1, sa-east-1, mx-central-1 | YES | NO | YES | YES |
| GPT-6 Sol | bedrock-runtime | invoke | global.openai.gpt-6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, af-south-1, sa-east-1, mx-central-1 | YES | YES | YES | YES |
| GPT-6 Sol | bedrock-mantle | responses | openai.gpt-6-sol | aws | us-east-1 | YES | YES | YES | NO |
| GPT-6 Sol | bedrock-mantle | chat_completions | openai.gpt-6-sol | aws | us-east-1 | YES | YES | YES | NO |
| GPT-6 Luna | bedrock-runtime | responses | us.openai.gpt-6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | YES |
| GPT-6 Luna | bedrock-runtime | chat_completions | us.openai.gpt-6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | YES |
| GPT-6 Luna | bedrock-runtime | converse | us.openai.gpt-6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | NO | YES | YES |
| GPT-6 Luna | bedrock-runtime | invoke | us.openai.gpt-6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | YES |
| GPT-6 Luna | bedrock-runtime | responses | global.openai.gpt-6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, af-south-1, sa-east-1, mx-central-1 | YES | YES | YES | YES |
| GPT-6 Luna | bedrock-runtime | chat_completions | global.openai.gpt-6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, af-south-1, sa-east-1, mx-central-1 | YES | YES | YES | YES |
| GPT-6 Luna | bedrock-runtime | converse | global.openai.gpt-6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, af-south-1, sa-east-1, mx-central-1 | YES | NO | YES | YES |
| GPT-6 Luna | bedrock-runtime | invoke | global.openai.gpt-6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, af-south-1, sa-east-1, mx-central-1 | YES | YES | YES | YES |
| GPT-6 Luna | bedrock-mantle | responses | openai.gpt-6-luna | aws | us-east-1 | YES | YES | YES | NO |
| GPT-6 Luna | bedrock-mantle | chat_completions | openai.gpt-6-luna | aws | us-east-1 | YES | YES | YES | NO |
| GPT-5.6 Sol | bedrock-runtime | responses | us.openai.gpt-5.6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | NO |
| GPT-5.6 Sol | bedrock-runtime | chat_completions | us.openai.gpt-5.6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | NO | NO | YES | NO |
| GPT-5.6 Sol | bedrock-runtime | converse | us.openai.gpt-5.6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | NO | NO | YES | YES |
| GPT-5.6 Sol | bedrock-runtime | responses | global.openai.gpt-5.6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | YES | YES | YES | NO |
| GPT-5.6 Sol | bedrock-runtime | chat_completions | global.openai.gpt-5.6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | NO | NO | YES | NO |
| GPT-5.6 Sol | bedrock-runtime | converse | global.openai.gpt-5.6-sol | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | NO | NO | YES | YES |
| GPT-5.6 Sol | bedrock-mantle | responses | openai.gpt-5.6-sol | aws | us-east-1, us-east-2 | YES | YES | VERIFY | NO |
| GPT-5.6 Sol | bedrock-mantle | chat_completions | openai.gpt-5.6-sol | aws | us-east-1, us-east-2 | NO | NO | VERIFY | NO |
| GPT-5.6 Terra | bedrock-runtime | responses | us.openai.gpt-5.6-terra | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | NO |
| GPT-5.6 Terra | bedrock-runtime | chat_completions | us.openai.gpt-5.6-terra | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | NO | NO | YES | NO |
| GPT-5.6 Terra | bedrock-runtime | converse | us.openai.gpt-5.6-terra | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | NO | NO | YES | YES |
| GPT-5.6 Terra | bedrock-runtime | responses | global.openai.gpt-5.6-terra | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | YES | YES | YES | NO |
| GPT-5.6 Terra | bedrock-runtime | chat_completions | global.openai.gpt-5.6-terra | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | NO | NO | YES | NO |
| GPT-5.6 Terra | bedrock-runtime | converse | global.openai.gpt-5.6-terra | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | NO | NO | YES | YES |
| GPT-5.6 Terra | bedrock-runtime | responses | in.openai.gpt-5.6-terra | aws | ap-south-1, ap-south-2 | YES | YES | YES | NO |
| GPT-5.6 Terra | bedrock-runtime | chat_completions | in.openai.gpt-5.6-terra | aws | ap-south-1, ap-south-2 | NO | NO | YES | NO |
| GPT-5.6 Terra | bedrock-runtime | converse | in.openai.gpt-5.6-terra | aws | ap-south-1, ap-south-2 | NO | NO | YES | YES |
| GPT-5.6 Terra | bedrock-mantle | responses | openai.gpt-5.6-terra | aws | us-east-1, us-east-2, us-west-2 | YES | YES | VERIFY | NO |
| GPT-5.6 Terra | bedrock-mantle | chat_completions | openai.gpt-5.6-terra | aws | us-east-1, us-east-2, us-west-2 | NO | NO | VERIFY | NO |
| GPT-5.6 Terra | bedrock-mantle | responses | openai.gpt-5.6-terra | aws-us-gov | us-gov-west-1, us-gov-east-1 | YES | YES | VERIFY | NO |
| GPT-5.6 Terra | bedrock-mantle | chat_completions | openai.gpt-5.6-terra | aws-us-gov | us-gov-west-1, us-gov-east-1 | NO | NO | VERIFY | NO |
| GPT-5.6 Luna | bedrock-runtime | responses | us.openai.gpt-5.6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | YES | YES | NO |
| GPT-5.6 Luna | bedrock-runtime | chat_completions | us.openai.gpt-5.6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | NO | NO | YES | NO |
| GPT-5.6 Luna | bedrock-runtime | converse | us.openai.gpt-5.6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | NO | NO | YES | YES |
| GPT-5.6 Luna | bedrock-runtime | responses | global.openai.gpt-5.6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | YES | YES | YES | NO |
| GPT-5.6 Luna | bedrock-runtime | chat_completions | global.openai.gpt-5.6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | NO | NO | YES | NO |
| GPT-5.6 Luna | bedrock-runtime | converse | global.openai.gpt-5.6-luna | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | NO | NO | YES | YES |
| GPT-5.6 Luna | bedrock-runtime | responses | in.openai.gpt-5.6-luna | aws | ap-south-1, ap-south-2 | YES | YES | YES | NO |
| GPT-5.6 Luna | bedrock-runtime | chat_completions | in.openai.gpt-5.6-luna | aws | ap-south-1, ap-south-2 | NO | NO | YES | NO |
| GPT-5.6 Luna | bedrock-runtime | converse | in.openai.gpt-5.6-luna | aws | ap-south-1, ap-south-2 | NO | NO | YES | YES |
| GPT-5.6 Luna | bedrock-mantle | responses | openai.gpt-5.6-luna | aws | us-east-1, us-east-2, us-west-2 | YES | YES | VERIFY | NO |
| GPT-5.6 Luna | bedrock-mantle | chat_completions | openai.gpt-5.6-luna | aws | us-east-1, us-east-2, us-west-2 | NO | NO | VERIFY | NO |
| GPT-5.6 Luna | bedrock-mantle | responses | openai.gpt-5.6-luna | aws-us-gov | us-gov-west-1, us-gov-east-1 | YES | YES | VERIFY | NO |
| GPT-5.6 Luna | bedrock-mantle | chat_completions | openai.gpt-5.6-luna | aws-us-gov | us-gov-west-1, us-gov-east-1 | NO | NO | VERIFY | NO |
| GPT-5.5 | bedrock-runtime | responses | us.openai.gpt-5.5 | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | NO | YES | NO |
| GPT-5.5 | bedrock-runtime | chat_completions | us.openai.gpt-5.5 | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | NO | NO | VERIFY | NO |
| GPT-5.5 | bedrock-runtime | converse | us.openai.gpt-5.5 | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | NO | NO | VERIFY | YES |
| GPT-5.5 | bedrock-runtime | responses | global.openai.gpt-5.5 | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, mx-central-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | YES | NO | YES | NO |
| GPT-5.5 | bedrock-runtime | chat_completions | global.openai.gpt-5.5 | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, mx-central-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | NO | NO | VERIFY | NO |
| GPT-5.5 | bedrock-runtime | converse | global.openai.gpt-5.5 | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, mx-central-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | NO | NO | VERIFY | YES |
| GPT-5.5 | bedrock-mantle | responses | openai.gpt-5.5 | aws | us-east-1, us-east-2 | YES | NO | VERIFY | NO |
| GPT-5.5 | bedrock-mantle | chat_completions | openai.gpt-5.5 | aws | us-east-1, us-east-2 | NO | NO | VERIFY | NO |
| GPT-5.4 | bedrock-runtime | responses | us.openai.gpt-5.4 | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | YES | NO | YES | NO |
| GPT-5.4 | bedrock-runtime | chat_completions | us.openai.gpt-5.4 | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | NO | NO | VERIFY | NO |
| GPT-5.4 | bedrock-runtime | converse | us.openai.gpt-5.4 | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1 | NO | NO | VERIFY | YES |
| GPT-5.4 | bedrock-runtime | responses | global.openai.gpt-5.4 | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, mx-central-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | YES | NO | YES | NO |
| GPT-5.4 | bedrock-runtime | chat_completions | global.openai.gpt-5.4 | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, mx-central-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | NO | NO | VERIFY | NO |
| GPT-5.4 | bedrock-runtime | converse | global.openai.gpt-5.4 | aws | us-east-1, us-east-2, us-west-1, us-west-2, ca-central-1, ca-west-1, mx-central-1, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2, eu-west-3, ap-east-2, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-south-2, ap-southeast-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ap-southeast-5, ap-southeast-6, ap-southeast-7, il-central-1, me-central-1, me-south-1, af-south-1, sa-east-1 | NO | NO | VERIFY | YES |
| GPT-5.4 | bedrock-mantle | responses | openai.gpt-5.4 | aws | us-east-1, us-east-2, us-west-2 | YES | NO | VERIFY | NO |
| GPT-5.4 | bedrock-mantle | chat_completions | openai.gpt-5.4 | aws | us-east-1, us-east-2, us-west-2 | NO | NO | VERIFY | NO |
| GPT-5.4 | bedrock-mantle | responses | openai.gpt-5.4 | aws-us-gov | us-gov-west-1 | YES | NO | VERIFY | NO |
| GPT-5.4 | bedrock-mantle | chat_completions | openai.gpt-5.4 | aws-us-gov | us-gov-west-1 | NO | NO | VERIFY | NO |

## Documentation differences

- GPT-6.1 Sol / limits: Use AWS route limits for Bedrock, preserve OpenAI direct limits separately; confirm exact token accounting before large requests. Sources: AWS-61-SOL, OAI-GPT-6.1-SOL.
- GPT-6 Astra / Mantle Regions: AWS model card is the deployment authority; OpenAI guide lists a narrower older example. Sources: AWS-ASTRA, OAI-BEDROCK.
- GPT-5.4 / GPT-5.5 / context window: AWS model cards list 1,050,000; OpenAI Bedrock guide says 1 million. Check exact accounting for requests approaching the limit. Sources: AWS-54, AWS-55, OAI-BEDROCK.

## Sources

| ID | Scope | Retrieved | Official documentation |
| --- | --- | --- | --- |
| S01 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-56-sol.md |
| S02 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-56-terra.md |
| S03 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-56-luna.md |
| S04 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints.md |
| S05 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/inference-responses-api.md |
| S06 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/inference-chat-completions.md |
| S07 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.md |
| S08 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-converse-api.md |
| S09 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.md |
| S10 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-client-side.md |
| S11 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/web-search.md |
| S12 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/projects.md |
| S13 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.md |
| S14 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.md |
| S15 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.md |
| S16 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.md |
| S17 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-mantle-metrics.md |
| S18 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/logging-cloudtrail-mantle.md |
| S19 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/cost-mgmt-application-inference-profiles.md |
| S20 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/vpc-interface-endpoints.md |
| S21 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/abuse-detection.md |
| AWS-CATALOG | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.md |
| AWS-ASTRA | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-6-astra.md |
| AWS-61-SOL | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-6-1-sol.md |
| AWS-6-SOL | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-6-sol.md |
| AWS-6-LUNA | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-6-luna.md |
| AWS-55 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-55.md |
| AWS-54 | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-54.md |
| OAI-GPT-6-ASTRA | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/models/gpt-6-astra.md |
| OAI-GPT-6.1-SOL | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/models/gpt-6.1-sol.md |
| OAI-GPT-6-SOL | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/models/gpt-6-sol.md |
| OAI-GPT-6-LUNA | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/models/gpt-6-luna.md |
| OAI-GPT-5.6-SOL | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/models/gpt-5.6-sol.md |
| OAI-GPT-5.6-TERRA | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/models/gpt-5.6-terra.md |
| OAI-GPT-5.6-LUNA | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/models/gpt-5.6-luna.md |
| OAI-GPT-5.5 | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/models/gpt-5.5.md |
| OAI-GPT-5.4 | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/models/gpt-5.4.md |
| OAI-CATALOG | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/models.md |
| OAI-BEDROCK | bedrock | 2026-10-14 | https://developers.openai.com/api/docs/guides/amazon-bedrock.md |
| OAI-CACHE | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/guides/prompt-caching.md |
| OAI-SCHEMA | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/guides/structured-outputs.md |
| OAI-TOOLS | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/guides/function-calling.md |
| OAI-DATA | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/guides/your-data.md |
| OAI-DEPRECATIONS | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/deprecations.md |
| OAI-PRICING | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/pricing.md |
| OAI-BACKGROUND | direct_openai | 2026-10-14 | https://developers.openai.com/api/docs/guides/background.md |
| AWS-PRICING | bedrock | 2026-10-14 | https://aws.amazon.com/bedrock/pricing/ |
| AWS-TOOL-USE | bedrock | 2026-10-14 | https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use.md |
