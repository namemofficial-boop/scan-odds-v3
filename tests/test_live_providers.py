from scan_odds.providers import BetfairProvider, OvertimeProvider, _walk_overtime

def test_betfair_requires_local_credentials_without_network():
    provider = BetfairProvider(app_key="", session_token="")
    try:
        provider._rpc("listEventTypes", {})
    except RuntimeError as exc:
        assert "BETFAIR_APP_KEY" in str(exc)
    else:
        raise AssertionError("missing credentials must fail before making a request")

def test_overtime_requires_approved_key_without_network():
    provider = OvertimeProvider(api_key="")
    try:
        provider.fetch()
    except RuntimeError as exc:
        assert "OVERTIME_API_KEY" in str(exc)
    else:
        raise AssertionError("missing key must fail before making a request")

def test_overtime_normalizer_reads_simple_nested_fixture():
    payload = {
        "eventName": "Team A vs Team B",
        "marketName": "Match Winner",
        "outcomes": [
            {"outcomeName": "Team A", "decimalOdds": 2.1},
            {"outcomeName": "Team B", "decimalOdds": 1.9}
        ]
    }
    rows = _walk_overtime(payload)
    assert len(rows) == 2
    assert {row["selection"] for row in rows} == {"Team A", "Team B"}
    assert all(row["event"] == "Team A vs Team B" for row in rows)
