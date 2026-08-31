---
title: "The agent loop: a goal, some tools, and a round ceiling"
capabilities: [AGT-01, STR-02]
primary_capability: AGT-01
industry: TRV
industry_scenario: >
  An airline cancels a short-haul flight. Someone has to rebook every affected passenger onto
  the best remaining option while respecting hospital appointments, onward transatlantic
  connections, party sizes and loyalty priority — and seats run out as the work proceeds, so
  each decision changes the options for the next one.
models: [openai.gpt-5.6-terra]
region: us-east-1
apis: [responses]
languages: [python]
dependency_groups: []
iam_actions:
  - bedrock-mantle:CreateInference
level: advanced
estimated_cost: medium
status: validated
last_validated: 2026-08-13
validated_with:
  python: "3.12"
  openai: "2.53.0"
---

# The agent loop: a goal, some tools, and a round ceiling

Tool calling answers a question. An agent is handed a **goal** and decides for itself how
many steps to take, in what order, and when it is finished.

The protocol is identical — `function_call` out, `function_call_output` back — and there is
no framework here on purpose: an agent loop is about thirty lines, and knowing those thirty
lines is what lets you debug the frameworks that wrap them. What an agent adds to a tool call
is three things a question never needs: **a stopping condition, a ceiling, and a record of
what it did**.

