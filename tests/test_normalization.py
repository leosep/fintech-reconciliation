from decimal import Decimal
import pytest

from app.services.normalization import normalize_reference, normalize_amount, normalize_date


def test_normalize_reference_removes_dashes_and_spaces():
    assert normalize_reference("TX-001") == "TX001"
    assert normalize_reference(" tx 001 ") == "TX001"
    assert normalize_reference("tx_001") == "TX001"


def test_normalize_amount_handles_currency_symbols_and_commas():
    assert normalize_amount("RD$ 1,500.00") == Decimal("1500.00")
    assert normalize_amount("1500") == Decimal("1500.00")
    assert normalize_amount(1500.5) == Decimal("1500.50")


def test_normalize_amount_rejects_invalid_values():
    with pytest.raises(ValueError):
        normalize_amount(None)
    with pytest.raises(ValueError):
        normalize_amount("abc")


def test_normalize_date_accepts_common_formats():
    assert normalize_date("2026-08-25").year == 2026
    assert normalize_date("25/08/2026").month == 8
