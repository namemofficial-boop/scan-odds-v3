# Live odds scan (read-only)

This adds the first live-provider layer. It does not place bets; the $100 bankroll is only used for paper calculations.

## Run

From the repository root:

    python -m scan_odds.live_scan --providers betfair --bankroll 100

Run both configured sources repeatedly:

    python -m scan_odds.live_scan --providers betfair,overtime --bankroll 100 --interval 15

The report is written to reports/latest-live-scan.json. Errors are included in provider status. Press Ctrl+C to stop.

## Credentials

Set these environment variables locally, never in GitHub or chat:
- BETFAIR_APP_KEY
- BETFAIR_SESSION_TOKEN
- OVERTIME_API_KEY

This module reads environment variables directly and does not load a .env file automatically.

## Coverage and limits

- Betfair polls MATCH_ODDS markets and requests best back/lay prices. Surebet scan uses back prices only. Delayed keys can return delayed quotes; quote age does not prove real-time freshness. Session tokens expire.
- Overtime calls protected prematch/live market endpoints using x-api-key. Approved access is required. If the current schema is not recognized, the scanner reports schema_unrecognized instead of inventing odds.
- Web3 gambling sites have no universal odds API. Each site needs its own authorized feed or page adapter. No CAPTCHA, login, anti-bot, or access-control bypass is implemented.
- Initial market matching requires exact event and market labels; cross-site matching is not yet reliable enough for live execution. Settlement rules, period, handicap and outcome mappings must be verified.
- A theoretical opportunity is not guaranteed executable. This program never places bets.

## Next steps

1. Validate actual Betfair responses with an authorized key/session.
2. Obtain approved Overtime API access and validate its actual response schema.
3. Add and test one connector per Web3 site where odds data is accessible and authorized.
4. Add event/market identity mapping, exchange fees, limits, and paper execution simulation.
