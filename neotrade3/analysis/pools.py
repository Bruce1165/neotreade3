"""
股票池管理模块

提供股票池的构建、管理和维护功能，包括杯柄形态池和量化因子池。
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, date
import sqlite3
import json


class PoolStatus(Enum):
    """股票池成员状态枚举"""
    ACTIVE = "active"       # 活跃
    GRADUATED = "graduated" # 毕业（已触发买入）
    FAILED = "failed"       # 失败（跌破止损）
    EXITED = "exited"       # 已退出


@dataclass
class PoolMember:
    """股票池成员"""
    ts_code: str
    name: str
    sector: str
    enter_date: date
    enter_price: float
    status: PoolStatus = PoolStatus.ACTIVE
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    cup_depth: Optional[float] = None
    handle_depth: Optional[float] = None
    rps_120: Optional[float] = None
    rps_250: Optional[float] = None
    notes: str = ""
    
    @property
    def cup_depth_pct(self) -> Optional[float]:
        """杯深百分比"""
        if self.cup_depth is not None and self.enter_price > 0:
            return self.cup_depth / self.enter_price
        return None
    
    @property
    def days_in_pool(self) -> int:
        """在池天数"""
        end_date = self.exit_date or date.today()
        return (end_date - self.enter_date).days
    
    @property
    def return_pct(self) -> Optional[float]:
        """收益率"""
        if self.exit_price is not None:
            return (self.exit_price - self.enter_price) / self.enter_price
        return None


@dataclass
class PoolSnapshot:
    """股票池快照"""
    snapshot_date: date
    pool_type: str
    total_count: int
    active_count: int
    graduated_count: int
    failed_count: int
    exited_count: int
    members: List[PoolMember] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PoolManager:
    """股票池管理器"""
    
    def __init__(self, db_path: str):
        """
        初始化股票池管理器
        
        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """确保必要的表存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 股票池成员表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pool_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL,
                name TEXT,
                sector TEXT,
                pool_type TEXT NOT NULL,
                enter_date TEXT NOT NULL,
                enter_price REAL NOT NULL,
                status TEXT DEFAULT 'active',
                exit_date TEXT,
                exit_price REAL,
                cup_depth REAL,
                handle_depth REAL,
                rps_120 REAL,
                rps_250 REAL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 股票池快照表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pool_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                pool_type TEXT NOT NULL,
                total_count INTEGER DEFAULT 0,
                active_count INTEGER DEFAULT 0,
                graduated_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                exited_count INTEGER DEFAULT 0,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def build_pool(
        self,
        pool_type: str,
        candidates: List[Dict[str, Any]],
        entry_date: date
    ) -> List[PoolMember]:
        """
        构建股票池
        
        Args:
            pool_type: 股票池类型
            candidates: 候选股票列表
            entry_date: 入场日期
            
        Returns:
            PoolMember列表
        """
        members = []
        
        for candidate in candidates:
            member = PoolMember(
                ts_code=candidate.get("ts_code", ""),
                name=candidate.get("name", ""),
                sector=candidate.get("sector", ""),
                enter_date=entry_date,
                enter_price=candidate.get("price", 0.0),
                status=PoolStatus.ACTIVE,
                cup_depth=candidate.get("cup_depth"),
                handle_depth=candidate.get("handle_depth"),
                rps_120=candidate.get("rps_120"),
                rps_250=candidate.get("rps_250"),
                notes=candidate.get("notes", "")
            )
            members.append(member)
        
        return members
    
    def build_cup_handle_pool_from_screener(
        self,
        screener_results: List[Dict[str, Any]],
        entry_date: date,
        min_cup_depth: float = 0.15,
        max_cup_depth: float = 0.50,
        min_handle_depth: float = 0.05,
        max_handle_depth: float = 0.15
    ) -> List[PoolMember]:
        """
        从杯柄筛选结果构建股票池
        
        Args:
            screener_results: 筛选器结果
            entry_date: 入场日期
            min_cup_depth: 最小杯深
            max_cup_depth: 最大杯深
            min_handle_depth: 最小柄深
            max_handle_depth: 最大柄深
            
        Returns:
            PoolMember列表
        """
        filtered = []
        
        for result in screener_results:
            cup_depth = result.get("cup_depth", 0)
            handle_depth = result.get("handle_depth", 0)
            
            # 过滤符合条件的杯柄形态
            if (min_cup_depth <= cup_depth <= max_cup_depth and
                min_handle_depth <= handle_depth <= max_handle_depth):
                filtered.append(result)
        
        return self.build_pool("cup_handle", filtered, entry_date)
    
    def build_quant_pool_from_factor_matrix(
        self,
        factor_matrix: Dict[str, Dict[str, float]],
        entry_date: date,
        top_n: int = 50,
        min_score: float = 0.6
    ) -> List[PoolMember]:
        """
        从因子矩阵构建量化股票池
        
        Args:
            factor_matrix: 因子矩阵 {ts_code: {factor: value}}
            entry_date: 入场日期
            top_n: 选取前N名
            min_score: 最低分数
            
        Returns:
            PoolMember列表
        """
        # 计算综合得分
        scored_stocks = []
        
        for ts_code, factors in factor_matrix.items():
            # 简单的加权平均得分计算
            score = 0.0
            weight_sum = 0.0
            
            for factor, value in factors.items():
                weight = 1.0  # 默认权重
                if "rps" in factor.lower():
                    weight = 1.5
                elif "momentum" in factor.lower():
                    weight = 1.2
                
                score += value * weight
                weight_sum += weight
            
            if weight_sum > 0:
                score /= weight_sum
            
            if score >= min_score:
                scored_stocks.append({
                    "ts_code": ts_code,
                    "score": score,
                    "factors": factors
                })
        
        # 排序并选取前N名
        scored_stocks.sort(key=lambda x: x["score"], reverse=True)
        top_stocks = scored_stocks[:top_n]
        
        # 获取价格信息
        candidates = []
        for stock in top_stocks:
            candidates.append({
                "ts_code": stock["ts_code"],
                "name": "",
                "sector": "",
                "price": 0.0,  # 需要从数据库查询
                "notes": f"Score: {stock['score']:.3f}"
            })
        
        # 从数据库丰富信息
        candidates = self._enrich_candidates_from_db(candidates, entry_date)
        
        return self.build_pool("quant", candidates, entry_date)
    
    def build_all_pools(
        self,
        entry_date: date,
        screener_results: Optional[List[Dict]] = None,
        factor_matrix: Optional[Dict] = None
    ) -> Dict[str, List[PoolMember]]:
        """
        构建所有股票池
        
        Args:
            entry_date: 入场日期
            screener_results: 筛选器结果
            factor_matrix: 因子矩阵
            
        Returns:
            {pool_type: members}字典
        """
        pools = {}
        
        if screener_results:
            pools["cup_handle"] = self.build_cup_handle_pool_from_screener(
                screener_results, entry_date
            )
        
        if factor_matrix:
            pools["quant"] = self.build_quant_pool_from_factor_matrix(
                factor_matrix, entry_date
            )
        
        return pools
    
    def save_pool_snapshot(
        self,
        pool_type: str,
        members: List[PoolMember],
        snapshot_date: Optional[date] = None
    ) -> int:
        """
        保存股票池快照
        
        Args:
            pool_type: 股票池类型
            members: 成员列表
            snapshot_date: 快照日期
            
        Returns:
            快照ID
        """
        if snapshot_date is None:
            snapshot_date = date.today()
        
        # 统计各状态数量
        active_count = sum(1 for m in members if m.status == PoolStatus.ACTIVE)
        graduated_count = sum(1 for m in members if m.status == PoolStatus.GRADUATED)
        failed_count = sum(1 for m in members if m.status == PoolStatus.FAILED)
        exited_count = sum(1 for m in members if m.status == PoolStatus.EXITED)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 保存快照
        cursor.execute("""
            INSERT INTO pool_snapshots
            (snapshot_date, pool_type, total_count, active_count, 
             graduated_count, failed_count, exited_count, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot_date.isoformat(),
            pool_type,
            len(members),
            active_count,
            graduated_count,
            failed_count,
            exited_count,
            json.dumps({"avg_cup_depth": 0.0})  # 可扩展更多元数据
        ))
        
        snapshot_id = cursor.lastrowid
        
        # 保存成员
        for member in members:
            cursor.execute("""
                INSERT INTO pool_members
                (ts_code, name, sector, pool_type, enter_date, enter_price,
                 status, exit_date, exit_price, cup_depth, handle_depth,
                 rps_120, rps_250, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                member.ts_code,
                member.name,
                member.sector,
                pool_type,
                member.enter_date.isoformat(),
                member.enter_price,
                member.status.value,
                member.exit_date.isoformat() if member.exit_date else None,
                member.exit_price,
                member.cup_depth,
                member.handle_depth,
                member.rps_120,
                member.rps_250,
                member.notes
            ))
        
        conn.commit()
        conn.close()
        
        return snapshot_id
    
    def _load_active_members(
        self,
        pool_type: Optional[str] = None
    ) -> List[PoolMember]:
        """
        加载活跃成员
        
        Args:
            pool_type: 股票池类型，None表示所有
            
        Returns:
            PoolMember列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if pool_type:
            cursor.execute("""
                SELECT ts_code, name, sector, enter_date, enter_price,
                       status, exit_date, exit_price, cup_depth, handle_depth,
                       rps_120, rps_250, notes
                FROM pool_members
                WHERE status = 'active' AND pool_type = ?
                ORDER BY enter_date DESC
            """, (pool_type,))
        else:
            cursor.execute("""
                SELECT ts_code, name, sector, enter_date, enter_price,
                       status, exit_date, exit_price, cup_depth, handle_depth,
                       rps_120, rps_250, notes
                FROM pool_members
                WHERE status = 'active'
                ORDER BY enter_date DESC
            """)
        
        rows = cursor.fetchall()
        conn.close()
        
        members = []
        for row in rows:
            member = PoolMember(
                ts_code=row[0],
                name=row[1] or "",
                sector=row[2] or "",
                enter_date=datetime.fromisoformat(row[3]).date(),
                enter_price=row[4],
                status=PoolStatus(row[5]),
                exit_date=datetime.fromisoformat(row[6]).date() if row[6] else None,
                exit_price=row[7],
                cup_depth=row[8],
                handle_depth=row[9],
                rps_120=row[10],
                rps_250=row[11],
                notes=row[12] or ""
            )
            members.append(member)
        
        return members
    
    def _enrich_candidates_from_db(
        self,
        candidates: List[Dict[str, Any]],
        target_date: date
    ) -> List[Dict[str, Any]]:
        """
        从数据库丰富候选股票信息
        
        Args:
            candidates: 候选列表
            target_date: 目标日期
            
        Returns:
            丰富后的候选列表
        """
        if not candidates:
            return candidates
        
        ts_codes = [c["ts_code"] for c in candidates]
        chunk_size = 900
        basic_info: Dict[str, Dict[str, Any]] = {}
        price_info: Dict[str, Any] = {}

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            for offset in range(0, len(ts_codes), chunk_size):
                chunk = ts_codes[offset : offset + chunk_size]
                if not chunk:
                    continue
                placeholders = ",".join(["?"] * len(chunk))
                cursor.execute(
                    f"""
                    SELECT ts_code, name, industry
                    FROM stock_basic
                    WHERE ts_code IN ({placeholders})
                    """,
                    chunk,
                )
                for ts_code, name, industry in cursor.fetchall():
                    basic_info[str(ts_code)] = {"name": name, "sector": industry}

            for offset in range(0, len(ts_codes), chunk_size):
                chunk = ts_codes[offset : offset + chunk_size]
                if not chunk:
                    continue
                placeholders = ",".join(["?"] * len(chunk))
                cursor.execute(
                    f"""
                    SELECT ts_code, close
                    FROM daily
                    WHERE ts_code IN ({placeholders}) AND trade_date <= ?
                    ORDER BY ts_code, trade_date DESC
                    """,
                    chunk + [target_date.isoformat()],
                )
                for ts_code, close in cursor.fetchall():
                    key = str(ts_code)
                    if key not in price_info:
                        price_info[key] = close
        finally:
            conn.close()
        
        # 丰富信息
        for candidate in candidates:
            ts_code = candidate["ts_code"]
            if ts_code in basic_info:
                candidate["name"] = basic_info[ts_code]["name"]
                candidate["sector"] = basic_info[ts_code]["sector"]
            if ts_code in price_info:
                candidate["price"] = price_info[ts_code]
        
        return candidates
