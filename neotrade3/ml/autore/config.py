#!/usr/bin/env python3
"""
Autore - 目标驱动的自动机器学习研究框架

基于 karpathy/autoretch 思想，适配到股票预测任务。
核心循环：Agent 读取 program.md → 提出假设 → 修改 train.py → 评估 → 保留/回退
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

# ============================================================
# 固定常量（不允许 Agent 修改）
# ============================================================

DB_PATH = Path("var/db/stock_data.db")
MODEL_DIR = Path("var/models")
BASELINE_FILE = Path("neotrade3/ml/autore/BASELINE.txt")
FAILED_FILE = Path("neotrade3/ml/autore/FAILED.md")
PROGRAM_FILE = Path("neotrade3/ml/autore/program.md")

# 搜索空间定义（Agent 可调整的参数范围）
SEARCH_SPACE = {
    # 模型参数
    "n_estimators": [50, 100, 200, 300],
    "max_depth": [6, 8, 10, 12, 15],
    "min_samples_split": [5, 10, 15, 20],
    "min_samples_leaf": [2, 3, 5, 8],
    
    # 训练参数
    "lookback_days": [60, 90, 120, 180],
    "threshold_up": [1.5, 2.0, 2.5, 3.0],
    "threshold_down": [-1.5, -2.0, -2.5, -3.0],
    
    # 特征参数
    "use_rsi": [True, False],
    "use_macd": [True, False],
    "use_bollinger": [True, False],
    "use_volatility_regime": [True, False],
    "use_market_breadth": [True, False],
}


@dataclass
class ExperimentResult:
    """单次实验结果"""
    accuracy: float
    precision: float
    recall: float
    f1: float
    out_of_sample_accuracy: float
    train_samples: int
    test_samples: int
    config: dict[str, Any]
    timestamp: str


def get_baseline() -> float | None:
    """读取当前 baseline 分数"""
    if not BASELINE_FILE.exists():
        return None
    try:
        content = BASELINE_FILE.read_text().strip()
        return float(content.split("=")[1].strip())
    except Exception:
        return None


def update_baseline(score: float) -> None:
    """更新 baseline 分数"""
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(f"accuracy = {score:.4f}")


def log_failed(hypothesis: str, config: dict, reason: str) -> None:
    """记录失败的实验"""
    FAILED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FAILED_FILE, "a") as f:
        f.write(f"\n## Failed Experiment\n")
        f.write(f"**Hypothesis**: {hypothesis}\n")
        f.write(f"**Config**: {config}\n")
        f.write(f"**Reason**: {reason}\n")
        f.write(f"**Time**: {date.today()}\n\n")


def log_success(config: dict, metrics: dict, improvement: float) -> None:
    """记录成功的实验"""
    log_file = Path("neotrade3/ml/autore/SUCCESS.md")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as f:
        f.write(f"\n## Successful Experiment\n")
        f.write(f"**Config**: {config}\n")
        f.write(f"**Metrics**: {metrics}\n")
        f.write(f"**Improvement**: +{improvement:.4f}\n")
        f.write(f"**Time**: {date.today()}\n\n")
