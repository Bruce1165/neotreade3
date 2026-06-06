# ML Autore Research Program

## 目标
优化股票预测模型的样本外准确率 (out_of_sample_accuracy)。

## 评估指标
- **主指标**: out_of_sample_accuracy (April 2025 数据上的准确率)
- **参考指标**: 样本内 accuracy, precision, recall, F1

## 当前 Baseline
accuracy = 0.7183 (MAX_DEPTH=15, N_ESTIMATORS=300)

## 实验协议
1. 修改 train.py 中的超参数或特征开关
2. 运行: `python neotrade3/ml/autore/train.py`
3. 读取输出的 out_of_sample_accuracy
4. 比较与 baseline 的差异
5. 如果改进: 记录成功，更新 BASELINE.txt
6. 如果退步: 记录失败 (FAILED.md)，git revert
7. 继续下一轮实验

## 搜索空间

### 模型参数
- `N_ESTIMATORS`: [50, 100, 200, 300, 500]
- `MAX_DEPTH`: [10, 12, 15, 18, 20, None]
- `MIN_SAMPLES_SPLIT`: [5, 10, 15, 20]
- `MIN_SAMPLES_LEAF`: [2, 3, 5, 8, 10]

### 训练参数
- `LOOKBACK_DAYS`: [90, 120, 150, 180] ← 注意: 90天已验证无效
- `THRESHOLD_UP`: [1.5, 2.0, 2.5, 3.0]
- `THRESHOLD_DOWN`: [-1.5, -2.0, -2.5, -3.0]

### 特征开关
- `USE_RSI`: True/False
- `USE_MACD`: True/False
- `USE_BOLLINGER`: True/False
- `USE_VOLATILITY_REGIME`: True/False
- `USE_MARKET_BREADTH`: True/False

## 探索记录

### 已验证 (有效)
- [x] MAX_DEPTH=15 → +8.33% improvement (0.635 → 0.718)

### 已验证 (无效)
- [x] LOOKBACK_DAYS=90 → -15.99% regression

### 待探索
- [ ] N_ESTIMATORS=500 (更多树)
- [ ] MAX_DEPTH=18 或 20 (更深)
- [ ] MIN_SAMPLES_LEAF=8 或 10 (更大叶节点，减少过拟合)
- [ ] 只保留最重要的特征 (移除 RSI/MACD)
- [ ] 扩大阈值范围到 ±1.5%
- [ ] 组合优化

## 禁止事项
- 不要修改 DB_PATH
- 不要修改 OUTPUT_FILE 路径
- 不要修改评估逻辑 (out_of_sample_test 函数)
- 不要回退到 LOOKBACK_DAYS=90

## 下一步建议
1. 尝试 N_ESTIMATORS=500
2. 尝试 MAX_DEPTH=18
3. 尝试 MIN_SAMPLES_LEAF=8 (减少过拟合)
