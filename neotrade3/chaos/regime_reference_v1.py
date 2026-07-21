from __future__ import annotations

from dataclasses import dataclass


def _mean(values: list[float]) -> float:
    items = [float(x) for x in list(values or [])]
    if not items:
        return 0.0
    return float(sum(items)) / float(len(items))


def _std(values: list[float]) -> float:
    items = [float(x) for x in list(values or [])]
    if len(items) <= 1:
        return 0.0
    m = _mean(items)
    var = _mean([(x - m) ** 2 for x in items])
    return float(var) ** 0.5


def _zscore(values: list[float], current: float) -> float | None:
    items = [float(x) for x in list(values or [])]
    if len(items) <= 1:
        return None
    m = _mean(items)
    s = _std(items)
    if s <= 0:
        return None
    return (float(current) - float(m)) / float(s)


def _percentile_rank(values: list[float], current: float) -> float | None:
    items = [float(x) for x in list(values or [])]
    if not items:
        return None
    cur = float(current)
    le = sum(1 for x in items if float(x) <= cur)
    return float(le) / float(len(items))


def _sign_with_deadzone(v: float, *, eps: float) -> int:
    x = float(v)
    if abs(x) < float(eps):
        return 0
    return 1 if x > 0 else -1


def _compress_nonzero_signs(signs: list[int]) -> list[int]:
    out: list[int] = []
    for s in list(signs or []):
        si = int(s)
        if si == 0:
            continue
        out.append(si)
    return out


def _flip_count_nonzero(signs: list[int]) -> int:
    nz = _compress_nonzero_signs(signs)
    if len(nz) <= 1:
        return 0
    c = 0
    prev = int(nz[0])
    for s in nz[1:]:
        si = int(s)
        if si != prev:
            c += 1
        prev = si
    return int(c)


def find_last_confirmed_flip_anchor_date_any(
    *,
    dates: list[str],
    net_energy_series: list[float],
    deadzone_eps: float,
    confirm_days: int,
) -> str:
    n = min(len(dates or []), len(net_energy_series or []))
    if n <= int(confirm_days) + 1:
        return ""
    dates_n = [str(dates[i]) for i in range(n)]
    series_n = [float(net_energy_series[i]) for i in range(n)]
    signs = [_sign_with_deadzone(v, eps=float(deadzone_eps)) for v in series_n]

    for i in range(n - int(confirm_days) - 1, -1, -1):
        s0 = int(signs[i])
        s1 = int(signs[i + 1])
        if s0 == 0 or s1 == 0 or s0 == s1:
            continue
        ok = True
        for j in range(1, int(confirm_days) + 1):
            if int(signs[i + j]) != s1:
                ok = False
                break
        if ok:
            return str(dates_n[i + 1])
    return ""


@dataclass(frozen=True)
class SelfHistoryReferenceV1:
    regime_anchor_date: str
    regime_day_index: int
    within_regime_window_days: int
    net_energy_percentile_in_window: float | None
    net_energy_zscore_in_window: float | None
    flip_count_in_window: int
    flip_rate_in_window: float
    yang_speed_mean_in_window: float
    regime_shift_flag: bool
    fixed_window_days: int
    fixed_flip_count: int
    fixed_flip_rate: float
    fixed_yang_speed_mean: float


def compute_self_history_reference_v1(
    *,
    dates: list[str],
    net_energy_series: list[float],
    deadzone_eps: float,
    confirm_days: int,
    fixed_window_days: int,
) -> SelfHistoryReferenceV1:
    n = min(len(dates or []), len(net_energy_series or []))
    if n <= 0:
        return SelfHistoryReferenceV1(
            regime_anchor_date="",
            regime_day_index=-1,
            within_regime_window_days=0,
            net_energy_percentile_in_window=None,
            net_energy_zscore_in_window=None,
            flip_count_in_window=0,
            flip_rate_in_window=0.0,
            yang_speed_mean_in_window=0.0,
            regime_shift_flag=False,
            fixed_window_days=int(fixed_window_days),
            fixed_flip_count=0,
            fixed_flip_rate=0.0,
            fixed_yang_speed_mean=0.0,
        )

    dates_n = [str(dates[i]) for i in range(n)]
    series_n = [float(net_energy_series[i]) for i in range(n)]
    current = float(series_n[-1])
    anchor_date = find_last_confirmed_flip_anchor_date_any(
        dates=dates_n,
        net_energy_series=series_n,
        deadzone_eps=float(deadzone_eps),
        confirm_days=int(confirm_days),
    )
    anchor_idx = dates_n.index(anchor_date) if anchor_date and anchor_date in dates_n else -1
    if anchor_idx >= 0:
        regime_start = int(anchor_idx)
        regime_day_index = int((n - 1) - anchor_idx)
    else:
        regime_start = max(0, n - int(max(1, fixed_window_days)))
        regime_day_index = -1
    regime_window = series_n[regime_start:n]
    regime_signs = [_sign_with_deadzone(v, eps=float(deadzone_eps)) for v in regime_window]
    flip_count = _flip_count_nonzero(regime_signs)
    nz = _compress_nonzero_signs(regime_signs)
    flip_rate = float(flip_count) / float(max(1, len(nz) - 1))
    diffs = [float(regime_window[i] - regime_window[i - 1]) for i in range(1, len(regime_window))] if len(regime_window) >= 2 else []
    speed_mean = _mean(diffs)
    pct_rank = _percentile_rank(regime_window, float(current))
    z = _zscore(regime_window, float(current))
    regime_shift = bool(pct_rank is not None and (float(pct_rank) <= 0.1 or float(pct_rank) >= 0.9))

    fw = int(max(1, fixed_window_days))
    fixed_start = max(0, n - fw)
    fixed_window = series_n[fixed_start:n]
    fixed_signs = [_sign_with_deadzone(v, eps=float(deadzone_eps)) for v in fixed_window]
    fixed_flip_count = _flip_count_nonzero(fixed_signs)
    fixed_nz = _compress_nonzero_signs(fixed_signs)
    fixed_flip_rate = float(fixed_flip_count) / float(max(1, len(fixed_nz) - 1))
    fixed_diffs = [float(fixed_window[i] - fixed_window[i - 1]) for i in range(1, len(fixed_window))] if len(fixed_window) >= 2 else []
    fixed_speed_mean = _mean(fixed_diffs)

    return SelfHistoryReferenceV1(
        regime_anchor_date=str(anchor_date),
        regime_day_index=int(regime_day_index),
        within_regime_window_days=int(len(regime_window)),
        net_energy_percentile_in_window=pct_rank,
        net_energy_zscore_in_window=z,
        flip_count_in_window=int(flip_count),
        flip_rate_in_window=float(flip_rate),
        yang_speed_mean_in_window=float(speed_mean),
        regime_shift_flag=bool(regime_shift),
        fixed_window_days=int(fixed_window_days),
        fixed_flip_count=int(fixed_flip_count),
        fixed_flip_rate=float(fixed_flip_rate),
        fixed_yang_speed_mean=float(fixed_speed_mean),
    )

