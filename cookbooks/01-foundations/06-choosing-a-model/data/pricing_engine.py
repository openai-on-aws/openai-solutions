"""Larkspur Retail basket pricing — synthetic reference implementation.

This module is the *subject* of a task, not part of the recipe's machinery. The recipe
shows this source to a model, asks it for the exact total of a basket in cents, and
scores the answer against what this code actually returns. The code is therefore the
oracle: nobody has to adjudicate the right answer.

It is deliberately full of the kind of ordering and rounding decisions a real pricing
engine accumulates, each of which is individually reasonable and jointly hard to
simulate in your head.
"""


def line_total_cents(unit_price_cents: int, quantity: int, percent_off: int) -> int:
    """Percentage discount on the line, then rounded half-up to the nearest cent."""
    gross = unit_price_cents * quantity
    discounted = gross * (100 - percent_off) / 100
    return int(discounted + 0.5)


def multibuy_credit_cents(
    unit_price_cents: int, quantity: int, percent_off: int
) -> int:
    """Every third unit of a multibuy line is free.

    The credit is computed from the *discounted* unit price, rounded half-up, and only
    applies to lines flagged multibuy.
    """
    free_units = quantity // 3
    discounted_unit = unit_price_cents * (100 - percent_off) / 100
    return int(discounted_unit * free_units + 0.5)


def basket_total_cents(basket: dict) -> int:
    """Total payable, in cents.

    Order of operations, which is where the interesting cases live:

    1. Line totals, each rounded to the nearest cent.
    2. Multibuy credits subtracted.
    3. Free shipping is decided on the subtotal *before* any voucher is applied.
    4. The voucher is applied to the subtotal, and cannot take it below zero.
    5. Shipping is added last, so a voucher never buys free shipping.
    """
    subtotal = 0
    for line in basket["lines"]:
        percent_off = line.get("percent_off", 0)
        subtotal += line_total_cents(
            line["unit_price_cents"], line["quantity"], percent_off
        )
        if line.get("multibuy"):
            subtotal -= multibuy_credit_cents(
                line["unit_price_cents"], line["quantity"], percent_off
            )

    shipping = 0 if subtotal >= basket["free_shipping_threshold_cents"] else basket[
        "shipping_cents"
    ]

    voucher = basket.get("voucher_cents", 0)
    subtotal = max(subtotal - voucher, 0)

    return subtotal + shipping
