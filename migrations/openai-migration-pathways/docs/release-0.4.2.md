# OpenAI Migration Pathways 0.4.2

Publication candidate prepared October 15, 2026. Authors: Sudeesh and EB Khiyami.

This release packages the existing migration assessment plugin for the OpenAI Solutions on AWS repository. It preserves the approved nine-model catalog and the shared discovery/code report behavior from 0.4.1.

- Adds repository marketplace registration under `openai-solutions`, installation instructions and repository/homepage metadata.
- Adds scoped offline CI and a tag-triggered release workflow that packages a ZIP and checksums after verification.
- The packager accepts an explicit marketplace name and writes a portable ZIP checksum file without overwriting an existing release.
- Adds original-code/documentation license texts and explicit exclusions/notices for third-party provider captures and cloud artwork.
- Includes publication validation and a self-contained fictional discovery example. The existing synthetic code-report tests exercise evaluated and repository-only assessments.

Provider capability claims, evidence dates and the workbook are unchanged from 0.4.1. The catalog remains a dated review, not live account verification. Proposed orchestration is not implemented by an assessment. The deployment portal still lacks profile/Mantle account-availability verification.

See [validation-report.json](validation-report.json) for the recorded checks and [publishing.md](publishing.md) for release and rollback steps. A published GitHub release exists only after maintainers merge, approve third-party inclusion and create the matching tag.
