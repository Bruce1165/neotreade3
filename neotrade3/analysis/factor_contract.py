"""
因子契约定义模块 (Factor Contract)

集中定义因子矩阵中所有因子的元数据，提供统一的因子注册表、查询与校验能力。
与 factor_matrix.py 中实际使用的因子保持一一对应。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FactorDefinition:
    """单个因子的契约定义。

    Attributes
    ----------
    factor_id : str
        因子唯一标识，与 payload / signals 中的字段名一致。
    name : str
        因子中文显示名。
    category : str
        因子所属分类：market / fundamental / screener / analysis / lab / announcement。
    frequency : str
        数据频率：daily / realtime / on_event。
    data_source : str
        数据来源描述，格式为 "表名.字段名" 或模块路径。
    description : str
        因子含义与计算逻辑的简要说明。
    direction : str
        因子方向偏好：higher_better / lower_better / neutral。
    """

    factor_id: str
    name: str
    category: str
    frequency: str
    data_source: str
    description: str
    direction: str


# ---------------------------------------------------------------------------
# 因子注册表 —— 18 个因子，与 factor_matrix.py 逐一对应
# ---------------------------------------------------------------------------

FACTOR_REGISTRY: list[FactorDefinition] = [
    # ---- 市场因子 (market) ---- 源自 daily_prices 表
    FactorDefinition(
        factor_id="pct_change",
        name="当日涨跌幅",
        category="market",
        frequency="daily",
        data_source="daily_prices.pct_change",
        description="当日收盘价相对前一日收盘价的百分比变化，用于技术评分和信号方向判断。",
        direction="higher_better",
    ),
    FactorDefinition(
        factor_id="amount",
        name="成交额",
        category="market",
        frequency="daily",
        data_source="daily_prices.amount",
        description="当日总成交金额（元），用于 universe 选股排序和情绪评分。",
        direction="higher_better",
    ),
    FactorDefinition(
        factor_id="amount_rank",
        name="成交额排名",
        category="market",
        frequency="daily",
        data_source="daily_prices.amount（排序后计算）",
        description="个股成交额在 universe 中的降序排名，用于情绪评分中的 amount_score。",
        direction="lower_better",
    ),
    FactorDefinition(
        factor_id="turnover",
        name="换手率",
        category="market",
        frequency="daily",
        data_source="daily_prices.turnover",
        description="当日换手率（%），用于成交量趋势 proxy 和共振评分。",
        direction="neutral",
    ),
    FactorDefinition(
        factor_id="volume",
        name="成交量",
        category="market",
        frequency="daily",
        data_source="daily_prices.volume",
        description="当日总成交量（手），辅助成交额进行量价分析。",
        direction="neutral",
    ),
    # ---- 基本面因子 (fundamental) ---- 源自 stocks 表
    FactorDefinition(
        factor_id="pe_ratio",
        name="市盈率",
        category="fundamental",
        frequency="daily",
        data_source="stocks.pe_ratio",
        description="市盈率（PE），composite 评分权重 50%。<15 低估，15-30 合理，30-60 偏高，>60 高估。",
        direction="lower_better",
    ),
    FactorDefinition(
        factor_id="pb_ratio",
        name="市净率",
        category="fundamental",
        frequency="daily",
        data_source="stocks.pb_ratio",
        description="市净率（PB），composite 评分权重 30%。<1 破净，1-2 低估，2-5 合理，>5 高估。",
        direction="lower_better",
    ),
    FactorDefinition(
        factor_id="roe",
        name="净资产收益率",
        category="fundamental",
        frequency="daily",
        data_source="stocks.roe",
        description="净资产收益率（ROE %），composite 评分权重 20%。>15 优秀，8-15 一般，<8 较差。",
        direction="higher_better",
    ),
    FactorDefinition(
        factor_id="market_cap",
        name="总市值",
        category="fundamental",
        frequency="daily",
        data_source="stocks.total_market_cap",
        description="总市值（亿元），用于大盘/中盘/小盘分类标签，不直接参与评分。",
        direction="neutral",
    ),
    # ---- 筛选器因子 (screener)
    FactorDefinition(
        factor_id="screener_hits",
        name="筛选器命中数",
        category="screener",
        frequency="daily",
        data_source="screener_runs（var/artifacts/screener_runs/{date}/）",
        description="当日命中的筛选器总数，每个命中 +8 technical_score。",
        direction="higher_better",
    ),
    FactorDefinition(
        factor_id="limit_up_reason",
        name="涨停原因",
        category="screener",
        frequency="on_event",
        data_source="limit_up_reasons（外部数据源，当前占位）",
        description="涨停原因命中记录，当前为占位因子，value 固定为 0.0。",
        direction="higher_better",
    ),
    # ---- 分析因子 (analysis)
    FactorDefinition(
        factor_id="resonance_score",
        name="共振评分",
        category="analysis",
        frequency="daily",
        data_source="resonance_scorer.calculate_technical_score()",
        description="基于 RPS、价格趋势、成交量趋势、均线排列、突破信号的共振技术评分（0-100），加成 technical_score。",
        direction="higher_better",
    ),
    FactorDefinition(
        factor_id="stock_tier",
        name="个股分层",
        category="analysis",
        frequency="daily",
        data_source="stock_tiering.analyze()",
        description="个股在板块内的分层（leader / core / follower），leader +10 sentiment_score，core +5。",
        direction="higher_better",
    ),
    FactorDefinition(
        factor_id="market_phase",
        name="市场阶段",
        category="analysis",
        frequency="daily",
        data_source="market_phase.detect_market_phase()",
        description="当前市场阶段（bull / bear / range / transition），决定 technical / sentiment / composite 的动态权重。",
        direction="neutral",
    ),
    FactorDefinition(
        factor_id="sector_rps",
        name="板块相对强度",
        category="analysis",
        frequency="daily",
        data_source="sector_rotation.analyze() → rps_120",
        description="个股所属板块的 120 日相对强度排名百分位，用于共振评分和情绪加成。",
        direction="higher_better",
    ),
    FactorDefinition(
        factor_id="elliott_wave",
        name="艾略特波浪",
        category="analysis",
        frequency="daily",
        data_source="elliott_wave.ElliottWaveAnalyzer",
        description="艾略特波浪分析结果，识别当前波浪位置与交易信号，用于信号生成模块。",
        direction="neutral",
    ),
    # ---- 实验室因子 (lab)
    FactorDefinition(
        factor_id="lab_hits",
        name="实验室命中数",
        category="lab",
        frequency="daily",
        data_source="lab_runs（var/artifacts/lab_runs/{date}/）",
        description="当日命中的实验室策略总数，每个命中 +5 technical_score（上限 15）和 +5 sentiment_score（上限 20）。",
        direction="higher_better",
    ),
    # ---- 公告因子 (announcement)
    FactorDefinition(
        factor_id="announcement",
        name="公告",
        category="announcement",
        frequency="on_event",
        data_source="announcements（外部数据源，当前占位）",
        description="公司公告命中记录，当前为占位因子，value 固定为 0.0，direction 为 neutral。",
        direction="neutral",
    ),
]

# 按 factor_id 建立快速索引
_FACTOR_INDEX: dict[str, FactorDefinition] = {
    f.factor_id: f for f in FACTOR_REGISTRY
}


# ---------------------------------------------------------------------------
# 查询与校验函数
# ---------------------------------------------------------------------------

def get_factor(factor_id: str) -> FactorDefinition | None:
    """根据 factor_id 查找因子定义，未找到返回 None。"""
    return _FACTOR_INDEX.get(factor_id)


def get_factors_by_category(category: str) -> list[FactorDefinition]:
    """返回指定分类下的所有因子定义。"""
    return [f for f in FACTOR_REGISTRY if f.category == category]


def validate_factor_matrix_payload(payload: dict) -> list[str]:
    """校验因子矩阵 payload 中 candidate 记录是否包含所有必需的因子字段。

    Parameters
    ----------
    payload : dict
        FactorMatrixBuilder.build() 返回的完整 payload。

    Returns
    -------
    list[str]
        校验错误列表，空列表表示全部通过。
    """
    errors: list[str] = []

    # 检查 payload 顶层结构
    for key in ("target_date", "tiers", "candidates_summary", "market_context"):
        if key not in payload:
            errors.append(f"payload 缺少顶层字段: {key}")

    # 从 tiers 中收集所有 candidate 记录
    tiers = payload.get("tiers", {})
    candidates: list[dict] = []
    for tier_key in ("ge_80", "ge_70", "ge_60"):
        tier_list = tiers.get(tier_key, [])
        if not isinstance(tier_list, list):
            errors.append(f"tiers.{tier_key} 不是列表")
            continue
        candidates.extend(tier_list)

    if not candidates:
        # 无 candidate 时跳过字段级校验（可能是空 payload）
        return errors

    # 每个 candidate 必须包含的字段
    required_candidate_fields = {
        "stock_code", "stock_name", "certainty", "subscores", "signals", "factor_summary",
    }
    # signals 中必须覆盖的 factor_id 集合
    required_factor_ids = {f.factor_id for f in FACTOR_REGISTRY}

    for idx, c in enumerate(candidates):
        prefix = f"candidate[{idx}]"
        if not isinstance(c, dict):
            errors.append(f"{prefix}: 不是字典类型")
            continue

        # 检查 candidate 必需字段
        missing = required_candidate_fields - set(c.keys())
        if missing:
            errors.append(f"{prefix} 缺少字段: {sorted(missing)}")

        # 检查 signals 中是否覆盖所有注册因子
        signals = c.get("signals", [])
        if isinstance(signals, list):
            signal_names = {
                s.get("name", "") for s in signals if isinstance(s, dict)
            }
            missing_factors = required_factor_ids - signal_names
            if missing_factors:
                errors.append(
                    f"{prefix} signals 缺少因子: {sorted(missing_factors)}"
                )

    return errors
