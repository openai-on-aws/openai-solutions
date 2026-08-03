# OpenAI Solutions on AWS

Practical resources for building, migrating, and operating OpenAI-powered applications on
AWS. This repository brings together runnable examples, migration guidance, and
production-oriented architectures for developers, architects, and technical teams.

> This project is under active development.

## What you will find

| Collection | Use it for |
| --- | --- |
| [Cookbooks](cookbooks/) | Runnable, task-focused examples that show how to build a specific capability with OpenAI and AWS. |
| [Migrations](migrations/) | Guides, code, and checklists for moving existing AI workloads to OpenAI on AWS. |
| [Reference architectures](reference-architectures/) | Production-oriented designs that explain components, data flows, operational concerns, and tradeoffs. |

### Choosing the right collection

Add content to **cookbooks** when a reader should be able to follow a focused workflow and
run the result. This includes demos when they teach a reproducible technique rather than
only showcasing a finished application.

Add content to **migrations** when the primary goal is to help readers move an existing
workload, API integration, model workflow, or operating model. Migration content should
make the starting point, target state, transition path, validation plan, and rollback
strategy explicit.

Add content to **reference architectures** when the primary value is a reusable system
design. Reference architectures should emphasize requirements, component responsibilities,
security boundaries, data flows, deployment choices, and production tradeoffs. They may
link to a cookbook for a runnable implementation.

Patterns and templates should remain with the cookbook, migration, or architecture that
uses them. A separate top-level collection can be introduced later when an asset is reused
across multiple independent solutions.

## Repository layout

```text
openai-solutions/
├── cookbooks/
├── migrations/
└── reference-architectures/
```

Each solution should live in its own directory with a README as its entry point. Keep code,
infrastructure definitions, diagrams, sample configuration, and tests close to the content
they support.

## Content expectations

Every contribution should make it clear:

- what problem it solves and who it is for;
- which OpenAI APIs, AWS services, regions, tools, and account permissions it requires;
- how the architecture and data flow work;
- how to configure, deploy, run, validate, and clean up the solution;
- which model, API, runtime, and dependency assumptions it makes;
- how it handles identity, secrets, network access, data privacy, and content safety;
- what readers should consider for reliability, observability, performance, and cost; and
- what limitations, non-goals, and production hardening steps remain.

Examples should be independently testable, avoid embedded credentials or account-specific
values, and provide sample configuration through documented placeholders such as
`.env.example`.

## Getting started

1. Choose the collection that matches your goal.
2. Open the README for the solution you want to use.
3. Review its prerequisites, supported regions, service costs, and security considerations.
4. Follow the setup and validation steps.
5. Run the documented cleanup steps when you are finished.

AWS services used by these solutions may incur charges. Review the relevant AWS and OpenAI
pricing before deployment and remove resources that you no longer need.

## Responsible use

Treat these resources as starting points rather than production guarantees. Evaluate model
behavior with data representative of your use case, apply appropriate safeguards and human
oversight, and review applicable OpenAI policies, AWS service terms, and organizational
requirements before deploying a solution.

## Contributing

Contributions should be focused, documented, and reproducible. For significant additions,
open an issue before implementation so the scope and location can be discussed.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full process and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community expectations.

## Security

Do not commit credentials, API keys, personal data, or sensitive account information. Use
least-privilege permissions and a managed secret store for deployed workloads.

See [security issue notifications](CONTRIBUTING.md#security-issue-notifications) for
information on reporting a potential vulnerability. Do not report security issues through
a public GitHub issue.

## License

This repository is dual-licensed:

- **Code** is licensed under the [MIT No Attribution (MIT-0)](LICENSE) license.
- **Documentation and text content** is licensed under the [Creative Commons Attribution-ShareAlike 4.0 International (CC-BY-SA 4.0)](LICENSE-DOCS.md) license.
