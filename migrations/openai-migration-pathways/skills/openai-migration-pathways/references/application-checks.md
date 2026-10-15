# Application checks

Choose checks for the changed workloads and the execution the user authorized. These are evidence levels, not prerequisites for installing the plugin or delivering a partial assessment.

## Exercise the delivered code

For runtime changes, install each service's declared dependencies in a clean, separate environment where permitted. Import the whole entrypoint before testing selected functions. This catches missing dependencies and source-cloud clients imported even when the target path does not use them. Record the installed versions and keep credentials out of the test environment.

Test the application's real process composition. A helper's unit tests, AST-selected functions, or mocked constructors cannot establish that the application starts. For connected services, exercise one representative request from ingress through the actual queue/worker and back to the caller, including authentication, correlation and shutdown. Use the workload's real protocols and separately scoped credentials; do not introduce a different queue merely to make the fixture easier.

External services may use fixtures for local checks. Name those boundaries explicitly. A signed test token can exercise signature verification without proving the customer's identity-provider login. Fixed model replies can exercise orchestration without proving live model access or quality. Do not replace the authentication/authorization decision itself and report authentication as tested.

## Check failures as well as successful output

For workflows with multiple steps, verify that failure of a required step prevents a successful result. Include a failed request after a successful request: default state or old results must not count as completion of the current attempt. Check partial failures, end/empty-state requests, and revoked access where applicable. Error replies must match the public response schema and preserve internal request correlation without exposing provider errors or secrets. Do not automatically replay mutating tool calls.

## Keep claims tied to their evidence

Record the tested commit/patch or artifact digest, command, dependency environment, actual result, and any substitutes. Use `validation.json`'s optional `execution` annotation; for example:

```json
{
  "subject": "application",
  "mode": "local",
  "environment": "isolated local services with synthetic credentials",
  "substitutes": ["identity-provider public-key source", "model transport"]
}
```

Local integration is not an image build or a cloud deployment. A frontend asset build does not establish that its container or backend works. Build and run the selected images on the intended platform when an approved builder is available; otherwise provide portable commands and mark that check not run. No Docker daemon, GitHub runner, privileged installation or publisher machine is required to use the plugin.

Before sharing, apply delivered patches to fresh pinned source and verify the resulting hashes. Run applicable checks from that layout so authoring-machine paths and undeclared dependencies cannot silently supply missing pieces. Keep useful failed checkpoints as historical evidence, not as passing checks for a later revision.
