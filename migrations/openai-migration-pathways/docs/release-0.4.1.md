# OpenAI Migration Pathways 0.4.1

Released October 14, 2026. Authors: Sudeesh and EB Khiyami.

Discovery and code assessment now share a nine-section report. All full reports include linked route, gap/blocker, orchestration and Azure-to-AWS service tables. Missing or inapplicable collections require an explanation.

- Section 8 is the central gap and blocker register, with affected routes/services, impact, priority, owner, resolution, acceptance tests and blocked stages.
- Section 5 records existing and proposed orchestration, control flow, state, permissions, failure behavior, semantic changes and tests. Acceptance and implementation/verification are separate. A proposed workaround does not change a native incompatibility to supported.
- Section 6 records Azure source evidence separately from the AWS recommendation. Repository references cannot establish deployed cloud resources.
- Section 2 distinguishes supplied descriptions, repository findings, assumptions, cloud inventory and validation evidence. Nested source artifacts can record independent revision/hash, inspected scope and omissions.
- New code assessments use revision 3 plus `report-contract.json`. The validator binds shared tables to code routes, feature gaps, selected compatibility candidates and, when present, canonical deployment service mappings. Existing revision-1/2 assessments remain readable.
- Saved evaluations are reproduced against pinned requirements and evidence. Current verification separately checks evidence freshness; explicit historical replay is available.
- A fictional discovery report demonstrates a native hosted-file-search gap and an unaccepted application-retrieval proposal. It makes no repository-inspection, implementation or deployment claim.
- Portable and compatibility manifests share one identity/version. Installation instructions and a packaging helper produce a local marketplace folder, ZIP and checksums.

The compatibility registry remains version 0.4.0, reviewed October 14, 2026. This release changes reporting and distribution; it does not add or alter provider capability claims. The approved nine models and the exclusion of GPT-OSS and Daybreak remain unchanged. See [0.4.0 catalog changes](release-0.4.0.md).

See [validation-report.json](validation-report.json) for offline checks. Validators establish consistency of recorded evidence and artifacts; they cannot prove discovery completeness, user approval authenticity, model quality, account availability or application correctness. The deployment portal still needs an account-specific verifier for inference-profile and Mantle routes.
