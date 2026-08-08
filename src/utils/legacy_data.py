"""Compatibility helpers for retired persisted fields."""

from typing import Any

RETIRED_WEALTH_KEYS = {
    "wealth",
    "wealth_ledger",
    "_active_wealth_transaction_id",
}


def strip_retired_wealth_keys(value: Any) -> Any:
    """Return a recursive copy without exact retired wealth-system keys."""
    if isinstance(value, dict):
        return {
            key: strip_retired_wealth_keys(nested)
            for key, nested in value.items()
            if key not in RETIRED_WEALTH_KEYS
        }
    if isinstance(value, list):
        return [strip_retired_wealth_keys(nested) for nested in value]
    if isinstance(value, tuple):
        return tuple(strip_retired_wealth_keys(nested) for nested in value)
    return value
