"""Command-line interface."""
import argparse
import json
import sys
from collections import defaultdict

from .arbitrage import calculate_back_lay, calculate_surebet
from .io import load_rows


def _surebet(args: argparse.Namespace) -> int:
    rows = load_rows(args.input)
    groups = defaultdict(list)
    for row in rows:
        groups[(row.event, row.market)].append(row)
    results = []
    for group in groups.values():
        if len(group) < 2:
            continue
        result = calculate_surebet(group, args.bankroll)
        item = result.to_dict()
        if args.only_arbitrage and not result.is_arbitrage:
            continue
        results.append(item)
    results.sort(key=lambda item: item["theoretical_roi"], reverse=True)
    print(json.dumps({"mode": "surebet", "count": len(results), "results": results}, indent=2))
    return 0


def _back_lay(args: argparse.Namespace) -> int:
    result = calculate_back_lay(
        back_odds=args.back_odds,
        lay_odds=args.lay_odds,
        back_stake=args.back_stake,
        lay_commission=args.lay_commission,
        back_commission=args.back_commission,
        lay_stake=args.lay_stake,
    )
    print(json.dumps({"mode": "back-lay", **result.to_dict()}, indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="scan-odds", description="Scan Odds V3 calculation engine")
    sub = parser.add_subparsers(dest="command", required=True)
    surebet = sub.add_parser("surebet", help="scan JSON/CSV odds snapshot for Surebet groups")
    surebet.add_argument("--input", required=True, help="path to JSON or CSV odds snapshot")
    surebet.add_argument("--bankroll", type=float, default=100.0, help="total stake budget")
    surebet.add_argument("--only-arbitrage", action="store_true", help="only show groups with theoretical positive ROI")
    surebet.set_defaults(func=_surebet)

    backlay = sub.add_parser("back-lay", help="calculate Back/Lay hedge and both outcome P/L")
    backlay.add_argument("--back-odds", type=float, required=True)
    backlay.add_argument("--lay-odds", type=float, required=True)
    backlay.add_argument("--back-stake", type=float, required=True)
    backlay.add_argument("--lay-commission", type=float, default=0.0)
    backlay.add_argument("--back-commission", type=float, default=0.0)
    backlay.add_argument("--lay-stake", type=float, default=None, help="optional fixed lay stake; omit to balance P/L")
    backlay.set_defaults(func=_back_lay)

    args = parser.parse_args()
    try:
        sys.exit(args.func(args))
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
