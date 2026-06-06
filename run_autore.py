#!/usr/bin/env python3
"""
run_autore.py - 自动运行 autoresearch 循环

这个脚本模拟 AI Agent 的行为：
1. 读取 program.md 获取研究方向
2. 提出假设并修改 train.py
3. 运行实验
4. 比较结果并更新记录
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple

import numpy as np

# 搜索空间
PARAM_GRID = {
    "N_ESTIMATORS": [50, 100, 200, 300],
    "MAX_DEPTH": [6, 8, 10, 12, 15, None],  # None = 无限制
    "MIN_SAMPLES_SPLIT": [5, 10, 15, 20],
    "MIN_SAMPLES_LEAF": [2, 3, 5, 8],
    "LOOKBACK_DAYS": [60, 90, 120, 180],
    "THRESHOLD_UP": [1.5, 2.0, 2.5],
    "THRESHOLD_DOWN": [-1.5, -2.0, -2.5],
    "UNIVERSE_SIZE": [200, 500, 1000],
}

FEATURE_FLAGS = [
    "USE_RSI", "USE_MACD", "USE_BOLLINGER",
    "USE_VOLATILITY_REGIME", "USE_MARKET_BREADTH"
]

# 文件路径
TRAIN_FILE = Path("neotrade3/ml/autore/train.py")
BASELINE_FILE = Path("neotrade3/ml/autore/BASELINE.txt")
FAILED_FILE = Path("neotrade3/ml/autore/FAILED.md")
SUCCESS_FILE = Path("neotrade3/ml/autore/SUCCESS.md")
PROGRAM_FILE = Path("neotrade3/ml/autore/program.md")
RESULT_FILE = Path("neotrade3/ml/autore/last_result.txt")


def get_current_baseline() -> float:
    """获取当前 baseline"""
    if BASELINE_FILE.exists():
        content = BASELINE_FILE.read_text()
        match = re.search(r"=\s*([\d.]+)", content)
        if match:
            return float(match.group(1))
    return 0.635  # 默认 baseline


def get_current_config() -> dict:
    """从 train.py 读取当前配置"""
    content = TRAIN_FILE.read_text()
    config = {}
    
    # 读取数值参数
    for param in ["N_ESTIMATORS", "MAX_DEPTH", "MIN_SAMPLES_SPLIT", "MIN_SAMPLES_LEAF",
                  "LOOKBACK_DAYS", "THRESHOLD_UP", "THRESHOLD_DOWN"]:
        match = re.search(rf"{param}\s*=\s*([\d.]+)", content)
        if match:
            value = match.group(1)
            config[param] = int(float(value)) if '.' in value else int(value)
    
    # 读取特征开关
    for flag in FEATURE_FLAGS:
        match = re.search(rf"{flag}\s*=\s*(True|False)", content)
        if match:
            config[flag] = match.group(1) == "True"
    
    return config


def modify_train_file(changes: dict) -> None:
    """修改 train.py 中的参数"""
    content = TRAIN_FILE.read_text()
    
    for param, value in changes.items():
        # 匹配参数赋值语句
        pattern = rf"({param}\s*=\s*)[\d.a-zA-Z_]+"
        if isinstance(value, bool):
            replacement = rf"\g<1>{str(value)}"
        elif value is None:
            replacement = rf"\g<1>None"
        else:
            replacement = rf"\g<1>{value}"
        content = re.sub(pattern, replacement, content)
    
    TRAIN_FILE.write_text(content)


def run_experiment() -> Tuple[bool, float, dict]:
    """运行实验并返回结果"""
    print("\n" + "=" * 50)
    print(f"Running experiment at {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)
    
    try:
        result = subprocess.run(
            [sys.executable, str(TRAIN_FILE)],
            capture_output=True,
            text=True,
            timeout=600,  # 10 分钟超时（universe扩大后需要更长时间）
        )
        
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return False, 0.0, {}
        
        # 解析输出
        output = result.stdout + result.stderr
        
        # 读取结果文件
        if RESULT_FILE.exists():
            content = RESULT_FILE.read_text()
            match = re.search(r"=\s*([\d.]+)", content)
            if match:
                accuracy = float(match.group(1))
            else:
                accuracy = 0.0
        else:
            # 从输出中提取
            match = re.search(r"out_of_sample_accuracy\s*=\s*([\d.]+)", output)
            accuracy = float(match.group(1)) if match else 0.0
        
        # 打印关键输出
        for line in output.split('\n'):
            if 'accuracy' in line.lower() or 'precision' in line.lower():
                print(line)
        
        return True, accuracy, get_current_config()
        
    except subprocess.TimeoutExpired:
        print("Experiment timed out!")
        return False, 0.0, {}
    except Exception as e:
        print(f"Experiment failed: {e}")
        return False, 0.0, {}


def update_baseline(accuracy: float) -> None:
    """更新 baseline"""
    BASELINE_FILE.write_text(f"accuracy = {accuracy:.4f}")


def log_failed(hypothesis: str, config: dict, accuracy: float, baseline: float) -> None:
    """记录失败的实验"""
    with open(FAILED_FILE, "a") as f:
        f.write(f"\n## Failed Experiment\n")
        f.write(f"**Hypothesis**: {hypothesis}\n")
        f.write(f"**Config**: {config}\n")
        f.write(f"**Accuracy**: {accuracy:.4f} (baseline: {baseline:.4f})\n")
        f.write(f"**Delta**: {accuracy - baseline:+.4f}\n")
        f.write(f"**Time**: {datetime.now().isoformat()}\n\n")


def log_success(hypothesis: str, config: dict, accuracy: float, baseline: float) -> None:
    """记录成功的实验"""
    with open(SUCCESS_FILE, "a") as f:
        f.write(f"\n## Successful Experiment\n")
        f.write(f"**Hypothesis**: {hypothesis}\n")
        f.write(f"**Config**: {config}\n")
        f.write(f"**Accuracy**: {accuracy:.4f} (baseline: {baseline:.4f})\n")
        f.write(f"**Improvement**: {accuracy - baseline:+.4f}\n")
        f.write(f"**Time**: {datetime.now().isoformat()}\n\n")


def generate_hypothesis(current_config: dict, explored: set, failed: set) -> Tuple[str, dict, str]:
    """生成下一个实验假设和配置变更，返回 (描述, 变更, 假设名称)"""
    
    # 按优先级尝试不同的方向
    hypotheses = [
        # 方向1: 增加模型复杂度
        {
            "name": "increase_n_estimators_500",
            "condition": current_config.get("N_ESTIMATORS", 300) < 500,
            "changes": {"N_ESTIMATORS": 500},
            "description": "增加决策树数量到 500"
        },
        {
            "name": "increase_max_depth_18",
            "condition": current_config.get("MAX_DEPTH", 15) < 18,
            "changes": {"MAX_DEPTH": 18},
            "description": "增加树深度到 18"
        },
        {
            "name": "increase_max_depth_20",
            "condition": current_config.get("MAX_DEPTH", 18) < 20,
            "changes": {"MAX_DEPTH": 20},
            "description": "增加树深度到 20"
        },
        # 方向2: 调整叶节点大小
        {
            "name": "increase_min_leaf_8",
            "condition": current_config.get("MIN_SAMPLES_LEAF", 5) < 8,
            "changes": {"MIN_SAMPLES_LEAF": 8},
            "description": "增加最小叶节点到 8，减少过拟合"
        },
        # 方向3: 调整阈值
        {
            "name": "wider_threshold_1.5",
            "condition": current_config.get("THRESHOLD_UP", 2.0) > 1.5,
            "changes": {"THRESHOLD_UP": 1.5, "THRESHOLD_DOWN": -1.5},
            "description": "扩大阈值范围到 ±1.5%"
        },
        # 方向4: 特征重要性实验
        {
            "name": "remove_rsi",
            "condition": current_config.get("USE_RSI", True),
            "changes": {"USE_RSI": False},
            "description": "移除 RSI 特征"
        },
        {
            "name": "remove_macd",
            "condition": current_config.get("USE_MACD", True),
            "changes": {"USE_MACD": False},
            "description": "移除 MACD 特征"
        },
        {
            "name": "remove_bollinger",
            "condition": current_config.get("USE_BOLLINGER", True),
            "changes": {"USE_BOLLINGER": False},
            "description": "移除布林带特征"
        },
        # 方向5: 组合优化
        {
            "name": "combined_more_trees_deeper",
            "condition": True,
            "changes": {
                "N_ESTIMATORS": 500,
                "MAX_DEPTH": 18,
            },
            "description": "组合优化: 500树+深度18"
        },
        # 组合优化方向
        {
            "name": "combo_500_depth18",
            "condition": True,
            "changes": {"N_ESTIMATORS": 500, "MAX_DEPTH": 18},
            "description": "组合优化: 500树+深度18"
        },
        {
            "name": "combo_300_depth20",
            "condition": True,
            "changes": {"N_ESTIMATORS": 300, "MAX_DEPTH": 20},
            "description": "组合优化: 300树+深度20"
        },
        {
            "name": "combo_500_depth15_leaf8",
            "condition": True,
            "changes": {"N_ESTIMATORS": 500, "MAX_DEPTH": 15, "MIN_SAMPLES_LEAF": 8},
            "description": "组合优化: 500树+深度15+叶节点8"
        },
        {
            "name": "combo_500_depth18_leaf3",
            "condition": True,
            "changes": {"N_ESTIMATORS": 500, "MAX_DEPTH": 18, "MIN_SAMPLES_LEAF": 3},
            "description": "组合优化: 500树+深度18+叶节点3"
        },
        {
            "name": "wider_threshold_2.5",
            "condition": True,
            "changes": {"THRESHOLD_UP": 2.5, "THRESHOLD_DOWN": -2.5},
            "description": "收窄阈值到 ±2.5%"
        },
        # 方向6: MIN_SAMPLES_SPLIT 调整
        {
            "name": "increase_min_split_15",
            "condition": current_config.get("MIN_SAMPLES_SPLIT", 10) < 15,
            "changes": {"MIN_SAMPLES_SPLIT": 15},
            "description": "增加最小分裂样本到 15"
        },
        {
            "name": "increase_min_split_20",
            "condition": current_config.get("MIN_SAMPLES_SPLIT", 10) < 20,
            "changes": {"MIN_SAMPLES_SPLIT": 20},
            "description": "增加最小分裂样本到 20"
        },
        # 方向7: 特征组合实验
        {
            "name": "remove_volatility_regime",
            "condition": current_config.get("USE_VOLATILITY_REGIME", True),
            "changes": {"USE_VOLATILITY_REGIME": False},
            "description": "移除波动率状态特征"
        },
        {
            "name": "remove_market_breadth",
            "condition": current_config.get("USE_MARKET_BREADTH", True),
            "changes": {"USE_MARKET_BREADTH": False},
            "description": "移除市场广度特征"
        },
        {
            "name": "remove_money_flow",
            "condition": current_config.get("USE_MONEY_FLOW", True),
            "changes": {"USE_MONEY_FLOW": False},
            "description": "移除资金流向特征"
        },
        # 方向8: 深度组合
        {
            "name": "combo_best_no_rsi",
            "condition": True,
            "changes": {
                "N_ESTIMATORS": 500,
                "MAX_DEPTH": 15,
                "MIN_SAMPLES_LEAF": 8,
                "THRESHOLD_UP": 1.5,
                "THRESHOLD_DOWN": -1.5,
                "USE_RSI": False,
            },
            "description": "最佳组合: 500树+深度15+叶节点8+阈值1.5+无RSI"
        },
        {
            "name": "combo_best_no_macd",
            "condition": True,
            "changes": {
                "N_ESTIMATORS": 500,
                "MAX_DEPTH": 15,
                "MIN_SAMPLES_LEAF": 8,
                "USE_MACD": False,
            },
            "description": "测试: 移除MACD效果"
        },
        {
            "name": "combo_best_no_bollinger",
            "condition": True,
            "changes": {
                "N_ESTIMATORS": 500,
                "MAX_DEPTH": 15,
                "MIN_SAMPLES_LEAF": 8,
                "USE_BOLLINGER": False,
            },
            "description": "测试: 移除布林带效果"
        },
        # 方向9: 扩大 universe（关键！减少过拟合和因子漂移）
        {
            "name": "universe_500",
            "condition": current_config.get("UNIVERSE_SIZE", 100) < 500,
            "changes": {"UNIVERSE_SIZE": 500},
            "description": "扩大universe到500只股票，减少过拟合"
        },
        {
            "name": "universe_1000",
            "condition": current_config.get("UNIVERSE_SIZE", 100) < 1000,
            "changes": {"UNIVERSE_SIZE": 1000},
            "description": "扩大universe到1000只股票"
        },
        {
            "name": "universe_500_best_params",
            "condition": True,
            "changes": {
                "UNIVERSE_SIZE": 500,
                "N_ESTIMATORS": 500,
                "MAX_DEPTH": 15,
                "MIN_SAMPLES_LEAF": 8,
                "THRESHOLD_UP": 1.5,
                "THRESHOLD_DOWN": -1.5,
                "USE_RSI": False,
            },
            "description": "扩大universe到500 + 最优参数组合"
        },
        {
            "name": "universe_1000_best_params",
            "condition": True,
            "changes": {
                "UNIVERSE_SIZE": 1000,
                "N_ESTIMATORS": 500,
                "MAX_DEPTH": 15,
                "MIN_SAMPLES_LEAF": 8,
                "THRESHOLD_UP": 1.5,
                "THRESHOLD_DOWN": -1.5,
                "USE_RSI": False,
            },
            "description": "扩大universe到1000 + 最优参数组合"
        },
        # 方向10: 热门板块加权采样（结合市场热点）
        {
            "name": "sector_weighted_500",
            "condition": True,
            "changes": {
                "UNIVERSE_SIZE": 500,
                "USE_SECTOR_WEIGHTING": True,
                "SECTOR_BOOST_FACTOR": 2.0,
            },
            "description": "universe=500 + 热门板块加权采样"
        },
        {
            "name": "sector_weighted_500_best",
            "condition": True,
            "changes": {
                "UNIVERSE_SIZE": 500,
                "N_ESTIMATORS": 300,
                "MAX_DEPTH": 20,
                "MIN_SAMPLES_LEAF": 8,
                "THRESHOLD_UP": 1.5,
                "THRESHOLD_DOWN": -1.5,
                "USE_RSI": False,
                "USE_SECTOR_WEIGHTING": True,
                "SECTOR_BOOST_FACTOR": 2.0,
            },
            "description": "最优参数 + universe=500 + 板块加权"
        },
        {
            "name": "sector_weighted_1000",
            "condition": True,
            "changes": {
                "UNIVERSE_SIZE": 1000,
                "N_ESTIMATORS": 300,
                "MAX_DEPTH": 20,
                "MIN_SAMPLES_LEAF": 8,
                "THRESHOLD_UP": 1.5,
                "THRESHOLD_DOWN": -1.5,
                "USE_RSI": False,
                "USE_SECTOR_WEIGHTING": True,
                "SECTOR_BOOST_FACTOR": 2.0,
            },
            "description": "最优参数 + universe=1000 + 板块加权"
        },
        {
            "name": "sector_weighted_500_boost3",
            "condition": True,
            "changes": {
                "UNIVERSE_SIZE": 500,
                "N_ESTIMATORS": 300,
                "MAX_DEPTH": 20,
                "MIN_SAMPLES_LEAF": 8,
                "THRESHOLD_UP": 1.5,
                "THRESHOLD_DOWN": -1.5,
                "USE_RSI": False,
                "USE_SECTOR_WEIGHTING": True,
                "SECTOR_BOOST_FACTOR": 3.0,
            },
            "description": "最优参数 + universe=500 + 板块加权×3"
        },
    ]
    
    # 选择第一个未探索且满足条件的假设
    for h in hypotheses:
        key = h["name"]
        if key not in explored and key not in failed and h["condition"]:
            return h["description"], h["changes"], h["name"]
    
    # 如果都探索过了，随机选择一个未失败的
    available = [h for h in hypotheses if h["condition"] and h["name"] not in failed]
    if available:
        h = np.random.choice(available)
        return h["description"], h["changes"], h["name"]
    
    return "No more experiments", {}, "none"


def main():
    """主循环"""
    print("=" * 60)
    print("ML Autore - 目标驱动的自动机器学习研究")
    print("=" * 60)
    
    n_experiments = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    baseline = get_current_baseline()
    print(f"\nCurrent baseline: {baseline:.4f}")
    print(f"Running {n_experiments} experiments...\n")
    
    explored = set()
    failed = set()
    improvements = []
    
    for i in range(n_experiments):
        print(f"\n{'#' * 60}")
        print(f"# Experiment {i + 1}/{n_experiments}")
        print(f"{'#' * 60}")
        
        # 生成假设
        hypothesis, changes, hyp_name = generate_hypothesis(get_current_config(), explored, failed)
        print(f"\nHypothesis: {hypothesis}")
        print(f"Changes: {changes}")
        
        # 保存当前配置用于回退
        original_content = TRAIN_FILE.read_text()
        
        # 应用变更
        modify_train_file(changes)
        explored.add(hyp_name if hyp_name else "unknown")
        
        # 运行实验
        success, accuracy, config = run_experiment()
        
        if not success:
            print("Experiment failed, reverting...")
            TRAIN_FILE.write_text(original_content)
            failed.add(hyp_name if hyp_name else "unknown")
            continue
        
        # 比较结果
        delta = accuracy - baseline
        
        print(f"\n{'=' * 50}")
        print(f"Result: accuracy = {accuracy:.4f}")
        print(f"Delta: {delta:+.4f}")
        print(f"{'=' * 50}")
        
        if delta > 0:
            # 改进
            print(f"✅ IMPROVEMENT! (+{delta:.4f})")
            baseline = accuracy
            update_baseline(baseline)
            log_success(hypothesis, config, accuracy, baseline - delta)
            improvements.append((hypothesis, delta))
        else:
            # 退步，回退
            print(f"❌ REGRESSION ({delta:.4f}), reverting...")
            TRAIN_FILE.write_text(original_content)
            log_failed(hypothesis, config, accuracy, baseline)
    
    # 总结
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"Total experiments: {n_experiments}")
    print(f"Successful improvements: {len(improvements)}")
    print(f"Final baseline: {baseline:.4f}")
    
    if improvements:
        print("\nImprovements found:")
        for hyp, delta in improvements:
            print(f"  + {delta:.4f}: {hyp}")
    
    print(f"\nLogs saved to:")
    print(f"  - {SUCCESS_FILE}")
    print(f"  - {FAILED_FILE}")
    print(f"  - {BASELINE_FILE}")


if __name__ == "__main__":
    main()
