# Scan Odds V3

A practical odds-arbitrage calculation core with **real Surebet and Back/Lay balancing**, CSV/JSON input, tests, and explicit data-source boundaries.

## What works now
- Surebet calculation for outcomes of the same event/market, with per-outcome decimal odds and commission rates.
- Stake allocation for a specified total bankroll, equalized net payout, estimated profit and ROI after configured commission.
- Back/Lay hedge sizing, lay liability, commission-aware P/L for both selection outcomes, and balanced hedge sizing.
- CLI scans normalized JSON/CSV odds snapshots and emits machine-readable JSON.
- Input validation rejects invalid odds, invalid commission, and incompatible event/market keys when supplied.
- Unit tests for core calculations.

## What is not magically included
This repository does **not** claim live access to every bookmaker. Live feeds require each provider's approved API/stream access and credentials. No passwords, session cookies, API secrets, or private keys belong in this repository. The included sample data is clearly labelled sample input, not live odds. Site HTML scraping is not enabled by default; follow each provider's terms and access controls.

Overtime V2 market endpoints require an approved API key. Betfair live Exchange streaming requires an appropriate application key and session token. Add provider adapters only after access is approved and the response schemas have been verified.

## Requirements
- Python 3.11+
- Install: `python -m pip install -e ".[dev]"`

## Run
Sample Surebet scan:
```bash
python -m scan_odds.cli surebet --input examples/odds.json --bankroll 100
```

Back/Lay hedge:
```bash
python -m scan_odds.cli back-lay --back-odds 2.20 --lay-odds 2.10 --back-stake 10 --lay-commission 0.02
```

Tests:
```bash
python -m pytest -q
```

## JSON input format
Each row is one selectable outcome:
```json
{
  "event": "Team A vs Team B",
  "market": "match_winner_90m",
  "selection": "Team A",
  "odds": 2.15,
  "commission": 0.02,
  "source": "sample-source",
  "available": 100
}
```
All outcomes in one Surebet group must be mutually exclusive and collectively cover the same settlement market. Do not combine full-time and half-time markets, different handicaps, or markets with different settlement rules.

## Important assumptions
- Odds are decimal.
- Commission is a fraction: 0.02 means 2%, charged on winning profit.
- Available stake/liquidity is an optional cap; real execution can still fail due to movement, limits, latency, or rejected orders.
- The calculator estimates opportunity only. It does not place bets or guarantee profit.