Those thirty lines are not our invention. OpenAI documents the same five steps in
[Running agents](https://developers.openai.com/api/docs/guides/agents/running-agents): call the
model, inspect the output, execute any tool calls and continue, switch agents on a handoff, and
return once there is a final answer with no tool work left. What you write below is that loop
with the handoff step left out.

| | |
|:--|:--|
| **What you will learn** | How to write an agent loop from first principles, and the decisions a write tool forces on you |
| **Capability** | The tool loop, hand-rolled |
| **Model** | `openai.gpt-5.6-terra` |
| **Region** | `us-east-1` |
| **Level** | Advanced |
| **Cost** | Medium — the measured run took eight rounds, 15,516 input and 2,046 output tokens |
| **You will need** | Inference permission only, and no agent framework |

> **What it does.** Gives the model a goal — rebook everyone off a cancelled flight — five
> tools including one that writes, and a hard round ceiling, then prints every call it made.
> **What it creates.** Two things: an in-memory dict the write tool mutates, and one stored
> response per round, which the recipe deletes in its clean-up step.

## Who carries the transcript

`store` defaults to `true` on Bedrock, and this recipe uses that default rather than
turning it off. Each round references the previous response by id and sends **only the
new tool results**, so the request stops growing by a full transcript every time:

```python
response = client.responses.create(
    model=MODEL_ID,
    previous_response_id=response.id,   # the rounds before this one
    input=results,                      # only the tool outputs from this round
    tools=TOOLS,
    store=True,
)
```

That is what `store=True` buys: a smaller request and no bookkeeping. What it does **not**
buy is a smaller bill — the model receives the prior context either way, and
[`cookbooks/01-foundations/04-conversation-state/`](../../01-foundations/04-conversation-state/)
measures both patterns to show the input tokens are the same. Choose it for the payload,
not for the cost.

The other side of the default is retention: a stored response is kept by AWS, input and
output, for 30 days. So a recipe that stores owes a clean-up step, and this one deletes
every response it created.

## What makes this a loop rather than a batch

One of the five tools writes. `rebook_passenger` decrements seat availability, so the agent's
own later reads see the consequences of its earlier writes — a passenger rebooked onto the
13:15 takes one of the two remaining seats, and the next passenger genuinely cannot have it.

That feedback is the whole difference. A batch of independent lookups can be parallelised and
retried; a loop whose state changes underneath it has to be sequenced, bounded and observed.

![The agent loop drawn as a cycle. The model decides and returns function_call items, or none; your code executes the tools, which the model never does; the tools read from and write to a shared booking system; the transcript grows by history plus response.output; and the model is called again. A rebook_passenger write takes flight AE420 from two seats to one, so the following get_flight read returns a different answer. The loop ends when no function_call items come back, guarded by while rounds is less than MAX_ROUNDS.](images/agent-loop-cycle.drawio.svg)

*The edge worth following is the one through the shared state. `rebook_passenger` writes, and the
next `get_flight` reads what it wrote — which is why this has to be sequenced rather than fanned
out, and why it needs a ceiling.*

## What you will build

```
A. the tools    four reads and one write, and why the write is different
B. the goal     one instruction, no script
C. the loop     until the agent stops asking, with a hard round limit
D. the trace    every call it made, in order, and what it cost
E. the checks   five questions to answer before a loop runs unsupervised
```

## Prerequisites

- The [prerequisites in the cookbooks README](../../README.md). Inference only —
  `bedrock-mantle:CreateInference`. No extra permissions, no AWS resources, and no agent
  framework: the loop is written out.
- Synthetic data in [`data/disruption.json`](data/disruption.json) — a fabricated flight
  register, four passengers with deliberately conflicting constraints, and a loyalty
  entitlement table. Two passengers cannot both take the one obvious alternative, which is
  the point.

**Cost: medium, from transcript growth rather than call count.** The measured run took all
eight rounds for 15,516 input and 2,046 output tokens, because each round resends the whole
conversation including previous tool calls, results and reasoning items. Output is capped at
1,500 tokens per round. [Rates](https://aws.amazon.com/bedrock/pricing/).

## Run it

```bash
uv sync
uv run python 04-agents/01-the-agent-loop/python/the_agent_loop.py
```

## The loop, in full

```python
while rounds < MAX_ROUNDS:
    rounds += 1
    response = client.responses.create(
        model=MODEL_ID, instructions=INSTRUCTIONS, input=pending,
        tools=TOOLS, max_output_tokens=1500,
        previous_response_id=previous_id,           # the rounds before this one
        store=True,
    )
    STORED.append(response.id)                     # deleted in step F
    calls = [item for item in response.output if item.type == "function_call"]
    if not calls:
        final_answer = response.output_text         # the stopping condition
        break
    history += [run_one(call) for call in calls]    # results, each quoting its call_id
```

Three lines in that are load-bearing:

- **`history += response.output`, unmodified.** On a reasoning model the output includes a
  reasoning item. Filtering it to "just the tool calls" degrades multi-step tool use, and it
  is the most common way a hand-rolled loop gets subtly worse than a framework.
- **The stopping condition is the absence of tool calls**, not a keyword in the text. A model
  that has finished simply answers.
- **`while rounds < MAX_ROUNDS`.** A loop with no ceiling is a way to spend money without a
  plan. Hitting the ceiling is an alert, not something to retry.

## Reads and writes are not the same kind of tool

| | Reads | The write |
| --- | --- | --- |
| Safe to retry | yes | no — a repeat is a second rebooking |
| Safe to run in parallel | yes | no — two calls can each take the last seat |
| Cost of being wrong | a wasted call | a passenger on the wrong flight |

The recipe marks the write in its trace output for exactly this reason. Three design choices
follow, and they are worth copying:

- **Describe the constraint in the tool description.** `rebook_passenger` tells the model to
  check seats first and call it once per passenger. That is enforcement by prompt, which is
  weak — so the function also validates seat availability itself and returns an error.
- **Return errors as data.** `{"error": "AE420 has 2 seat(s), party of 3 needs 3"}` lets the
  agent recover and choose differently. A raised exception ends the run.
- **Validate arguments server-side.** `arguments` is model-generated JSON. For a write, treat
  it as untrusted input.

## What it did

Eight rounds and fifteen tool calls:

```
round 1  get_flight(AE414) · list_affected_passengers(AE414)
round 2  find_alternatives(LIS, DUB) · get_entitlements(gold/silver/standard)
round 3  ✎ rebook_passenger(PX-88120, AE420)   "highest-priority Gold passenger"
round 4  get_flight(AE420) · get_flight(AE431) · get_flight(AE688) · get_flight(AE702)
round 5  ✎ rebook_passenger(PX-88122, AE420)   "only remaining same-day nonstop seat"
round 6  get_flight(AE688) · get_flight(AE702)
round 7  ✎ rebook_passenger(PX-88121, AE688+AE702)  "three seats on both legs"
round 8  the report
```

Read the shape of that: **it assessed, then planned, then wrote, then re-read.** Round 4
re-checks all four flights immediately after its first write — the agent looking at the
consequences of its own action before taking the next one, which is the behaviour the seat
decrement makes necessary.

The allocation it reached:

| Passenger | Tier | Rebooked onto | Why |
| --- | --- | --- | --- |
| PX-88120 | gold | AE420 | Priority 1, and lands before the 18:00 hospital appointment |
| PX-88122 | standard | AE420 | Took the **last** seat — has a 16:10 transatlantic connection |
| PX-88121 | standard | AE688 + AE702 | Party of 3, and AE420 no longer had three seats |
| PX-88123 | silver | **left unbooked** | see below |

Seats afterwards: AE420 **0**, AE688 11, AE702 6, AE431 22.

That is a coherent allocation rather than a plausible one. The two seats on the direct flight
went to the passengers with hard external deadlines, and the party of three was routed via
London precisely because the direct flight could no longer take them.

### The best thing it did was refuse

PX-88123 asked to be rebooked onto **the cheapest** option. The agent left her unbooked and
said why: none of its tools expose fares, so "cheapest" is not a judgement it can make. It
escalated instead of guessing.

That is worth more than the three successful rebookings. An agent that invents a fare, or
quietly picks a flight and calls it cheapest, is the failure mode that makes these systems
untrustworthy — and the behaviour was produced by one clause in the instructions: *if a
passenger cannot be accommodated within their constraints, leave them unbooked and say why*.

### What it cost

Input per round: 398 → 757 → 1,213 → 2,022 → 2,408 → 2,713 → 2,944 → 3,061. **15,516 input
tokens and 2,046 output (1,297 of them reasoning) for fifteen tool calls.**

Note the ratio: input is roughly eight times output, because every round resends the whole
transcript. And note the ceiling — the run finished on round 8 of a maximum of 8. It had no
margin, which is exactly the kind of thing you only learn by printing the round number.

## What to read in the output

The trace is the deliverable, not the final prose. It shows the order the agent worked in —
whether it listed passengers before looking for alternatives, whether it checked entitlements
before prioritising, whether it re-read a flight after committing a seat — and that order is
the thing you cannot see from the answer alone.

Then compare the seat counts printed at the end against the rebookings. Together they answer
the only question that matters about an agent that writes: **did it do something coherent, or
something plausible?**

## Production considerations

- **The cost model is the transcript.** Input grows every round because the whole
  conversation is resent. A twenty-round loop is not twenty times a one-round loop; it is
  worse. Cache the stable instruction prefix, and consider dropping or summarising early
  turns once they stop mattering.
- **Watch what accumulates even with `previous_response_id`.** Referencing the previous round
  keeps your request small, and the model still receives the whole transcript, so input tokens
  climb round on round. That works with tool
  calls, and it removes the transcript from your request payload entirely. It does not
  reduce input tokens, because the model still receives the
  context either way, and it means AWS retains each response for 30 days. Choose it for the
  bookkeeping, not for the bill. See
  [`cookbooks/01-foundations/04-conversation-state/`](../../01-foundations/04-conversation-state/).
- **Set `reasoning.context` deliberately.** On GPT-5.6 it defaults to replaying every earlier
  turn's reasoning, which in a long loop grows superlinearly on top of the transcript growth.
- **Make writes idempotent, or make them approvable.** Either the tool can safely be called
  twice with the same arguments, or a human confirms it. "The model probably won't call it
  twice" is not a design.
- **Bound everything.** Rounds, tokens per round, wall-clock time, and the number of write
  calls a single run may make.
- **Persist the trace.** For anything that acts on the world, the sequence of calls and
  results is the audit record. Printing it is the demonstration; storing it is the
  requirement.
- **Decide what a partial run means.** This loop can rebook two passengers and stop. That
  state has to be safe to leave, or the write needs to be transactional across the whole
  goal — which tools like these usually are not.
- **A framework does not remove these decisions.** The OpenAI Agents SDK and Strands both run
  this loop for you against the same API; the ceiling, the write policy and the trace remain
  yours.

## Data handling and security

- **No credential is handled by the recipe.** The Bedrock provider reads the AWS credential
  chain; nothing is passed, stored or printed.
- **`store=True`, because `previous_response_id` needs it**, so each round's request and
  response are retained for 30 days unless you remove them. The transcript accumulates
  passenger details, so the recipe deletes every response it stored in its clean-up step and
  prints the count.
- **Tool results enter the model's context.** Passenger constraints, including a note about a
  hospital appointment, are sent to the model because the task cannot be done without them.
  In a real system that is a data-minimisation question: return the fields the decision needs
  and no more.
- **The write is in-memory only.** Nothing leaves the process, and no external system is
  touched.
- **Flights, passengers, identifiers and notes are fabricated.**

## Limitations and non-goals

- **No framework comparison.** The same agent expressed through an SDK, and deployed to a
  managed runtime, is the subject of the next recipe in this group.
- **No human approval step.** The write executes as soon as the model asks. A real
  disruption desk would gate it, and the recipe's closing section is about exactly that
  decision.
- **No concurrency.** Parallel tool calls are executed in sequence, because one of the tools
  mutates shared state.
- **No retries or compensation.** A failed write is reported to the agent and not otherwise
  handled; there is no rollback.
- **No evaluation.** Whether the agent's choices were *good* is judged by eye here. Scoring
  agent sessions is a separate capability.
- **One disruption, four passengers.** Enough for the constraints to conflict, not enough to
  characterise reliability.

## Clean up

The loop stores one response per round, so it deletes them in step F and prints how many
went. Nothing else needs tearing down: the write tool mutates an in-memory dictionary that
disappears when the process exits, and on-demand inference creates no resources.

If the script dies part way, the responses it had already created stay until they age out
after 30 days. Re-running is safe — deleting a response that is already gone is a no-op.

## Next steps

- [`cookbooks/02-reasoning-and-output/03-tool-calling/`](../../02-reasoning-and-output/03-tool-calling/)
  — the protocol underneath this loop, including `tool_choice` and parallel calls.
- [`cookbooks/02-reasoning-and-output/04-reasoning-across-turns/`](../../02-reasoning-and-output/04-reasoning-across-turns/)
  — the parameter that decides how much of the agent's earlier thinking is replayed each
  round.
- [`cookbooks/04-agents/02-openai-agents-sdk/`](../02-openai-agents-sdk/) — the same loop, run
  by the OpenAI Agents SDK, and the one setting a Bedrock workload must change.
- [`cookbooks/04-agents/03-strands-agents-sdk/`](../03-strands-agents-sdk/) — the same loop in
  Strands, which reaches mantle a different way.
- [`cookbooks/05-production/01-prompt-caching/`](../../05-production/01-prompt-caching/) — how to
  stop paying full price for the instruction prefix on every round.

## Further reading

- [Running agents](https://developers.openai.com/api/docs/guides/agents/running-agents) — the
  agent loop as OpenAI defines it, plus the four continuation strategies.
- [Function calling](https://developers.openai.com/api/docs/guides/function-calling) — the
  request and response shapes this loop exchanges.
