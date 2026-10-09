"""Validated odds input models."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OddsRow:
    event: str
    market: str
    selection: str
    odds: float
    commission: float = 0.0
    source: str = "unknown"
    available: float | None = None
    timestamp: str | None = None

    @classmethod
    def from_mapping(cls, row: dict[str, Any]) -> "OddsRow":
        required = ("event", "market", "selection", "odds")
        missing = [key for key in required if key not in row]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        odds = float(row["odds"])
        commission = float(row.get("commission", 0.0))
        available = row.get("available")
        available = None if available in (None, "") else float(available)
        if odds <= 1:
            raise ValueError("Decimal odds must be greater than 1.0")
        if not 0 <= commission < 1:
            raise ValueError("commission must be >= 0 and < 1")
        if available is not None and available < 0:
            raise ValueError("available stake must not be negative")
        return cls(
            event=str(row["event"]).strip(),
            market=str(row["market"]).strip(),
            selection=str(row["selection"]).strip(),
            odds=odds,
            commission=commission,
            source=str(row.get("source", "unknown")),
            available=available,
            timestamp=row.get("timestamp"),
        )
