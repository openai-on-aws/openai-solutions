---
title: Authenticating with a Bedrock API key
capabilities: [FND-02]
primary_capability: FND-02
industry: —
industry_scenario: >
  Cross-industry. A platform team standardizes how services authenticate to
  Bedrock and needs to know when a Bedrock API key is the right choice, what its
  lifetime is, and how it interacts with the IAM credentials already on the host.
models: [openai.gpt-5.6-luna]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: [foundations]
iam_actions:
  - bedrock-mantle:CreateInference
  - bedrock-mantle:CallWithBearerToken
level: beginner
estimated_cost: low
status: validated
last_validated: 2026-08-13
validated_with:
  python: "3.12"
  openai: "2.53.0"
  aws-bedrock-token-generator: "1.1.0"
---

# Authenticating with a Bedrock API key

Every other recipe here signs its requests with SigV4 and never touches a credential. This
one takes the other supported path — a **Bedrock API key** carried in
`AWS_BEARER_TOKEN_BEDROCK` — and walks its whole lifecycle, because a key is the right answer
in a few specific situations and you will meet it in AWS's own examples either way.

| | |
|:--|:--|
| **What you will learn** | When a Bedrock API key is the right credential, what one contains, and how it interacts with the IAM credentials already on your host |
| **Capability** | Bearer-token authentication on `bedrock-mantle` |
| **Model** | `openai.gpt-5.6-luna` |
| **Region** | `us-east-1` |
| **Level** | Beginner |
| **Cost** | Low — four calls capped at 16 output tokens each, well under a cent |
| **You will need** | Working AWS credentials, since the key is derived from them |

> **What it does.** Mints a short-term key from your own IAM identity, prints its non-secret
> properties, authenticates with it two different ways, then shows how the key interacts with
> SigV4 when both are available. **What it creates.** A short-lived key held only in the
> process environment, and the environment is restored on exit even if the run fails.

## When a key is the right choice

Reach for the credential chain first. On EC2, ECS, EKS or Lambda an instance or task role
gives you rotating credentials with nothing to store, expire or leak, and that is what the
rest of this cookbook uses.

