"""Surebet and Back/Lay calculations, with explicit fee assumptions."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Iterable

from .models import OddsRow


@dataclass(frozen=True)
class SurebetLeg:
    selection: str
    source: str
    odds: float
    commission: float
    stake: float
    available: float | None
    effective_odds: float


@dataclass(frozen=True)
class SurebetResult:
    event: str
    market: str
    bankroll: float
    implied_probability_sum: float
    theoretical_roi: float
    guaranteed_profit: float
    is_arbitrage: bool
    liquidity_feasible: bool
    legs: list[SurebetLeg]

    def to_dict(self) -> dict:
        return {
            "event": self.event,
            "market": self.market,
            "bankroll": round(self.bankroll, 6),
            "implied_probability_sum": round(self.implied_probability_sum, 8),
            "theoretical_roi": round(self.theoretical_roi, 8),
            "guaranteed_profit": round(self.guaranteed_profit, 6),
            "is_arbitrage": self.is_arbitrage,
            "liquidity_feasible": self.liquidity_feasible,
            "legs": [asdict(leg) for leg in self.legs],
        }


def _positive_number(value: float, label: str) -> float:
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a finite number greater than zero")
    return value


def effective_decimal_odds(odds: float, commission: float = 0.0) -> float:
    """Net winning payout / stake, assuming commission is charged on winnings."""
    odds = float(odds)
    commission = float(commission)
    if not isfinite(odds) or odds <= 1:
        raise ValueError("Decimal odds must be greater than 1.0")
    if not isfinite(commission) or not 0 <= commission < 1:
        raise ValueError("commission must be >= 0 and < 1")
    return 1.0 + (odds - 1.0) * (1.0 - commission)


def calculate_surebet(rows: Iterable[OddsRow], bankroll: float) -> SurebetResult:
    """Dutch mutually exclusive outcomes; commission is charged on winning profit.

    Each row must represent a different outcome of the same event/market. The caller
    must ensure the outcomes cover the market and share settlement rules.
    """
    bankroll = _positive_number(bankroll, "bankroll")
    legs_in = list(rows)
    if len(legs_in) < 2:
        raise ValueError("At least two distinct outcomes are required")
    event_markets = {(r.event, r.market) for r in legs_in}
    if len(event_markets) != 1:
        raise ValueError("All Surebet rows must have the same event and market")
    selections = [r.selection.casefold() for r in legs_in]
    if len(set(selections)) != len(selections):
        raise ValueError("Duplicate selections are not allowed in a Surebet group")

    eff = [effective_decimal_odds(r.odds, r.commission) for r in legs_in]
    inv_sum = sum(1.0 / x for x in eff)
    stakes = [bankroll * (1.0 / x) / inv_sum for x in eff]
    payouts = [s * o for s, o in zip(stakes, eff)]
    guaranteed_profit = min(payouts) - bankroll
    roi = guaranteed_profit / bankroll
    legs = [
        SurebetLeg(
            selection=r.selection,
            source=r.source,
            odds=r.odds,
            commission=r.commission,
            stake=stakes[i],
            available=r.available,
            effective_odds=eff[i],
        )
        for i, r in enumerate(legs_in)
    ]
    event, market = next(iter(event_markets))
    liquidity_feasible = all(
        r.available is None or stakes[i] <= r.available + 1e-9
        for i, r in enumerate(legs_in)
    )
    return SurebetResult(
        event=event,
        market=market,
        bankroll=bankroll,
        implied_probability_sum=inv_sum,
        theoretical_roi=roi,
        guaranteed_profit=guaranteed_profit,
        is_arbitrage=(inv_sum < 1.0 - 1e-12) and liquidity_feasible,
        liquidity_feasible=liquidity_feasible,
        legs=legs,
    )


@dataclass(frozen=True)
class BackLayResult:
    back_odds: float
    lay_odds: float
    back_stake: float
    lay_stake: float
    lay_liability: float
    lay_commission: float
    pnl_if_selection_wins: float
    pnl_if_selection_loses: float
    balanced_pnl: float
    is_positive_after_fees: bool

    def to_dict(self) -> dict:
        result = asdict(self)
        return {k: (round(v, 8) if isinstance(v, float) else v) for k, v in result.items()}


def calculate_back_lay(
    back_odds: float,
    lay_odds: float,
    back_stake: float,
    lay_commission: float = 0.0,
    back_commission: float = 0.0,
    lay_stake: float | None = None,
) -> BackLayResult:
    """Calculate hedge and net P/L for backing a selection and laying the same one.

    Commission is charged on winning profit at each venue. If lay_stake is omitted,
    choose the stake that equalizes the two outcome P/L values after the configured
    commissions. This does not include exchange-specific rounding or market fees.
    """
    back_odds = float(back_odds)
    lay_odds = float(lay_odds)
    back_stake = _positive_number(back_stake, "back_stake")
    if not isfinite(back_odds) or back_odds <= 1:
        raise ValueError("back_odds must be greater than 1.0")
    if not isfinite(lay_odds) or lay_odds <= 1:
        raise ValueError("lay_odds must be greater than 1.0")
    for label, fee in (("lay_commission", lay_commission), ("back_commission", back_commission)):
        if not isfinite(float(fee)) or not 0 <= float(fee) < 1:
            raise ValueError(f"{label} must be >= 0 and < 1")
    lay_commission = float(lay_commission)
    back_commission = float(back_commission)

    # If selection wins: back winnings after commission - lay liability.
    # If selection loses: -back stake + lay winnings after commission.
    # Equating those outcomes gives L = B * (Ob - c_back*(Ob-1)) / (Ol - c_lay).
    if lay_stake is None:
        net_back_win = back_stake * (1.0 + (back_odds - 1.0) * (1.0 - back_commission))
        lay_stake = net_back_win / (lay_odds - lay_commission)
    lay_stake = _positive_number(lay_stake, "lay_stake")
    liability = lay_stake * (lay_odds - 1.0)
    pnl_win = back_stake * (back_odds - 1.0) * (1.0 - back_commission) - liability
    pnl_lose = -back_stake + lay_stake * (1.0 - lay_commission)
    balanced = min(pnl_win, pnl_lose)
    return BackLayResult(
        back_odds=back_odds,
        lay_odds=lay_odds,
        back_stake=back_stake,
        lay_stake=lay_stake,
        lay_liability=liability,
        lay_commission=lay_commission,
        pnl_if_selection_wins=pnl_win,
        pnl_if_selection_loses=pnl_lose,
        balanced_pnl=balanced,
        is_positive_after_fees=pnl_win > 0 and pnl_lose > 0,
    )
