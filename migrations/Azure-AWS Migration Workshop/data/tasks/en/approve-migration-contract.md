---
id: approve-migration-contract
title: Approve The Migration Contract
summary: Present the resolved contract and wait for the exact migration approval token.
phase: Migration Gate
---

Review the complete migration contract before Codex writes target code. This is a human decision point: approval covers the documented behavior and architecture changes, but it does not authorize AWS deployment.

- Review preserved interfaces, transformations, service mappings, and risks.
- Confirm the target path, architecture, live-verified model tuple, and AgentCore decision.
- Examine validation, rollback, and behavior-preserving remediation.
- Approve only by entering the exact `APPROVE MIGRATION` token.

```text
Present the complete migration contract for my review.

Summarize the behavior being preserved, selected AWS architecture and service mappings, verified Bedrock model and endpoint, Chat Completions-to-Responses changes, implementation work, validation plan, rollback, residual risks, and blockers.

If the contract is complete, ask me to type exactly `APPROVE MIGRATION`. Record my approval against the current contract. This approval authorizes target generation only; it does not authorize AWS deployment.
```

Continue only after `APPROVE MIGRATION` is recorded against the current validated artifact digests.
