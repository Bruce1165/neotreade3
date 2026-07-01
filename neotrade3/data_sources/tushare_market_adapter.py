from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional


class TushareMarketAdapter:
    """Generic adapter for paid Tushare market intelligence endpoints."""

    def __init__(
        self,
        *,
        token: Optional[str] = None,
        timeout_seconds: int = 20,
        base_url: str = "https://api.tushare.pro",
    ) -> None:
        self._token = (token or os.environ.get("TUSHARE_TOKEN") or "").strip() or None
        self._timeout_seconds = int(timeout_seconds)
        self._base_url = str(base_url).strip()
        self._errors: list[str] = []
        self._last_api_name: Optional[str] = None
        self._last_code: Optional[object] = None
        self._last_msg: Optional[str] = None

    @property
    def configured(self) -> bool:
        return bool(self._token)

    @property
    def token_fingerprint(self) -> Optional[str]:
        if not self._token:
            return None
        return hashlib.sha256(self._token.encode("utf-8")).hexdigest()[:12]

    @property
    def errors(self) -> list[str]:
        return list(self._errors)

    @property
    def last_api_name(self) -> Optional[str]:
        return self._last_api_name

    @property
    def last_code(self) -> Optional[object]:
        return self._last_code

    @property
    def last_msg(self) -> Optional[str]:
        return self._last_msg

    def _call(
        self,
        *,
        api_name: str,
        params: Optional[dict[str, Any]] = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        if not self._token:
            raise RuntimeError("tushare token not configured")

        api = str(api_name or "").strip()
        if not api:
            raise ValueError("tushare api_name is empty")

        self._last_api_name = api
        self._last_code = None
        self._last_msg = None

        payload = {
            "api_name": api,
            "token": self._token,
            "params": params or {},
            "fields": ",".join([str(f) for f in (fields or []) if str(f).strip()]),
        }
        req = urllib.request.Request(
            self._base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            self._errors.append(f"request_error: {exc}")
            self._last_code = "request_error"
            self._last_msg = str(exc)
            return []

        try:
            doc = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._errors.append(f"json_decode_error: {exc}")
            self._last_code = "json_decode_error"
            self._last_msg = str(exc)
            return []

        if not isinstance(doc, dict):
            self._errors.append("invalid_response: not a dict")
            self._last_code = "invalid_response"
            self._last_msg = "not a dict"
            return []

        code = doc.get("code")
        request_id = doc.get("request_id")
        self._last_code = code
        self._last_msg = str(doc.get("msg") or "").strip() or None
        if code not in (0, "0"):
            rid = str(request_id).strip() if request_id is not None else ""
            rid_part = f" request_id={rid}" if rid else ""
            self._errors.append(
                f"api_error: api={api} code={code} msg={doc.get('msg')}{rid_part}"
            )
            return []

        data = doc.get("data")
        if not isinstance(data, dict):
            self._errors.append("invalid_response: data missing")
            return []

        data_fields = data.get("fields")
        items = data.get("items")
        if not isinstance(data_fields, list) or not isinstance(items, list):
            return []

        field_names = [str(x) for x in data_fields]
        out: list[dict[str, Any]] = []
        for row in items:
            if not isinstance(row, list):
                continue
            rec: dict[str, Any] = {}
            for idx, key in enumerate(field_names):
                rec[key] = row[idx] if idx < len(row) else None
            out.append(rec)
        return out

    @staticmethod
    def _clean_params(**kwargs: Any) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in kwargs.items():
            if value is None:
                continue
            if isinstance(value, str):
                raw = value.strip()
                if not raw:
                    continue
                out[key] = raw
                continue
            out[key] = value
        return out

    def fetch_company_announcements(
        self,
        *,
        ts_code: str | None = None,
        ann_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="anns_d",
            params=self._clean_params(
                ts_code=ts_code,
                ann_date=ann_date,
                start_date=start_date,
                end_date=end_date,
            ),
            fields=fields
            or ["ann_date", "ts_code", "name", "title", "url", "rec_time"],
        )

    def fetch_policy_documents(
        self,
        *,
        org: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        ptype: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="npr",
            params=self._clean_params(
                org=org,
                start_date=start_date,
                end_date=end_date,
                ptype=ptype,
            ),
            fields=fields
            or ["pubtime", "title", "url", "content_html", "pcode", "puborg", "ptype"],
        )

    def fetch_research_reports(
        self,
        *,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        report_type: str | None = None,
        ts_code: str | None = None,
        inst_csname: str | None = None,
        ind_name: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="research_report",
            params=self._clean_params(
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
                report_type=report_type,
                ts_code=ts_code,
                inst_csname=inst_csname,
                ind_name=ind_name,
            ),
            fields=fields
            or [
                "trade_date",
                "abstr",
                "title",
                "report_type",
                "author",
                "name",
                "ts_code",
                "inst_csname",
                "ind_name",
                "url",
            ],
        )

    def fetch_report_consensus(
        self,
        *,
        ts_code: str | None = None,
        report_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="report_rc",
            params=self._clean_params(
                ts_code=ts_code,
                report_date=report_date,
                start_date=start_date,
                end_date=end_date,
            ),
            fields=fields
            or [
                "ts_code",
                "name",
                "report_date",
                "report_title",
                "classify",
                "org_name",
                "quarter",
                "op_rt",
                "np",
                "eps",
                "pe",
                "roe",
                "rating",
                "imp_dg",
            ],
        )

    def fetch_institutional_surveys(
        self,
        *,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="stk_surv",
            params=self._clean_params(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
            ),
            fields=fields
            or [
                "ts_code",
                "name",
                "surv_date",
                "fund_visitors",
                "rece_place",
                "rece_mode",
                "rece_org",
                "org_type",
            ],
        )

    def fetch_etf_basic(
        self,
        *,
        ts_code: str | None = None,
        index_code: str | None = None,
        list_date: str | None = None,
        list_status: str | None = None,
        exchange: str | None = None,
        mgr: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="etf_basic",
            params=self._clean_params(
                ts_code=ts_code,
                index_code=index_code,
                list_date=list_date,
                list_status=list_status,
                exchange=exchange,
                mgr=mgr,
            ),
            fields=fields
            or [
                "ts_code",
                "csname",
                "extname",
                "index_code",
                "index_name",
                "list_date",
                "list_status",
                "exchange",
                "mgr_name",
                "etf_type",
            ],
        )

    def fetch_fund_daily(
        self,
        *,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="fund_daily",
            params=self._clean_params(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
            ),
            fields=fields
            or ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"],
        )

    def fetch_rt_etf_daily(
        self,
        *,
        ts_code: str,
        topic: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="rt_etf_k",
            params=self._clean_params(ts_code=ts_code, topic=topic),
            fields=fields
            or [
                "ts_code",
                "name",
                "pre_close",
                "high",
                "open",
                "low",
                "close",
                "vol",
                "amount",
                "num",
                "trade_time",
            ],
        )

    def fetch_etf_share_size(
        self,
        *,
        ts_code: str | None = None,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        exchange: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="etf_share_size",
            params=self._clean_params(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
                exchange=exchange,
            ),
            fields=fields
            or [
                "trade_date",
                "ts_code",
                "etf_name",
                "total_share",
                "total_size",
                "nav",
                "close",
                "exchange",
            ],
        )

    def fetch_rt_etf_sz_iopv(
        self,
        *,
        ts_code: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="rt_etf_sz_iopv",
            params=self._clean_params(ts_code=ts_code),
            fields=fields
            or [
                "trade_time",
                "ts_code",
                "price",
                "iopv",
                "pre_iopv",
                "buy_num",
                "buy_vol",
                "sell_num",
                "sell_vol",
            ],
        )

    def fetch_etf_index(
        self,
        *,
        ts_code: str | None = None,
        pub_date: str | None = None,
        base_date: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="etf_index",
            params=self._clean_params(
                ts_code=ts_code,
                pub_date=pub_date,
                base_date=base_date,
            ),
            fields=fields
            or [
                "ts_code",
                "indx_name",
                "indx_csname",
                "pub_party_name",
                "pub_date",
                "base_date",
                "adj_circle",
            ],
        )

    def fetch_index_weight(
        self,
        *,
        index_code: str,
        trade_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="index_weight",
            params=self._clean_params(
                index_code=index_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
            ),
            fields=fields or ["index_code", "con_code", "trade_date", "weight"],
        )

    def fetch_fund_basic(
        self,
        *,
        ts_code: str | None = None,
        market: str | None = None,
        status: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="fund_basic",
            params=self._clean_params(ts_code=ts_code, market=market, status=status),
            fields=fields
            or [
                "ts_code",
                "name",
                "management",
                "fund_type",
                "found_date",
                "list_date",
                "benchmark",
                "status",
                "market",
            ],
        )

    def fetch_fund_portfolio(
        self,
        *,
        ts_code: str | None = None,
        symbol: str | None = None,
        ann_date: str | None = None,
        period: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="fund_portfolio",
            params=self._clean_params(
                ts_code=ts_code,
                symbol=symbol,
                ann_date=ann_date,
                period=period,
                start_date=start_date,
                end_date=end_date,
            ),
            fields=fields
            or [
                "ts_code",
                "ann_date",
                "end_date",
                "symbol",
                "mkv",
                "amount",
                "stk_mkv_ratio",
                "stk_float_ratio",
            ],
        )

    def fetch_index_announcements(
        self,
        *,
        ann_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        src: str | None = None,
        fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        return self._call(
            api_name="idx_anns",
            params=self._clean_params(
                ann_date=ann_date,
                start_date=start_date,
                end_date=end_date,
                src=src,
            ),
            fields=fields or ["ann_date", "title", "url", "source", "type"],
        )
