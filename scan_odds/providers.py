"""Read-only live odds adapters. Never place bets or bypass provider access controls."""
from __future__ import annotations
import json, os, urllib.error, urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

BETFAIR_RPC = "https://api.betfair.com/exchange/betting/json-rpc/v1"
OVERTIME_MARKETS = "https://api.overtime.io/overtime-v2/markets"
OVERTIME_LIVE_MARKETS = "https://api.overtime.io/overtime-v2/live-markets"

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _request_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None,
                  payload: Any = None, timeout: float = 12.0) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Cannot reach {url}: {exc}") from exc

@dataclass
class ProviderResult:
    provider: str
    status: str
    fetched_at: str
    rows: list[dict[str, Any]]
    message: str = ""
    def to_dict(self) -> dict[str, Any]:
        return {"provider": self.provider, "status": self.status, "fetched_at": self.fetched_at,
                "count": len(self.rows), "message": self.message, "odds": self.rows}

class BetfairProvider:
    """Read-only Betfair Exchange polling using an active app key/session token."""
    def __init__(self, app_key: str | None = None, session_token: str | None = None):
        self.app_key = app_key or os.getenv("BETFAIR_APP_KEY", "")
        self.session_token = session_token or os.getenv("BETFAIR_SESSION_TOKEN", "")
    def _rpc(self, method: str, params: dict[str, Any]) -> Any:
        if not self.app_key or not self.session_token:
            raise RuntimeError("Set BETFAIR_APP_KEY and BETFAIR_SESSION_TOKEN in the local environment.")
        data = _request_json(BETFAIR_RPC, method="POST",
            headers={"X-Application": self.app_key, "X-Authentication": self.session_token,
                     "Content-Type": "application/json", "Accept": "application/json"},
            payload=[{"jsonrpc":"2.0","method":f"SportsAPING/v1.0/{method}","params":params,"id":1}])
        if not isinstance(data, list) or not data:
            raise RuntimeError(f"Unexpected Betfair response for {method}")
        item=data[0]
        if item.get("error"): raise RuntimeError(f"Betfair {method}: {item['error']}")
        return item.get("result", [])
    def fetch(self, max_markets: int = 100) -> ProviderResult:
        now=utc_now()
        catalogue=self._rpc("listMarketCatalogue", {
            "filter":{"marketTypeCodes":["MATCH_ODDS"],"marketBettingTypes":["ODDS"]},
            "marketProjection":["EVENT","RUNNER_DESCRIPTION","MARKET_START_TIME"],
            "sort":"FIRST_TO_START","maxResults":str(max(1,min(max_markets,200)))})
        if not catalogue: return ProviderResult("betfair","ok",now,[],"No MATCH_ODDS markets returned.")
        ids=[m["marketId"] for m in catalogue if m.get("marketId")]
        books=self._rpc("listMarketBook",{"marketIds":ids,"priceProjection":{"priceData":["EX_BEST_OFFERS"]}})
        by_id={b.get("marketId"):b for b in books if isinstance(b,dict)}
        rows=[]
        for market in catalogue:
            market_id=market.get("marketId"); book=by_id.get(market_id,{})
            event=market.get("event") or {}; event_name=event.get("name") or market.get("marketName") or str(market_id)
            market_name=market.get("marketName") or "MATCH_ODDS"
            runners={r.get("selectionId"):r for r in market.get("runners",[])}
            for runner in book.get("runners",[]):
                selection=runners.get(runner.get("selectionId"),{})
                ex=runner.get("ex",{}) or {}
                for side, offers in (("back",ex.get("availableToBack",[])),("lay",ex.get("availableToLay",[]))):
                    if offers:
                        best=offers[0]
                        rows.append({"event":event_name,"market":f"{market_id}:{market_name}",
                            "selection":selection.get("runnerName",str(runner.get("selectionId"))),
                            "odds":float(best["price"]),"available":float(best.get("size",0)),
                            "source":"betfair","side":side,"timestamp":now,"market_id":market_id,
                            "selection_id":runner.get("selectionId"),"status":book.get("status","UNKNOWN")})
        return ProviderResult("betfair","ok",now,rows,"Exchange prices; key may return delayed data. Read-only adapter.")

def _first(mapping: dict[str, Any], keys: tuple[str,...]) -> Any:
    for key in keys:
        if mapping.get(key) is not None: return mapping[key]
    return None

def _number(value: Any) -> float | None:
    try:
        if isinstance(value,dict): value=_first(value,("odds","price","decimalOdds","value"))
        if isinstance(value,str): value=value.strip().replace(",",".")
        number=float(value)
        return number if number>1 else None
    except (TypeError,ValueError): return None

def _walk_overtime(value: Any, inherited: dict[str,Any] | None=None) -> list[dict[str,Any]]:
    """Best-effort schema-tolerant normalization; unknown shapes are never fabricated."""
    inherited=dict(inherited or {}); out=[]
    if isinstance(value,list):
        for item in value: out.extend(_walk_overtime(item,inherited))
        return out
    if not isinstance(value,dict): return out
    event=_first(value,("eventName","event_name","fixtureName","gameName","title","name"))
    if event: inherited["event"]=str(event)
    market=_first(value,("marketName","market_name","marketType","market_type","marketId","id"))
    if market: inherited["market"]=str(market)
    selection=_first(value,("outcomeName","outcome_name","selectionName","selection_name","runnerName","label"))
    odds=_number(_first(value,("decimalOdds","decimal_odds","odds","price","currentOdds","current_odds")))
    if selection is not None and odds is not None and inherited.get("event") and inherited.get("market"):
        out.append({"event":inherited["event"],"market":inherited["market"],"selection":str(selection),
            "odds":odds,"source":"overtime","side":"back","timestamp":utc_now(),
            "available":_number(_first(value,("available","liquidity","size")))})
    for child in value.values():
        if isinstance(child,(dict,list)): out.extend(_walk_overtime(child,inherited))
    return out

class OvertimeProvider:
    """Overtime V2 protected market endpoints. Requires an approved x-api-key."""
    def __init__(self, api_key: str | None=None):
        self.api_key=api_key or os.getenv("OVERTIME_API_KEY","")
    def fetch(self, live: bool=False) -> ProviderResult:
        now=utc_now()
        if not self.api_key: raise RuntimeError("Overtime odds endpoints require an approved OVERTIME_API_KEY.")
        url=OVERTIME_LIVE_MARKETS if live else OVERTIME_MARKETS
        payload=_request_json(url,headers={"x-api-key":self.api_key,"Accept":"application/json"})
        rows=_walk_overtime(payload); seen=set(); unique=[]
        for row in rows:
            key=(row["event"],row["market"],row["selection"],row["odds"])
            if key not in seen: seen.add(key); unique.append(row)
        message="API schema recognized." if unique else "Response schema not recognized; no odds fabricated. Inspect response and update normalizer."
        return ProviderResult("overtime","ok" if unique else "schema_unrecognized",now,unique,message)
