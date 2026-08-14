# Larkspur Retail — returns policy (extract for support agents)

Effective 2026-01-01. Applies to all consumer orders placed on larkspur.example.com.

## R1. Standard return window

Non-faulty items may be returned for a full refund within **30 days of delivery**.

## R2. Electronics

Electronics have a shorter window: **14 days of delivery**.

- Returned **unopened** (factory seal intact): full refund.
- Returned **opened**: **store credit only**, never a cash refund.

## R3. Final sale items

Items marked **final sale** at the point of purchase **cannot be returned** and are not
eligible for refund or store credit.

## R4. Faulty items

An item that is faulty, damaged on arrival, or not as described may be returned for a
**full refund within 12 months (365 days) of delivery**.

**R4 overrides R2 and R3.** A faulty item is refunded in full even if it is electronics
that has been opened, and even if it was a final sale item. Beyond 365 days, no return.

## R5. Gift purchases

Where an order is flagged as a gift and a **gift date** is recorded, the return window
runs from the **gift date** rather than the delivery date. The length of the window is
unchanged — the item's own category window applies.

## R6. Loyalty tiers

**Gold** members receive **15 additional days** on any return window under R1, R2 or R5.
The extension does **not** apply to final sale items (R3) and is unnecessary under R4.

## R7. Heavy items

Items over **20 kg** must be collected by our carrier and cannot be dropped off. This is a
logistics requirement and **has no effect on eligibility** — record
`collection_required: true` on the return.

## R8. Missing packaging

A non-faulty return without its original packaging attracts a **20% restocking fee**,
deducted from the refund or store credit. Faulty returns under R4 are never charged a
restocking fee.

## Outcomes

Every request resolves to exactly one of:

- `refund` — money back to the original payment method
- `store_credit` — credit to the customer's account
- `reject` — no return accepted

Where two rules could apply, the more specific one governs, and R4 governs over all others.
