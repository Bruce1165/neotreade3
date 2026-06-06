# Universe 逐步扩大 + 热门板块结合方案

## 问题分析

当前问题：
- universe=100 只股票 → 过拟合、因子漂移
- 数据库有 5017 只股票可用
- 需要逐步扩大，同时结合热门板块信息

## 方案设计

### 阶段1：基础扩大（已完成）
- universe=100 → 200 → 500
- 按成交额排序选取
- 验证模型稳定性

### 阶段2：热门板块加权采样

**核心思想**：
- 不完全随机扩大，而是根据板块热度加权
- 热门板块多采样，冷门板块少采样
- 保持 universe 大小的同时，提高样本质量

**实现方式**：

```python
# 1. 获取热门板块
hot_sectors = get_hot_sectors(date)  # Top 10 板块

# 2. 计算板块权重
sector_weights = {}
for sector in all_sectors:
    if sector in hot_sectors:
        sector_weights[sector] = 2.0  # 热门板块权重×2
    else:
        sector_weights[sector] = 1.0

# 3. 加权采样
selected_stocks = []
for sector in all_sectors:
    n_samples = int(base_count * sector_weights[sector] / sum_weights)
    sector_stocks = get_stocks_by_sector(sector, date, limit=n_samples)
    selected_stocks.extend(sector_stocks)
```

### 阶段3：分层次 Universe

**三层结构**：

| 层次 | 数量 | 选取标准 | 作用 |
|------|------|---------|------|
| 核心层 | 200 | 全市场成交额 Top 200 | 保证流动性 |
| 板块层 | 300 | 热门板块龙头股 | 捕捉热点 |
| 扩展层 | 500 | 中军股 + 高波动股 | 增加多样性 |
| **总计** | **1000** | | |

### 阶段4：动态 Universe

**根据市场阶段调整**：

- **牛市**：扩大至 1500-2000 只，捕捉更多机会
- **震荡市**：保持 800-1000 只，平衡风险收益
- **熊市**：收缩至 300-500 只，聚焦核心资产

## 实施计划

### 实验设计

| 实验 | Universe | 采样方式 | 预期效果 |
|------|----------|---------|---------|
| 1 | 200 | 纯成交额 | 基准对比 |
| 2 | 500 | 纯成交额 | 验证扩大效果 |
| 3 | 500 | 热门板块加权 | 验证板块策略 |
| 4 | 1000 | 分层采样 | 综合效果 |
| 5 | 1000 | 热门板块加权 | 最优组合 |
| 6 | 2000 | 分层+加权 | 极限测试 |

### 评估指标

1. **准确率稳定性**：多次运行标准差 < 2%
2. **因子稳定性**：特征重要性变化 < 20%
3. **样本外泛化**：不同时间段准确率差异 < 5%

## 代码实现要点

### 1. 添加板块信息到采样
```python
# train.py 修改
UNIVERSE_SIZE = 500
USE_SECTOR_WEIGHTING = True  # 是否使用板块加权
SECTOR_BOOST_FACTOR = 2.0    # 热门板块权重倍数
```

### 2. 修改采样逻辑
```python
def sample_universe(conn, date, size, use_sector_weight=False):
    if not use_sector_weight:
        # 原逻辑：纯成交额
        return sample_by_amount(conn, date, size)
    
    # 新逻辑：板块加权
    hot_sectors = get_hot_sectors(conn, date)
    return sample_sector_weighted(conn, date, size, hot_sectors)
```

### 3. 热门板块获取
```python
def get_hot_sectors(conn, date, top_n=10):
    """获取当日热门板块（基于板块成交额和涨幅）"""
    cursor = conn.execute("""
        SELECT sector_lv1, AVG(amount) as avg_amount, AVG(pct_change) as avg_change
        FROM daily_prices dp
        JOIN stocks s ON dp.code = s.code
        WHERE dp.trade_date = ?
        GROUP BY sector_lv1
        ORDER BY avg_amount * (1 + avg_change/100) DESC
        LIMIT ?
    """, (date.isoformat(), top_n))
    return [row[0] for row in cursor.fetchall()]
```

## 下一步行动

1. 等待当前 universe=500/1000 实验完成
2. 根据结果决定是否实施板块加权
3. 如果效果好，继续测试 2000 只
4. 最终确定最优 universe 策略
