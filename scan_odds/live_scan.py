"""Live read-only scan. Uses provider APIs when authorized; never places bets."""
from __future__ import annotations
import argparse, json, time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .arbitrage import calculate_surebet
from .models import OddsRow
from .providers import BetfairProvider, OvertimeProvider

def _load_provider(name: str) -> dict[str,Any]:
    if name=="betfair": return BetfairProvider().fetch().to_dict()
    if name=="overtime": return OvertimeProvider().fetch(live=True).to_dict()
    raise ValueError(f"Unknown provider: {name}")

def _eligible_rows(snapshots: list[dict[str,Any]], max_age: float) -> list[OddsRow]:
    now=datetime.now(timezone.utc); rows=[]
    for snapshot in snapshots:
        if snapshot.get("status")!="ok": continue
        for raw in snapshot.get("odds",[]):
            if raw.get("side","back")!="back": continue
            try:
                stamp=datetime.fromisoformat(str(raw.get("timestamp","")).replace("Z","+00:00"))
                if stamp.tzinfo is None: stamp=stamp.replace(tzinfo=timezone.utc)
                age=(now-stamp).total_seconds()
                if age < -5 or age > max_age: continue
                rows.append(OddsRow.from_mapping(raw))
            except (ValueError,TypeError): continue
    return rows

def run_once(providers: list[str], bankroll: float, max_age: float, output: str | None) -> dict[str,Any]:
    snapshots=[]
    for name in providers:
        try: snapshots.append(_load_provider(name))
        except Exception as exc:
            snapshots.append({"provider":name,"status":"error","fetched_at":datetime.now(timezone.utc).isoformat(),
                              "count":0,"message":str(exc),"odds":[]})
    rows=_eligible_rows(snapshots,max_age); groups=defaultdict(list)
    for row in rows: groups[(row.event.casefold(),row.market.casefold())].append(row)
    results=[]
    for group in groups.values():
        best={}
        for row in group:
            key=row.selection.casefold()
            if key not in best or row.odds>best[key].odds: best[key]=row
        if len(best)<2: continue
        try:
            result=calculate_surebet(best.values(),bankroll); item=result.to_dict()
            item["executable_candidate"]=bool(result.is_arbitrage and result.liquidity_feasible)
            results.append(item)
        except ValueError: continue
    results.sort(key=lambda x:x["theoretical_roi"],reverse=True)
    report={"mode":"live-read-only-paper-scan","generated_at":datetime.now(timezone.utc).isoformat(),
        "bankroll_usd":bankroll,"automatic_betting":False,"max_quote_age_seconds":max_age,
        "provider_status":snapshots,"usable_back_quotes":len(rows),"opportunities":results,
        "warning":"Theoretical candidates are not guaranteed executable. Verify market identity, settlement rules, fees, limits, liquidity, and latency."}
    rendered=json.dumps(report,indent=2,ensure_ascii=False)
    if output:
        path=Path(output); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(rendered+"\n",encoding="utf-8")
    print(rendered); return report

def main() -> None:
    parser=argparse.ArgumentParser(description="Scan real provider odds; read-only, no bets placed.")
    parser.add_argument("--providers",default="betfair,overtime",help="comma-separated: betfair,overtime")
    parser.add_argument("--bankroll",type=float,default=100.0)
    parser.add_argument("--max-age",type=float,default=180.0)
    parser.add_argument("--interval",type=float,default=0.0,help="repeat interval seconds; 0 means one scan")
    parser.add_argument("--output",default="reports/latest-live-scan.json")
    args=parser.parse_args()
    if args.bankroll<=0 or args.max_age<=0 or args.interval<0: parser.error("bankroll/max-age must be positive; interval cannot be negative")
    providers=[p.strip().lower() for p in args.providers.split(",") if p.strip()]
    if not providers or any(p not in {"betfair","overtime"} for p in providers): parser.error("providers must contain betfair and/or overtime")
    while True:
        run_once(providers,args.bankroll,args.max_age,args.output)
        if not args.interval: break
        time.sleep(args.interval)

if __name__=="__main__": main()
