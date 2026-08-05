---
id: select-source-application
title: Confirm The Source Application
summary: Confirm the bundled Azure AI Shopping Cart and document its as-is Azure architecture.
phase: Workspace Setup
---

Use the Azure AI Shopping Cart included in the starter workspace as the source application for this workshop.

- Confirm the source root is `apps/azure-ai-shopping-cart-app`.
- Inspect its documentation, build manifests, backend, and frontend entry points.
- Identify the application components Codex will examine in later tasks.
- Generate an evidence-backed source architecture diagram using Azure fundamentals.
- Leave the source application unchanged.

```text
Do not invoke a custom agent. Inspect apps/azure-ai-shopping-cart-app in the current starter workspace.

Read its repository documentation, backend and frontend build manifests, runtime entry points, and infrastructure files. Confirm that it contains the Azure OpenAI application used by this workshop and identify its major components.

Create /tmp/workshop-artifacts/source-architecture.md with a professional Mermaid diagram of the documented as-is architecture. Show the user/browser, React frontend, Spring Boot API on Azure Spring Apps, Azure OpenAI Chat Completions, and Azure Database for PostgreSQL Flexible Server, including the observed HTTP, API, JDBC, and inference flows and clear Azure/application boundaries.

Add an evidence table that maps every diagram component and connection to inspected source files. Document the local workshop substitutions—H2 and mock AI—separately from the deployed Azure architecture. Do not invent Azure services for networking, identity, secrets, or observability; label those areas as unknown when the repository has no evidence.

Report the confirmed workspace-relative source root and open the generated architecture Markdown for review. Do not create /tmp/workshop-artifacts/migration-context.json and do not modify source code.
```

Continue when `apps/azure-ai-shopping-cart-app` is confirmed, `/tmp/workshop-artifacts/source-architecture.md` is ready for review, and no source files have been changed.