A Bedrock API key earns its place when the caller cannot sign with SigV4 — a third-party tool
that only accepts an OpenAI-style `api_key`, a notebook on a machine you do not administer, or
a quick shared sandbox. It is also what
[OpenAI's Bedrock guide](https://developers.openai.com/api/docs/guides/amazon-bedrock) and
most AWS blog posts use in their examples, so if you arrived from either, this is the path you
already have configured.

## What you will build

The script walks the lifecycle end to end in a single run:

```
credential chain (baseline)   ->  200
    mint a short-term key     ->  inspect its non-secret properties
    authenticate with it      ->  200   (via the environment, and via api_key=)
    let it go stale           ->  401 invalid_api_key
    fall back to SigV4        ->  200   (api_key=None, and placement matters)
    restore the environment   ->  nothing left behind
```

## Prerequisites

- **The [prerequisites in the cookbooks README](../../README.md)** — a Region with model
  access and IAM permission for inference on `bedrock-mantle`.
- **Working AWS credentials**, because the key is minted from them. Run
  `aws sts get-caller-identity` first.
- **The `foundations` dependency group**, which adds
  [`aws-bedrock-token-generator`](https://pypi.org/project/aws-bedrock-token-generator/).

## Run it

```bash
uv sync --group foundations
uv run --group foundations python \
  01-foundations/03-bedrock-api-key-auth/python/bedrock_api_key_auth.py
```

## Two ways to get a key

| | Bedrock console | `provide_token()` |
| --- | --- | --- |
| Produces | Long-term or short-term keys | Short-term only |
| Lifetime | Short-term keys expire; a long-term key does not expire on its own | 12 hours by default, and `expiry=` overrides it |
| Needs | A person in the console | Whatever credentials the process already holds |
| Suits | A quickstart, a demo, a shared sandbox | A script, CI, anything unattended |

This recipe uses `provide_token` because it needs no console step, and because deriving the
key from your existing credentials makes the relationship between the two mechanisms
concrete: **a key is not a separate identity.** It is a signed, time-limited assertion of the
identity you already had, so it grants exactly what that identity grants and nothing more. See
[Amazon Bedrock API keys](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html).

## What a key actually contains

A key is a base64-encoded pre-signed URL, which is why it is long and why you can read its
properties without holding the signing secret. With `aws-bedrock-token-generator 1.1.0`:

| Property | Value |
| --- | --- |
| Prefix | `bedrock-api-key-` |
| Action | `CallWithBearerToken` |
| Algorithm | `AWS4-HMAC-SHA256` |
| Requested expiry | 43,200 seconds — 12 hours, the generator's default |
| Credential scope | `<date>/<region>/bedrock/aws4_request` |

Two things follow from that table, and both are useful.

**The 12 hours belong to the generator, not to Bedrock.** `provide_token` takes an `expiry`
argument, so you can ask for less. Note that this is the expiry *requested* in the signed URL;
whether the service caps it lower is not something this recipe tests.

**`CallWithBearerToken` is a real IAM action.** Because bearer-token authentication is
authorized by `bedrock-mantle:CallWithBearerToken`, an administrator can allow or deny this
entire path, and can distinguish short-term keys from long-term ones using the
`bedrock-mantle:BearerTokenType` condition key. That is a useful lever: you can permit
short-term keys in CI while refusing long-term ones everywhere.

The script prints these properties and **never prints the key itself**.

## How a key and SigV4 coexist

When a key is present in the environment, the provider uses it. That is deliberate and it is
the behaviour you want — setting the variable is an explicit statement of which credential to
use, and a library that silently preferred something else would be harder to reason about.

The whole rule fits in three rows, and it holds whatever else is on the host:

| `AWS_BEARER_TOKEN_BEDROCK` | `api_key=None` inside `bedrock(...)` | Credential used |
|:--|:--|:--|
| Set | No | The bearer token from the environment |
| Set | Yes | SigV4, because the environment lookup is suppressed |
| Unset | Either | SigV4 from the credential chain |

It is worth seeing the precedence once, though, because the symptom of a *stale* key is
easy to misread:

| Call | Result |
| --- | --- |
| `bedrock(region=r)` with a stale key in the environment | `401 invalid_api_key` |
| `OpenAI(provider=bedrock(region=r), api_key=None)` | `401` — the provider already resolved the variable |
| `OpenAI(provider=bedrock(region=r, api_key=None))` | `200` — the lookup is suppressed, so SigV4 applies |

**The placement of `api_key=None` is what matters.** At the top level the client sees it too
late, because the provider resolves the environment variable itself. Inside `bedrock(...)` it
suppresses that lookup, and you fall back to SigV4.

You will rarely need that form. The everyday fix is `unset AWS_BEARER_TOKEN_BEDROCK`. Where
`api_key=None` inside `bedrock(...)` does earn its place is in a library that must guarantee
SigV4 regardless of the environment it is dropped into.

## Clean up: restoring the environment

A key in the environment applies to every later call in the same process or shell, so a script
that sets one and exits without tidying up changes the behaviour of the *next* thing you run.
This script restores the previous state in a `finally` block, so it happens even when the run
fails halfway, and it puts back any pre-existing value rather than blindly deleting:

```python
previous = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
try:
    main()
finally:
    if previous is None:
        os.environ.pop("AWS_BEARER_TOKEN_BEDROCK", None)
    else:
        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = previous
```

That covers the script's own process. If you exported the variable in your shell, run
`unset AWS_BEARER_TOKEN_BEDROCK` there too.

## Production considerations

- **Prefer the credential chain wherever you can sign with SigV4.** A role gives you rotating
  credentials and nothing to manage; reach for a key when the caller genuinely cannot.
- **Never keep a key at rest in your application.** If you must persist one, put it in AWS
  Secrets Manager or Parameter Store and store its expiry alongside it — a short-term key
  outlives its usefulness quickly, and a long-term key does not expire on its own.
- **Re-mint rather than refresh.** `provide_token` returns a cached key while it is still
  valid, so calling it before each request is cheap and keeps expiry handling out of your code.
- **Use the `BearerTokenType` condition key** if you want to allow short-term keys and refuse
  long-term ones. It is the cleanest way to express that policy.
- **Long-term keys are more restricted than they look.** Their default policy permits only get
  and list on Projects, not create, update or archive.
- **Quotas behave identically either way.** A `429` is a tokens-per-minute quota, and the
  SDK's `max_retries` already backs off.

## Data handling and security

- **The key is never printed, written to a file, or committed.** The script shows only its
  non-secret properties — prefix, action, algorithm, expiry and scope.
- **The key carries your existing IAM identity**, so it grants nothing you did not already
  have.
- **It is short-lived and held only in the process environment**, never at rest.
- **The environment is restored on exit**, including when the run fails, so no credential is
  left for the next process to pick up.
- **`store=False` on every call**, so AWS retains neither request nor response.

## Limitations and non-goals

- **It does not walk the Bedrock console.** Creating a key in the UI is documented by AWS
  better than we could here.
- **It covers long-term keys only in passing**, noting their restricted default policy and
  that they do not expire on their own. Everything said about lifetime applies to the
  short-term key this recipe mints.
- **It does not test expiry enforcement.** The properties table reports what the signed URL
  requests, not what the service does as a key ages out.
- **It does not cover PrivateLink or VPC endpoint policies**, which are orthogonal to how you
  authenticate.
- **A key's internal format is undocumented.** The properties table is an observation on one
  version, useful for understanding what a key *is*; do not build anything that parses it.

## Next steps

- [`cookbooks/01-foundations/01-first-call/`](../01-first-call/) — the Responses API and the permissions that
  authorize a call. Read that one first if you have not; this recipe is the detour.
- [`cookbooks/01-foundations/04-conversation-state/`](../04-conversation-state/) — the next decision after
  authentication, and the one with a retention consequence.
