"""Unit tests for scoring_cache's encode/decode round-trip — pure functions,
no Redis. Decimal/date must survive JSON round-tripping exactly.
"""

from datetime import date
from decimal import Decimal

from soteria.analysis.models.scoring import TransactionFeatures
from soteria.analysis.scoring_cache import _decode_features, _encode_features


def _round_trip(features: TransactionFeatures) -> TransactionFeatures:
    return _decode_features(_encode_features(features))


def test_round_trips_positive_amount_exactly() -> None:
    original = TransactionFeatures(
        amount=Decimal("19.99"),
        transaction_date=date(2026, 7, 25),
        normalized_merchant="Cafe A",
        normalized_category="Food",
    )

    result = _round_trip(original)

    assert result == original
    assert isinstance(result.amount, Decimal)
    assert result.amount == Decimal("19.99")


def test_round_trips_negative_amount_exactly() -> None:
    original = TransactionFeatures(
        amount=Decimal("-42.50"),
        transaction_date=date(2026, 1, 1),
        normalized_merchant="Some Store",
        normalized_category="Shopping",
    )

    result = _round_trip(original)

    assert result == original
    assert result.amount == Decimal("-42.50")


def test_round_trip_never_coerces_to_float() -> None:
    # 0.1 + 0.2 != 0.3 in float -- a real Decimal-precision canary.
    original = TransactionFeatures(
        amount=Decimal("0.10") + Decimal("0.20"),
        transaction_date=date(2026, 3, 15),
        normalized_merchant="Precision Test",
        normalized_category="Other",
    )

    result = _round_trip(original)

    assert result.amount == Decimal("0.30")
    assert not isinstance(result.amount, float)


def test_round_trips_date() -> None:
    original = TransactionFeatures(
        amount=Decimal("5.00"),
        transaction_date=date(2025, 12, 31),
        normalized_merchant="Merchant",
        normalized_category="Category",
    )

    result = _round_trip(original)

    assert result.transaction_date == date(2025, 12, 31)
    assert isinstance(result.transaction_date, date)
