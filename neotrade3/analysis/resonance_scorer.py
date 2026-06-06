"""
三维共振评分模块

提供技术面、资金面和政策面的三维共振评分功能。
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import date


class MarketPhase(Enum):
    """市场阶段枚举"""
    BULL = "bull"
    BEAR = "bear"
    RANGE = "range"
    TRANSITION = "transition"


@dataclass
class ResonanceWeights:
    """共振权重配置"""
    technical_weight: float = 0.4
    capital_weight: float = 0.35
    policy_weight: float = 0.25
    
    def validate(self) -> bool:
        """验证权重和是否为1"""
        total = self.technical_weight + self.capital_weight + self.policy_weight
        return abs(total - 1.0) < 0.001


@dataclass
class SubScores:
    """分项得分"""
    technical_score: float = 0.0
    capital_score: float = 0.0
    policy_score: float = 0.0


@dataclass
class ResonanceResult:
    """共振评分结果"""
    ts_code: str
    name: str
    total_score: float
    sub_scores: SubScores
    weights: ResonanceWeights
    market_phase: MarketPhase
    rank: int = 0
    notes: str = ""


# 正面政策关键词
POSITIVE_POLICY_KEYWORDS = [
    "利好", "支持", "鼓励", "扶持", "补贴", "减税",
    "降准", "降息", "宽松", "刺激", "改革", "开放",
    "创新", "科技", "新能源", "碳中和", "数字经济",
    "人工智能", "芯片", "半导体", "国产替代", "自主可控"
]

# 负面政策关键词
NEGATIVE_POLICY_KEYWORDS = [
    "利空", "监管", "整顿", "限制", "禁止", "处罚",
    "加息", "紧缩", "风险", "泡沫", "过热", "调控",
    "反垄断", "调查", "退市", "违规", "警示"
]


class ResonanceScorer:
    """共振评分器"""
    
    # 不同市场阶段的默认权重
    PHASE_WEIGHTS = {
        MarketPhase.BULL: ResonanceWeights(
            technical_weight=0.35,
            capital_weight=0.45,
            policy_weight=0.20
        ),
        MarketPhase.BEAR: ResonanceWeights(
            technical_weight=0.30,
            capital_weight=0.30,
            policy_weight=0.40
        ),
        MarketPhase.RANGE: ResonanceWeights(
            technical_weight=0.45,
            capital_weight=0.35,
            policy_weight=0.20
        ),
        MarketPhase.TRANSITION: ResonanceWeights(
            technical_weight=0.40,
            capital_weight=0.35,
            policy_weight=0.25
        )
    }
    
    def __init__(self, market_phase: MarketPhase = MarketPhase.TRANSITION):
        """
        初始化共振评分器
        
        Args:
            market_phase: 当前市场阶段
        """
        self.market_phase = market_phase
        self.weights = self.get_weights_for_phase(market_phase)
    
    def get_weights_for_phase(self, phase: MarketPhase) -> ResonanceWeights:
        """
        获取指定市场阶段的权重
        
        Args:
            phase: 市场阶段
            
        Returns:
            权重配置
        """
        return self.PHASE_WEIGHTS.get(phase, ResonanceWeights())
    
    def calculate_technical_score(
        self,
        rps_120: float,
        rps_250: float,
        price_trend: float,
        volume_trend: float,
        ma_alignment: bool = False,
        breakout_signal: bool = False
    ) -> float:
        """
        计算技术面得分
        
        Args:
            rps_120: 120日RPS
            rps_250: 250日RPS
            price_trend: 价格趋势得分 (0-1)
            volume_trend: 成交量趋势得分 (0-1)
            ma_alignment: 均线多头排列
            breakout_signal: 突破信号
            
        Returns:
            技术面得分 (0-100)
        """
        score = 0.0
        
        # RPS得分 (40%)
        rps_avg = (rps_120 + rps_250) / 2
        score += rps_avg * 0.4
        
        # 价格趋势得分 (25%)
        score += price_trend * 25
        
        # 成交量趋势得分 (20%)
        score += volume_trend * 20
        
        # 均线排列加分 (10%)
        if ma_alignment:
            score += 10
        
        # 突破信号加分 (5%)
        if breakout_signal:
            score += 5
        
        return min(score, 100.0)
    
    def calculate_capital_score(
        self,
        fund_flow_score: float,
        northbound_flow: float,
        institutional_score: float,
        margin_balance_trend: float = 0.0,
        turnover_rate: float = 0.0
    ) -> float:
        """
        计算资金面得分
        
        Args:
            fund_flow_score: 资金流向得分 (0-1)
            northbound_flow: 北向资金流向得分 (0-1)
            institutional_score: 机构持仓得分 (0-1)
            margin_balance_trend: 融资融券余额趋势 (0-1)
            turnover_rate: 换手率得分 (0-1)
            
        Returns:
            资金面得分 (0-100)
        """
        score = 0.0
        
        # 资金流向得分 (35%)
        score += fund_flow_score * 35
        
        # 北向资金得分 (25%)
        score += northbound_flow * 25
        
        # 机构持仓得分 (25%)
        score += institutional_score * 25
        
        # 融资融券趋势得分 (10%)
        score += margin_balance_trend * 10
        
        # 换手率得分 (5%)
        score += turnover_rate * 5
        
        return min(score, 100.0)
    
    def calculate_policy_score(
        self,
        sector_policy_score: float,
        policy_news: List[str],
        policy_sentiment: Optional[float] = None
    ) -> float:
        """
        计算政策面得分
        
        Args:
            sector_policy_score: 行业政策得分 (0-1)
            policy_news: 政策新闻列表
            policy_sentiment: 政策情绪得分 (0-1)，可选
            
        Returns:
            政策面得分 (0-100)
        """
        score = 0.0
        
        # 行业政策基础得分 (50%)
        score += sector_policy_score * 50
        
        # 分析新闻关键词
        if policy_news:
            positive_count = 0
            negative_count = 0
            
            for news in policy_news:
                news_lower = news.lower()
                for keyword in POSITIVE_POLICY_KEYWORDS:
                    if keyword in news_lower:
                        positive_count += 1
                for keyword in NEGATIVE_POLICY_KEYWORDS:
                    if keyword in news_lower:
                        negative_count += 1
            
            total_keywords = positive_count + negative_count
            if total_keywords > 0:
                sentiment_score = positive_count / total_keywords
                score += sentiment_score * 30
        
        # 政策情绪得分 (20%)
        if policy_sentiment is not None:
            score += policy_sentiment * 20
        
        return min(score, 100.0)
    
    def calculate_resonance(
        self,
        ts_code: str,
        name: str,
        technical_indicators: Dict[str, float],
        capital_indicators: Dict[str, float],
        policy_indicators: Dict[str, any],
        custom_weights: Optional[ResonanceWeights] = None
    ) -> ResonanceResult:
        """
        计算三维共振得分
        
        Args:
            ts_code: 股票代码
            name: 股票名称
            technical_indicators: 技术指标字典
            capital_indicators: 资金指标字典
            policy_indicators: 政策指标字典
            custom_weights: 自定义权重，None使用默认
            
        Returns:
            共振评分结果
        """
        weights = custom_weights or self.weights
        
        # 计算技术面得分
        tech_score = self.calculate_technical_score(
            rps_120=technical_indicators.get("rps_120", 50),
            rps_250=technical_indicators.get("rps_250", 50),
            price_trend=technical_indicators.get("price_trend", 0.5),
            volume_trend=technical_indicators.get("volume_trend", 0.5),
            ma_alignment=technical_indicators.get("ma_alignment", False),
            breakout_signal=technical_indicators.get("breakout_signal", False)
        )
        
        # 计算资金面得分
        capital_score = self.calculate_capital_score(
            fund_flow_score=capital_indicators.get("fund_flow", 0.5),
            northbound_flow=capital_indicators.get("northbound_flow", 0.5),
            institutional_score=capital_indicators.get("institutional", 0.5),
            margin_balance_trend=capital_indicators.get("margin_trend", 0.0),
            turnover_rate=capital_indicators.get("turnover_rate", 0.0)
        )
        
        # 计算政策面得分
        policy_score = self.calculate_policy_score(
            sector_policy_score=policy_indicators.get("sector_score", 0.5),
            policy_news=policy_indicators.get("news", []),
            policy_sentiment=policy_indicators.get("sentiment")
        )
        
        # 计算加权总分
        total_score = (
            tech_score * weights.technical_weight +
            capital_score * weights.capital_weight +
            policy_score * weights.policy_weight
        )
        
        sub_scores = SubScores(
            technical_score=tech_score,
            capital_score=capital_score,
            policy_score=policy_score
        )
        
        # 生成备注
        notes = self._generate_notes(tech_score, capital_score, policy_score)
        
        return ResonanceResult(
            ts_code=ts_code,
            name=name,
            total_score=total_score,
            sub_scores=sub_scores,
            weights=weights,
            market_phase=self.market_phase,
            notes=notes
        )
    
    def _generate_notes(
        self,
        tech_score: float,
        capital_score: float,
        policy_score: float
    ) -> str:
        """生成评分备注"""
        notes = []
        
        if tech_score >= 80:
            notes.append("技术面强势")
        elif tech_score <= 40:
            notes.append("技术面弱势")
        
        if capital_score >= 80:
            notes.append("资金持续流入")
        elif capital_score <= 40:
            notes.append("资金流出")
        
        if policy_score >= 80:
            notes.append("政策利好")
        elif policy_score <= 40:
            notes.append("政策承压")
        
        return "; ".join(notes) if notes else ""
    
    def rank_stocks(
        self,
        results: List[ResonanceResult],
        min_score: float = 60.0,
        top_n: Optional[int] = None
    ) -> List[ResonanceResult]:
        """
        对股票进行排名
        
        Args:
            results: 共振评分结果列表
            min_score: 最低分数要求
            top_n: 返回前N名，None返回所有
            
        Returns:
            排名后的结果列表
        """
        # 过滤低分股票
        filtered = [r for r in results if r.total_score >= min_score]
        
        # 按总分排序
        sorted_results = sorted(
            filtered,
            key=lambda x: x.total_score,
            reverse=True
        )
        
        # 添加排名
        for i, result in enumerate(sorted_results, 1):
            result.rank = i
        
        # 返回前N名
        if top_n:
            return sorted_results[:top_n]
        
        return sorted_results
