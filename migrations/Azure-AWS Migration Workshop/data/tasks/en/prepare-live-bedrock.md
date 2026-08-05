---
id: prepare-live-bedrock
title: Prepare Live Amazon Bedrock Access
summary: Verify the exact model and Region before the migration contract is approved.
phase: Migration Review
---

Verify the provisional model against the participant's Amazon Bedrock access before approving or generating the target. Availability is an account-and-Region fact, so documentation alone is not sufficient.

- Enter the Amazon Bedrock API key securely in the current terminal.
- Query the regional Models API without printing or storing the key.
- Confirm the exact provisional model and Responses compatibility.
- Update and revalidate the canonical model/API decision.

```text
Help me verify the proposed Amazon Bedrock model and Region before I approve the migration.

Ask me to enter the Amazon Bedrock API key securely in the current terminal. Check the exact proposed model through the regional Models API, confirm its documented Responses compatibility, and update the migration decision with redacted live evidence.

Show me the verified model, Region, and inference endpoint or explain the blocker. Clear the credential from the terminal when the check is complete.
```

Continue when the exact model and Region are observed live, `model-api-decision.json` records an accepted tuple, and the key is no longer present in the terminal environment.
