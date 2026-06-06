#!/usr/bin/env python3
"""
基本面数据适配器 - 从数据库获取 PE、ROE、PB 等数据

数据已存在于 stocks 表中（来自 ifind 数据源）
"""

import sqlite3
import logging
from pathlib import Path
from datetime import date, datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class FundamentalDataAdapter:
    """基本面数据适配器 - 从 stocks 表获取"""
    
    def __init__(self, db_path: Path = Path("var/db/stock_data.db")):
        self.db_path = db_path
        
    def _get_db_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(str(self.db_path))
    
    def get_fundamental_data(self, code: str) -> Optional[Dict]:
        """
        从 stocks 表获取基本面数据
        
        Returns:
            {
                'pe_ratio': float,      # 市盈率
                'pb_ratio': float,      # 市净率
                'roe': float,           # 净资产收益率
                'revenue_growth': float, # 营收增长率
                'profit_growth': float,  # 利润增长率
                'eps': float,           # 每股收益
            }
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pe_ratio, pb_ratio, roe, revenue_growth, profit_growth, eps
            FROM stocks
            WHERE code = ? AND (is_delisted IS NULL OR is_delisted = 0)
        """, (code,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'pe_ratio': row[0],
                'pb_ratio': row[1],
                'roe': row[2],
                'revenue_growth': row[3],
                'profit_growth': row[4],
                'eps': row[5],
            }
        return None
    
    def calculate_peg(self, code: str) -> Optional[float]:
        """计算 PEG = PE / 盈利增速"""
        data = self.get_fundamental_data(code)
        if not data:
            return None
            
        pe = data.get('pe_ratio')
        growth = data.get('profit_growth')
        
        if pe and growth and growth > 0:
            return pe / growth
        return None


# 便捷函数
def get_fundamental_data(code: str, db_path: Path = Path("var/db/stock_data.db")) -> Optional[Dict]:
    """获取股票基本面数据"""
    adapter = FundamentalDataAdapter(db_path)
    return adapter.get_fundamental_data(code)


def calculate_peg(code: str, db_path: Path = Path("var/db/stock_data.db")) -> Optional[float]:
    """计算 PEG"""
    adapter = FundamentalDataAdapter(db_path)
    return adapter.calculate_peg(code)


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    # 测试获取数据
    test_code = "000001"
    data = get_fundamental_data(test_code)
    print(f"{test_code} 基本面数据: {data}")
    
    peg = calculate_peg(test_code)
    print(f"{test_code} PEG: {peg}")
