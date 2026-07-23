#!/usr/bin/env python3
"""
补采 2026-05-25 的日线数据
使用腾讯行情接口批量获取
"""

import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path
import time

# 项目路径
PROJECT_ROOT = Path("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3")
DB_PATH = PROJECT_ROOT / "var" / "db" / "stock_data.db"

# 腾讯接口基础URL
TENCENT_API_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

def get_stock_codes():
    """从数据库获取所有股票代码"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT code FROM stocks WHERE (is_delisted IS NULL OR is_delisted = 0)")
    codes = [row[0] for row in cursor.fetchall()]
    conn.close()
    return codes

def fetch_stock_data_tencent(code, date_str):
    """使用腾讯接口获取单只股票的历史数据"""
    # 转换代码格式
    if code.startswith('6'):
        tencent_code = f"sh{code}"
    elif code.startswith('0') or code.startswith('3'):
        tencent_code = f"sz{code}"
    else:
        return None
    
    url = f"{TENCENT_API_URL}?param={tencent_code},day,{date_str},{date_str},1,qfq"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            stock_data = data.get('data', {}).get(tencent_code, {})
            day_data = stock_data.get('day', [])
            
            if day_data and len(day_data) > 0:
                # day_data格式: [日期, 开盘, 收盘, 最低, 最高, 成交量]
                row = day_data[0]
                return {
                    'code': code,
                    'trade_date': row[0],
                    'open': float(row[1]),
                    'close': float(row[2]),
                    'low': float(row[3]),
                    'high': float(row[4]),
                    'volume': float(row[5]),
                }
    except Exception as e:
        print(f"获取 {code} 失败: {e}")
    
    return None

def insert_daily_prices(records):
    """批量插入日线数据"""
    if not records:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    inserted = 0
    for record in records:
        try:
            # 计算涨跌幅
            # 需要先获取前一天的收盘价
            cursor.execute(
                "SELECT close FROM daily_prices WHERE code = ? AND trade_date < ? ORDER BY trade_date DESC LIMIT 1",
                (record['code'], record['trade_date'])
            )
            prev_close_row = cursor.fetchone()
            
            if prev_close_row and prev_close_row[0]:
                preclose = prev_close_row[0]
                pct_change = (record['close'] - preclose) / preclose * 100
            else:
                preclose = record['close']  # 没有前一天数据时，用当天收盘价
                pct_change = 0
            
            # 计算成交额（估算：均价 * 成交量）
            avg_price = (record['open'] + record['close'] + record['high'] + record['low']) / 4
            amount = avg_price * record['volume']
            
            cursor.execute("""
                INSERT OR REPLACE INTO daily_prices 
                (code, trade_date, open, high, low, close, volume, amount, preclose, pct_change, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record['code'],
                record['trade_date'],
                record['open'],
                record['high'],
                record['low'],
                record['close'],
                record['volume'],
                amount,
                preclose,
                pct_change,
                datetime.now().isoformat()
            ))
            inserted += 1
            
            if inserted % 100 == 0:
                print(f"已插入 {inserted} 条数据...")
                conn.commit()
                
        except Exception as e:
            print(f"插入 {record['code']} 失败: {e}")
    
    conn.commit()
    conn.close()
    return inserted

def main():
    target_date = "2026-05-25"
    print(f"开始补采 {target_date} 的数据...")
    
    # 获取所有股票代码
    print("获取股票列表...")
    codes = get_stock_codes()
    print(f"共 {len(codes)} 只股票")
    
    # 分批获取数据
    batch_size = 100
    all_records = []
    failed_codes = []
    
    for i, code in enumerate(codes):
        print(f"[{i+1}/{len(codes)}] 获取 {code}...", end=' ')
        
        data = fetch_stock_data_tencent(code, target_date)
        if data:
            all_records.append(data)
            print(f"✓ 开盘:{data['open']:.2f} 收盘:{data['close']:.2f}")
        else:
            failed_codes.append(code)
            print("✗ 失败")
        
        # 每100只暂停一下，避免请求过快
        if (i + 1) % batch_size == 0:
            print(f"\n已处理 {i+1} 只，暂停2秒...")
            time.sleep(2)
    
    print(f"\n获取完成: 成功 {len(all_records)} 只，失败 {len(failed_codes)} 只")
    
    if failed_codes:
        print(f"失败的代码: {failed_codes[:10]}...")
    
    # 插入数据库
    print(f"\n开始插入数据库...")
    inserted = insert_daily_prices(all_records)
    print(f"成功插入 {inserted} 条记录")
    
    # 验证
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM daily_prices WHERE trade_date = ?", (target_date,))
    count = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n验证: 数据库中 {target_date} 共有 {count} 条记录")

if __name__ == "__main__":
    main()
