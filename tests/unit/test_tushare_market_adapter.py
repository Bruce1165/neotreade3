from __future__ import annotations

import json

from neotrade3.data_sources.tushare_market_adapter import TushareMarketAdapter


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_fetch_company_announcements_builds_expected_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout=0):
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "code": 0,
                "msg": "",
                "data": {
                    "fields": ["ann_date", "ts_code", "title", "url"],
                    "items": [["20260613", "000001.SZ", "测试公告", "https://example.com/a.pdf"]],
                },
            }
        )

    monkeypatch.setattr(
        "neotrade3.data_sources.tushare_market_adapter.urllib.request.urlopen",
        _fake_urlopen,
    )

    adapter = TushareMarketAdapter(token="token-123", timeout_seconds=9)
    rows = adapter.fetch_company_announcements(ann_date="20260613")

    assert rows == [
        {
            "ann_date": "20260613",
            "ts_code": "000001.SZ",
            "title": "测试公告",
            "url": "https://example.com/a.pdf",
        }
    ]
    assert captured["timeout"] == 9
    assert captured["payload"] == {
        "api_name": "anns_d",
        "token": "token-123",
        "params": {"ann_date": "20260613"},
        "fields": "ann_date,ts_code,name,title,url,rec_time",
    }


def test_fetch_fund_portfolio_uses_expected_api_and_default_fields(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout=0):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "code": 0,
                "msg": "",
                "data": {
                    "fields": ["ts_code", "symbol", "mkv", "stk_mkv_ratio"],
                    "items": [["510330.SH", "300308", 123456.0, 8.2]],
                },
            }
        )

    monkeypatch.setattr(
        "neotrade3.data_sources.tushare_market_adapter.urllib.request.urlopen",
        _fake_urlopen,
    )

    adapter = TushareMarketAdapter(token="token-abc")
    rows = adapter.fetch_fund_portfolio(ts_code="510330.SH", period="20250331")

    assert rows == [
        {
            "ts_code": "510330.SH",
            "symbol": "300308",
            "mkv": 123456.0,
            "stk_mkv_ratio": 8.2,
        }
    ]
    assert captured["payload"] == {
        "api_name": "fund_portfolio",
        "token": "token-abc",
        "params": {"ts_code": "510330.SH", "period": "20250331"},
        "fields": (
            "ts_code,ann_date,end_date,symbol,mkv,amount,"
            "stk_mkv_ratio,stk_float_ratio"
        ),
    }
