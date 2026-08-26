"""Lossless conversion helpers for the public rupee API boundary."""

from decimal import Decimal, InvalidOperation


PAISE_PER_RUPEE = Decimal("100")


def parse_rupee_amount(value: object) -> Decimal:
    """Parse an integer or decimal string without accepting binary floats."""
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("Money amounts must be decimal strings or integers, never floats")
    if not isinstance(value, (str, int, Decimal)):
        raise ValueError("Money amounts must be decimal strings or integers")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise ValueError("Money amounts must be valid decimal rupee values") from error
    if not amount.is_finite():
        raise ValueError("Money amounts must be finite")
    if amount.as_tuple().exponent < -2:
        raise ValueError("Money amounts may have at most 2 decimal places")
    return amount


def rupees_to_paise(amount: Decimal) -> int:
    """Convert a validated rupee Decimal to its exact integer-paise value."""
    paise = amount * PAISE_PER_RUPEE
    if not paise.is_finite() or paise != paise.to_integral_value():
        raise ValueError("Rupee amount cannot be represented exactly in paise")
    return int(paise)


def paise_to_rupees(amount: int) -> str:
    """Render an integer-paise amount as a fixed two-decimal rupee string."""
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise ValueError("Paise amounts must be integers")
    sign = "-" if amount < 0 else ""
    absolute_amount = abs(amount)
    return f"{sign}{absolute_amount // 100}.{absolute_amount % 100:02d}"
