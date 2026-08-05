---
id: resolve-migration-findings
title: Resolve Migration Findings
summary: Have the architect remediate every blocking decision before approval.
phase: Migration Review
---

Return the findings to the architecture agent for evidence-backed resolution. The canonical decisions must be corrected, explicitly blocked, or left with a visible residual risk before the participant sees an approval request.

- Resolve every blocking and high-severity finding.
- Update canonical JSON decisions when the architecture changes.
- Revalidate both decision schemas after remediation.
- Preserve unresolved risk instead of dismissing it without evidence.

```text
Resolve the independent migration findings and produce the complete migration guide.

Correct affected decisions, document accepted residual risks, and identify any issue that remains blocked. Then produce the complete migration guide covering the source, Azure-to-AWS mapping, selected architecture, Chat Completions-to-Responses changes, model decision, parameter compatibility, remediation, risks, and validation plan.

Show me what changed, how each finding was resolved, the remaining risks, and whether the migration is ready for live model verification.
```

Continue when both canonical decisions validate and no unresolved blocking finding is hidden from the approval step.
