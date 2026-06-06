from __future__ import annotations

import json
import hashlib
import os
from dataclasses import dataclass
from typing import Any, Optional
import urllib.error
import urllib.request


@dataclass(frozen=True)
class ConceptStock:
    code: str
    name: str
    price: float = 0.0
    change_pct: float = 0.0


@dataclass(frozen=True)
class ConceptSector:
    code: str
    name: str
    change_pct: float = 0.0
    stock_count: int = 0


@dataclass(frozen=True)
class TradeCalendarDay:
    cal_date: str
    is_open: bool
    pretrade_date: Optional[str] = None


class TushareConceptAdapter:
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
    def concept_provider(self) -> str:
        return "ths"

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
        self, *, api_name: str, params: dict[str, Any], fields: list[str]
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
            "fields": ",".join([str(f) for f in fields if str(f).strip()]),
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
            self._errors.append(f"api_error: api={api} code={code} msg={doc.get('msg')}{rid_part}")
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

    def fetch_all_concepts(self) -> list[ConceptSector]:
        rows = self._call(
            api_name="ths_index",
            params={"type": "N"},
            fields=["ts_code", "name", "count"],
        )
        sectors: list[ConceptSector] = []
        for r in rows:
            code = str(r.get("ts_code") or "").strip()
            name = str(r.get("name") or "").strip()
            if not code or not name:
                continue
            stock_count = 0
            raw_count = r.get("count")
            if raw_count is not None:
                try:
                    stock_count = int(raw_count)
                except Exception:
                    stock_count = 0
            sectors.append(ConceptSector(code=code, name=name, stock_count=stock_count))
        return sectors

    def fetch_hot_concepts(self, *, limit: int = 20) -> list[ConceptSector]:
        concepts = self.fetch_all_concepts()
        return concepts[: max(0, int(limit))]

    def fetch_concept_stocks(self, *, concept_code: str, limit: int = 50) -> list[ConceptStock]:
        rows = self._call(
            api_name="ths_member",
            params={"ts_code": str(concept_code)},
            fields=["ts_code", "con_code", "con_name"],
        )
        out: list[ConceptStock] = []
        for r in rows:
            ts_code = str(r.get("con_code") or "").strip()
            name = str(r.get("con_name") or "").strip()
            if not ts_code or not name:
                continue
            code = ts_code.split(".", 1)[0].strip()
            if not code:
                continue
            out.append(ConceptStock(code=code, name=name))
            if len(out) >= int(limit):
                break
        return out

    @staticmethod
    def _to_ymd(value: str) -> str:
        raw = str(value or "").strip()
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            return raw.replace("-", "")
        return raw

    @staticmethod
    def _from_ymd(value: object) -> Optional[str]:
        raw = str(value or "").strip()
        if len(raw) != 8 or not raw.isdigit():
            return None
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"

    def fetch_trade_calendar(
        self,
        *,
        start_date: str,
        end_date: str,
        exchange: str = "SSE",
    ) -> list[TradeCalendarDay]:
        rows = self._call(
            api_name="trade_cal",
            params={
                "exchange": str(exchange or "").strip(),
                "start_date": self._to_ymd(start_date),
                "end_date": self._to_ymd(end_date),
            },
            fields=["cal_date", "is_open", "pretrade_date"],
        )
        out: list[TradeCalendarDay] = []
        for r in rows:
            cal_date = self._from_ymd(r.get("cal_date"))
            if not cal_date:
                continue
            raw_open = r.get("is_open")
            is_open = str(raw_open).strip() in {"1", "true", "True", "yes", "Y"}
            pretrade = self._from_ymd(r.get("pretrade_date"))
            out.append(TradeCalendarDay(cal_date=cal_date, is_open=is_open, pretrade_date=pretrade))
        out.sort(key=lambda x: x.cal_date)
        return out
