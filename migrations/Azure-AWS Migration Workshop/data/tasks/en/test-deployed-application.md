---
id: test-deployed-application
title: Test The Deployed Application
summary: Validate deployed parity, health, persistence, and the intended inference path.
phase: AWS Validation
---

Test the deployed application through its public interface and compare it with both the source baseline and the validated local target. Deployment is not complete until application behavior, persistence, inference, and operational evidence agree.

- Exercise representative APIs and browser workflows against the deployed URL.
- Validate health, persistence, errors, and the selected Bedrock model.
- Confirm the intended direct Bedrock or conditional AgentCore path.
- Correlate application behavior with redacted CloudWatch evidence.

```text
Test the deployed application through its public endpoint.

Repeat representative API and browser workflows from the source and local target baselines. Verify health, persistence where applicable, expected errors, the exact selected model, absence of fallback, and the approved direct Bedrock or AgentCore inference path. Correlate the result with redacted operational evidence.

Show me the end-to-end acceptance result, observed differences, operational findings, and any issue that should be resolved before teardown.
```

Continue when the deployed application passes its acceptance contract and operational evidence confirms the intended inference path.
