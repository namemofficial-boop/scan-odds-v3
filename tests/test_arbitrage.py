import math
import pytest

from scan_odds.arbitrage import calculate_back_lay, calculate_surebet, effective_decimal_odds
from scan_odds.models import OddsRow


def row(selection, odds, commission=0.0, event="A vs B", market="1x2"):
    return OddsRow(event, market, selection, odds, commission, "test", None, None)


def test_effective_odds_with_commission():
    assert effective_decimal_odds(3.0, 0.05) == pytest.approx(2.9)


def test_surebet_positive_after_fees_and_balanced_payout():
    result = calculate_surebet([
        row("A", 3.2),
        row("Draw", 3.5),
        row("B", 3.7, 0.02),
    ], 100)
    assert result.is_arbitrage
    assert result.guaranteed_profit > 0
    payouts = [leg.stake * leg.effective_odds for leg in result.legs]
    assert max(payouts) - min(payouts) < 1e-8
    assert sum(leg.stake for leg in result.legs) == pytest.approx(100)


def test_no_surebet():
    result = calculate_surebet([
        row("A", 2.0), row("Draw", 3.0), row("B", 3.0)
    ], 100)
    assert not result.is_arbitrage
    assert result.guaranteed_profit < 0


def test_reject_mixed_markets():
    with pytest.raises(ValueError):
        calculate_surebet([
            row("A", 3.0, market="full_time"),
            row("Draw", 3.5, market="first_half"),
        ], 100)


def test_back_lay_balances_after_commission():
    result = calculate_back_lay(2.2, 2.1, 10, lay_commission=0.02)
    assert result.lay_stake > 0
    assert result.lay_liability > 0
    assert result.pnl_if_selection_wins == pytest.approx(result.pnl_if_selection_loses)
    assert result.balanced_pnl > 0  # back odds above lay odds can yield a positive hedge after commission


def test_back_lay_fixed_stake_reports_both_sides():
    result = calculate_back_lay(3.0, 2.5, 10, lay_stake=12)
    assert math.isfinite(result.pnl_if_selection_wins)
    assert math.isfinite(result.pnl_if_selection_loses)
    assert result.pnl_if_selection_wins != pytest.approx(result.pnl_if_selection_loses)
