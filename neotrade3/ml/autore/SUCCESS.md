
## Successful Experiment
**Hypothesis**: 增加树深度到 15
**Config**: {'N_ESTIMATORS': 300, 'MAX_DEPTH': 15, 'MIN_SAMPLES_SPLIT': 10, 'MIN_SAMPLES_LEAF': 5, 'LOOKBACK_DAYS': 120, 'THRESHOLD_UP': 2, 'USE_RSI': True, 'USE_MACD': True, 'USE_BOLLINGER': True, 'USE_VOLATILITY_REGIME': True, 'USE_MARKET_BREADTH': True}
**Accuracy**: 0.7183 (baseline: 0.6350)
**Improvement**: +0.0833
**Time**: 2026-05-25T10:57:05.704817


## Successful Experiment
**Hypothesis**: 增加最小叶节点到 8，减少过拟合
**Config**: {'N_ESTIMATORS': 500, 'MAX_DEPTH': 15, 'MIN_SAMPLES_SPLIT': 10, 'MIN_SAMPLES_LEAF': 8, 'LOOKBACK_DAYS': 120, 'THRESHOLD_UP': 2, 'USE_RSI': True, 'USE_MACD': True, 'USE_BOLLINGER': True, 'USE_VOLATILITY_REGIME': True, 'USE_MARKET_BREADTH': True}
**Accuracy**: 0.7353 (baseline: 0.7183)
**Improvement**: +0.0170
**Time**: 2026-05-25T12:33:09.358241


## Successful Experiment
**Hypothesis**: 扩大阈值范围到 ±1.5%
**Config**: {'N_ESTIMATORS': 500, 'MAX_DEPTH': 15, 'MIN_SAMPLES_SPLIT': 10, 'MIN_SAMPLES_LEAF': 8, 'LOOKBACK_DAYS': 120, 'THRESHOLD_UP': 1, 'USE_RSI': True, 'USE_MACD': True, 'USE_BOLLINGER': True, 'USE_VOLATILITY_REGIME': True, 'USE_MARKET_BREADTH': True}
**Accuracy**: 0.7358 (baseline: 0.7353)
**Improvement**: +0.0005
**Time**: 2026-05-25T12:36:41.827905


## Successful Experiment
**Hypothesis**: 移除 RSI 特征
**Config**: {'N_ESTIMATORS': 500, 'MAX_DEPTH': 15, 'MIN_SAMPLES_SPLIT': 10, 'MIN_SAMPLES_LEAF': 8, 'LOOKBACK_DAYS': 120, 'THRESHOLD_UP': 1, 'USE_RSI': False, 'USE_MACD': True, 'USE_BOLLINGER': True, 'USE_VOLATILITY_REGIME': True, 'USE_MARKET_BREADTH': True}
**Accuracy**: 0.7407 (baseline: 0.7358)
**Improvement**: +0.0049
**Time**: 2026-05-25T12:40:11.122324


## Successful Experiment
**Hypothesis**: 组合优化: 300树+深度20
**Config**: {'N_ESTIMATORS': 300, 'MAX_DEPTH': 20, 'MIN_SAMPLES_SPLIT': 10, 'MIN_SAMPLES_LEAF': 8, 'LOOKBACK_DAYS': 120, 'THRESHOLD_UP': 1, 'USE_RSI': False, 'USE_MACD': True, 'USE_BOLLINGER': True, 'USE_VOLATILITY_REGIME': True, 'USE_MARKET_BREADTH': True}
**Accuracy**: 0.8039 (baseline: 0.7407)
**Improvement**: +0.0632
**Time**: 2026-05-25T14:11:33.478105

