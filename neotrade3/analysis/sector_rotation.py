"""
板块轮动与RPS模块

提供板块轮动分析和相对强度（RPS）计算功能。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import logging
import sqlite3

logger = logging.getLogger(__name__)


# 政策主线板块映射
POLICY_MAINLINE_SECTORS = {
    "AI": ["人工智能", "计算机", "软件服务", "云计算", "大数据"],
    "AiDC": ["AIDC", "AiDC", "算力", "数据中心", "IDC", "服务器", "液冷", "光模块", "通信设备"],
    "储能": ["储能", "电池", "锂电池", "钠离子电池", "固态电池"],
    "新能源": ["新能源", "光伏", "风电", "新能源汽车", "充电桩"],
    "新材料": ["新材料", "稀土", "碳纤维", "高端材料", "特种材料"],
    "国产替代": ["半导体", "芯片", "集成电路", "光刻机", "电子元器件", "信创", "国产软件", "操作系统", "数据库", "工业软件"]
}


@dataclass
class SectorRPS:
    """板块RPS数据"""
    sector_name: str
    rps_20: float
    rps_60: float
    rps_120: float
    return_20d: float
    return_60d: float
    is_mainline: bool = False
    mainline_category: Optional[str] = None


@dataclass
class StockRPS:
    """个股RPS数据"""
    ts_code: str
    name: str
    sector: str
    rps_20: float
    rps_60: float
    rps_120: float
    rps_250: float
    composite_rps: float
    rank_in_sector: int = 0
    overall_rank: int = 0


@dataclass
class SectorRotationResult:
    """板块轮动分析结果"""
    analysis_date: str
    top_sectors: List[SectorRPS]
    weakening_sectors: List[SectorRPS]
    mainline_sectors: List[SectorRPS]
    emerging_sectors: List[SectorRPS]
    rotation_signal: str  # "accelerating", "stable", "reversing"
    market_context: Dict = field(default_factory=dict)


class SectorRotationAnalyzer:
    """板块轮动分析器"""
    
    def __init__(self, db_path: str):
        """
        初始化板块轮动分析器
        
        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
    
    def analyze(
        self,
        target_date: str,
        lookback_days: int = 120,
        top_n_sectors: int = 10
    ) -> SectorRotationResult:
        """
        分析板块轮动
        
        Args:
            target_date: 目标日期 (YYYY-MM-DD)
            lookback_days: 回看天数
            top_n_sectors: 返回前N板块
            
        Returns:
            板块轮动分析结果
        """
        # 计算板块收益率
        sector_returns = self._calc_sector_returns(target_date, lookback_days)
        
        # 计算板块RPS
        sector_rps_list = self._calc_sector_rps(sector_returns)
        
        # 标记政策主线板块
        for sr in sector_rps_list:
            for category, sectors in POLICY_MAINLINE_SECTORS.items():
                if any(keyword in sr.sector_name for keyword in sectors):
                    sr.is_mainline = True
                    sr.mainline_category = category
                    break
        
        # 排序并分类
        sorted_by_rps = sorted(
            sector_rps_list,
            key=lambda x: x.rps_120,
            reverse=True
        )
        
        top_sectors = sorted_by_rps[:top_n_sectors]
        
        # 识别弱势板块（RPS下降）
        weakening_sectors = [
            s for s in sector_rps_list
            if s.rps_20 < s.rps_60 < s.rps_120
        ]
        weakening_sectors.sort(key=lambda x: x.rps_20)
        weakening_sectors = weakening_sectors[:5]
        
        # 识别政策主线板块
        mainline_sectors = [s for s in sector_rps_list if s.is_mainline]
        mainline_sectors.sort(key=lambda x: x.rps_120, reverse=True)
        
        # 识别新兴板块（RPS快速上升）
        emerging_sectors = [
            s for s in sector_rps_list
            if s.rps_20 > s.rps_60 and s.rps_20 > 70
        ]
        emerging_sectors.sort(key=lambda x: x.rps_20 - x.rps_60, reverse=True)
        emerging_sectors = emerging_sectors[:5]
        
        # 判断轮动信号
        rotation_signal = self._determine_rotation_signal(sector_rps_list)
        
        return SectorRotationResult(
            analysis_date=target_date,
            top_sectors=top_sectors,
            weakening_sectors=weakening_sectors,
            mainline_sectors=mainline_sectors,
            emerging_sectors=emerging_sectors,
            rotation_signal=rotation_signal,
            market_context={
                "total_sectors": len(sector_rps_list),
                "mainline_count": len(mainline_sectors)
            }
        )
    
    def _calc_sector_returns(
        self,
        target_date: str,
        lookback_days: int
    ) -> Dict[str, Dict[int, float]]:
        """
        计算各板块收益率
        
        Args:
            target_date: 目标日期
            lookback_days: 回看天数
            
        Returns:
            {sector: {period: return}}字典
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 计算日期范围
            target_dt = datetime.strptime(target_date, "%Y-%m-%d")
            start_dt = target_dt - timedelta(days=lookback_days * 2)
            start_date = start_dt.strftime("%Y-%m-%d")
            
            # 查询板块数据
            cursor.execute("""
                SELECT s.sector_lv1 AS industry, d.trade_date, AVG(d.close) as avg_close
                FROM daily_prices d
                JOIN stocks s ON d.code = s.code
                WHERE d.trade_date BETWEEN ? AND ?
                  AND s.sector_lv1 IS NOT NULL
                GROUP BY s.sector_lv1, d.trade_date
                ORDER BY s.sector_lv1, d.trade_date
            """, (start_date, target_date))
            
            rows = cursor.fetchall()
            conn.close()
            
            # 按板块组织数据
            sector_prices = {}
            for industry, trade_date, avg_close in rows:
                if industry not in sector_prices:
                    sector_prices[industry] = []
                sector_prices[industry].append((trade_date, avg_close))
            
            # 计算收益率
            sector_returns = {}
            for sector, prices in sector_prices.items():
                if len(prices) < 20:
                    continue
                
                price_dict = {p[0]: p[1] for p in prices}
                dates = sorted(price_dict.keys())
                
                if len(dates) < 20:
                    continue
                
                current_price = price_dict[dates[-1]]
                
                returns = {}
                for period in [20, 60, 120]:
                    if len(dates) > period:
                        past_price = price_dict[dates[-(period + 1)]]
                        if past_price > 0:
                            returns[period] = (current_price - past_price) / past_price
                        else:
                            returns[period] = 0.0
                    else:
                        returns[period] = 0.0
                
                sector_returns[sector] = returns
            
            return sector_returns
            
        except Exception as e:
            logger.warning("计算板块收益率时出错: target_date=%s error=%s", target_date, e)
            return {}
    
    def _calc_sector_rps(
        self,
        sector_returns: Dict[str, Dict[int, float]]
    ) -> List[SectorRPS]:
        """
        计算板块RPS
        
        Args:
            sector_returns: 板块收益率字典
            
        Returns:
            SectorRPS列表
        """
        if not sector_returns:
            return []
        
        sector_rps_list = []
        
        for period in [20, 60, 120]:
            # 收集该周期的收益率
            period_returns = []
            for sector, returns in sector_returns.items():
                if period in returns:
                    period_returns.append((sector, returns[period]))
            
            if not period_returns:
                continue
            
            # 排序并计算RPS
            sorted_returns = sorted(
                period_returns,
                key=lambda x: x[1],
                reverse=True
            )
            
            total = len(sorted_returns)
            for rank, (sector, ret) in enumerate(sorted_returns, 1):
                rps = (1 - rank / total) * 100
                
                # 查找或创建SectorRPS
                existing = next(
                    (s for s in sector_rps_list if s.sector_name == sector),
                    None
                )
                
                if existing is None:
                    sr = SectorRPS(
                        sector_name=sector,
                        rps_20=0.0,
                        rps_60=0.0,
                        rps_120=0.0,
                        return_20d=0.0,
                        return_60d=0.0
                    )
                    if period == 20:
                        sr.rps_20 = rps
                        sr.return_20d = ret
                    elif period == 60:
                        sr.rps_60 = rps
                        sr.return_60d = ret
                    elif period == 120:
                        sr.rps_120 = rps
                    sector_rps_list.append(sr)
                else:
                    if period == 20:
                        existing.rps_20 = rps
                        existing.return_20d = ret
                    elif period == 60:
                        existing.rps_60 = rps
                        existing.return_60d = ret
                    elif period == 120:
                        existing.rps_120 = rps
        
        return sector_rps_list
    
    def _check_mainline(
        self,
        sector_name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        检查是否为政策主线板块
        
        Args:
            sector_name: 板块名称
            
        Returns:
            (是否主线, 主线类别)
        """
        for category, keywords in POLICY_MAINLINE_SECTORS.items():
            if any(keyword in sector_name for keyword in keywords):
                return True, category
        return False, None
    
    def _calc_stock_rps(
        self,
        target_date: str,
        sector: Optional[str] = None,
        top_n: int = 100
    ) -> List[StockRPS]:
        """
        计算个股RPS
        
        Args:
            target_date: 目标日期
            sector: 指定板块，None表示全市场
            top_n: 返回前N名
            
        Returns:
            StockRPS列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            target_dt = datetime.strptime(target_date, "%Y-%m-%d")
            
            # 构建查询
            if sector:
                cursor.execute("""
                    SELECT d.code, s.name, s.sector_lv1 AS industry,
                           d.close, d.trade_date
                    FROM daily_prices d
                    JOIN stocks s ON d.code = s.code
                    WHERE s.sector_lv1 = ? AND d.trade_date <= ?
                    ORDER BY d.code, d.trade_date DESC
                """, (sector, target_date))
            else:
                cursor.execute("""
                    SELECT d.code, s.name, s.sector_lv1 AS industry,
                           d.close, d.trade_date
                    FROM daily_prices d
                    JOIN stocks s ON d.code = s.code
                    WHERE d.trade_date <= ?
                    ORDER BY d.code, d.trade_date DESC
                """, (target_date,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # 组织数据
            stock_data = {}
            for code, name, industry, close, trade_date in rows:
                if code not in stock_data:
                    stock_data[code] = {
                        "name": name,
                        "sector": industry,
                        "prices": []
                    }
                stock_data[code]["prices"].append((trade_date, close))
            
            # 计算RPS
            stock_returns = []
            for code, data in stock_data.items():
                prices = data["prices"]
                if len(prices) < 250:
                    continue
                
                current_price = prices[0][1]
                returns = {}
                
                for period in [20, 60, 120, 250]:
                    if len(prices) > period:
                        past_price = prices[period][1]
                        if past_price > 0:
                            returns[period] = (current_price - past_price) / past_price
                        else:
                            returns[period] = 0.0
                
                if returns:
                    stock_returns.append({
                        "ts_code": code,
                        "name": data["name"],
                        "sector": data["sector"],
                        "returns": returns
                    })
            
            # 计算RPS分数
            stock_rps_list = []
            for period in [20, 60, 120, 250]:
                period_returns = [
                    (s["ts_code"], s["returns"].get(period, 0))
                    for s in stock_returns
                    if period in s["returns"]
                ]
                
                if not period_returns:
                    continue
                
                sorted_returns = sorted(
                    period_returns,
                    key=lambda x: x[1],
                    reverse=True
                )
                
                total = len(sorted_returns)
                for rank, (ts_code, _) in enumerate(sorted_returns, 1):
                    rps = (1 - rank / total) * 100
                    
                    existing = next(
                        (s for s in stock_rps_list if s.ts_code == ts_code),
                        None
                    )
                    
                    stock_info = next(
                        (s for s in stock_returns if s["ts_code"] == ts_code),
                        None
                    )
                    
                    if existing is None and stock_info:
                        sr = StockRPS(
                            ts_code=ts_code,
                            name=stock_info["name"],
                            sector=stock_info["sector"],
                            rps_20=0.0,
                            rps_60=0.0,
                            rps_120=0.0,
                            rps_250=0.0,
                            composite_rps=0.0
                        )
                        setattr(sr, f"rps_{period}", rps)
                        stock_rps_list.append(sr)
                    elif existing:
                        setattr(existing, f"rps_{period}", rps)
            
            # 计算综合RPS
            for sr in stock_rps_list:
                sr.composite_rps = (
                    sr.rps_20 * 0.1 +
                    sr.rps_60 * 0.2 +
                    sr.rps_120 * 0.3 +
                    sr.rps_250 * 0.4
                )
            
            # 排序并返回
            stock_rps_list.sort(key=lambda x: x.composite_rps, reverse=True)
            
            # 添加排名
            for i, sr in enumerate(stock_rps_list, 1):
                sr.overall_rank = i
            
            return stock_rps_list[:top_n]
            
        except Exception as e:
            logger.warning("计算个股RPS时出错: target_date=%s sector=%s error=%s", target_date, sector, e)
            return []
    
    def _determine_rotation_signal(
        self,
        sector_rps_list: List[SectorRPS]
    ) -> str:
        """
        确定轮动信号
        
        Args:
            sector_rps_list: 板块RPS列表
            
        Returns:
            轮动信号
        """
        if len(sector_rps_list) < 5:
            return "unknown"
        
        # 计算领先板块的变化
        top_sectors = sorted(
            sector_rps_list,
            key=lambda x: x.rps_120,
            reverse=True
        )[:10]
        
        # 检查RPS变化趋势
        increasing_count = sum(
            1 for s in top_sectors if s.rps_20 > s.rps_60
        )
        
        if increasing_count >= 7:
            return "accelerating"
        elif increasing_count <= 3:
            return "reversing"
        else:
            return "stable"


def get_sector_rotation_summary(
    result: SectorRotationResult
) -> Dict:
    """
    获取板块轮动摘要
    
    Args:
        result: 板块轮动分析结果
        
    Returns:
        摘要字典
    """
    summary = {
        "analysis_date": result.analysis_date,
        "rotation_signal": result.rotation_signal,
        "total_sectors": result.market_context.get("total_sectors", 0),
        "mainline_count": len(result.mainline_sectors),
        "top_sectors": [s.sector_name for s in result.top_sectors[:5]],
        "mainline_sectors": [
            {
                "name": s.sector_name,
                "category": s.mainline_category,
                "rps_120": round(s.rps_120, 2)
            }
            for s in result.mainline_sectors[:5]
        ],
        "emerging_sectors": [s.sector_name for s in result.emerging_sectors[:3]],
        "weakening_sectors": [s.sector_name for s in result.weakening_sectors[:3]]
    }
    
    return summary
