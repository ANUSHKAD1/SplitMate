from decimal import Decimal

import pytest

from app.schemas.money import paise_to_rupees, parse_rupee_amount, rupees_to_paise


@pytest.mark.parametrize(
    ("value", "expected_rupees", "expected_paise"),
    [
        (250, Decimal("250"), 25_000),
        ("250.50", Decimal("250.50"), 25_050),
        ("0.01", Decimal("0.01"), 1),
    ],
)
def test_parse_and_convert_rupees_exactly(
    value: int | str,
    expected_rupees: Decimal,
    expected_paise: int,
) -> None:
    amount = parse_rupee_amount(value)

    assert amount == expected_rupees
    assert rupees_to_paise(amount) == expected_paise


@pytest.mark.parametrize(
    "value",
    [True, False, 250.50, "NaN", "Infinity", "-Infinity", "1.001", "250.505"],
)
def test_parse_rupee_amount_rejects_unsafe_or_overprecise_values(value: object) -> None:
    with pytest.raises(ValueError):
        parse_rupee_amount(value)


def test_rupees_to_paise_rejects_an_amount_that_cannot_be_exact_paise() -> None:
    with pytest.raises(ValueError):
        rupees_to_paise(Decimal("250.505"))


@pytest.mark.parametrize(
    ("paise", "expected"),
    [
        (25_000, "250.00"),
        (25_050, "250.50"),
        (1, "0.01"),
        (-25_050, "-250.50"),
    ],
)
def test_paise_to_rupees_uses_a_fixed_two_decimal_representation(
    paise: int, expected: str
) -> None:
    assert paise_to_rupees(paise) == expected
