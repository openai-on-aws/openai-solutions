"""Small helpers shared across recipes, for work that is incidental to every lesson.

**What belongs here is deliberately narrow.** A recipe is read more often than it is
run, so anything a reader came to see stays written out in the recipe: the client
construction, the API call, the model ID, a guardrail's policy configuration, the token
counts it prints. Hiding those behind an import answers a different question.

What belongs here is the opposite — work that appears in several recipes, teaches
nothing the second time, and makes the surrounding code harder to read:

- **Masking account identifiers** before printing an ARN. Three recipes need it, and
  none of them are about string substitution.
- **Deleting responses a recipe stored.** Every recipe using `store=True` owes a
  clean-up step, and a `try`/`except` delete loop in each is noise around the point.

The test has two parts, and the first one is absolute: **the helper must be incidental
to the lesson of every recipe that uses it.** Then either it appears in three or more
recipes, or it serves a convention every recipe of its kind must follow — which is why
the delete helper is here with one caller today rather than three.

The distinction is visible in the two recipes that delete a stored response.
`02-reasoning-and-output/04-reasoning-across-turns` stores two turns to demonstrate
`previous_response_id` and then tidies up, so deleting is incidental and it calls this
helper. `01-foundations/04-conversation-state` **teaches** the delete — it is a numbered
step that confirms the response is gone afterwards — so it writes the call out in full.
Same operation, opposite decision, decided by whether the reader came to see it.
"""

from __future__ import annotations

import re
from typing import Any

from openai import NotFoundError

__all__ = ["mask_account_ids", "delete_stored_responses"]

# A 12-digit run is an AWS account id. Matching on length is crude and correct here:
# recipes print ARNs and role names, and nothing else in that output is 12 digits.
_ACCOUNT_ID = re.compile(r"\b\d{12}\b")


def mask_account_ids(text: Any, placeholder: str = "<account>") -> str:
    """Replace AWS account identifiers in text so output is safe to share.

    Recipes print ARNs — a project, a Lambda function, an execution role — and an ARN
    carries the account id. That makes otherwise-useful output awkward to paste into a
    ticket, a design document or a screenshot, so every recipe that prints one masks it
    first. The twelve-digit run becomes `<account>`, and the rest of the identifier is
    left alone so it stays recognisable.
    """
    return _ACCOUNT_ID.sub(placeholder, str(text))


def delete_stored_responses(client: Any, *response_ids: str) -> list[str]:
    """Delete responses a recipe stored, and report which ones went.

    `store=True` is the Bedrock default and the thing that makes `previous_response_id`
    work, so recipes use it where a later turn refers back. What they should not do is
    leave the stored responses behind for their 30-day retention window — nor carry the
    same defensive delete loop in every script.

    A response that is already gone is the outcome we wanted, so `NotFoundError` is
    skipped. **Everything else raises**, and that is deliberate: this is a clean-up
    helper, so the failure it must never hide is the one where nothing was cleaned up.
    Expired credentials or a throttled call would otherwise return an empty list, the
    caller would print "deleted 0", and a reader would believe the recipe tidied up
    while the responses sat out their retention window.

    Returns the ids that were deleted, so the caller can print an honest count.
    """
    deleted = []
    for response_id in response_ids:
        if not response_id:
            continue
        try:
            client.responses.delete(response_id)
        except NotFoundError:
            continue
        deleted.append(response_id)
    return deleted
