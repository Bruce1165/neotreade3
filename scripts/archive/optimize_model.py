#!/usr/bin/env python3
"""
模型参数优化脚本 - 系统性地搜索最优参数
"""

import subprocess
import sys
import re
from itertools import product

def run_experiment(config_changes, description):
    """运行单次实验"""
    print(f"\n{'='*60}")
    print(f"实验: {description}")
    print(f"配置: {config_changes}")
    print(f"{'='*60}")
    
    # 读取原文件
    with open('neotrade3/ml/autore/train.py', 'r') as f:
        content = f.read()
    
    original = content
    
    # 应用变更
    for param, value in config_changes.items():
        # 构建正则表达式匹配参数赋值
        pattern = rf"({param}\s*=\s*)([^\n#]+)"
        if isinstance(value, bool):
            replacement = rf"\g<1>{str(value)}"
        elif isinstance(value, str):
            replacement = rf'\g<1>"{value}"'
        else:
            replacement = rf"\g<1>{value}"
        content = re.sub(pattern, replacement, content)
    
    # 写入修改后的文件
    with open('neotrade3/ml/autore/train.py', 'w') as f:
        f.write(content)
    
    try:
        # 运行训练
        result = subprocess.run(
            [sys.executable, 'neotrade3/ml/autore/train.py'],
            capture_output=True,
            text=True,
            timeout=600,  # 10分钟超时
        )
        
        # 解析结果
        output = result.stdout + result.stderr
        # 尝试多种格式匹配
        match = re.search(r'out_of_sample_accuracy\s*=\s*(\d+\.\d+)', output)
        if not match:
            match = re.search(r'Out-of-sample accuracy:\s*(\d+\.\d+)', output)
        if match:
            accuracy = float(match.group(1))
            print(f"准确率: {accuracy:.4f}")
            return accuracy
        else:
            print("无法解析结果")
            print("STDOUT:", output[-300:])
            print("STDERR:", result.stderr[-300:])
            return None
            
    except subprocess.TimeoutExpired:
        print("超时!")
        return None
    except Exception as e:
        print(f"错误: {e}")
        return None
    finally:
        # 恢复原文件
        with open('neotrade3/ml/autore/train.py', 'w') as f:
            f.write(original)


def grid_search():
    """网格搜索最优参数"""
    
    # 基于当前最优配置 (80.39%) 进行微调
    base_config = {
        'N_ESTIMATORS': 300,
        'MAX_DEPTH': 20,
        'MIN_SAMPLES_LEAF': 8,
        'THRESHOLD_UP': 1.5,
        'THRESHOLD_DOWN': -1.5,
        'USE_RSI': False,
        'USE_MACD': True,
        'USE_BOLLINGER': True,
        'USE_VOLATILITY_REGIME': True,
        'USE_MARKET_BREADTH': True,
    }
    
    # 待测试的参数组合
    experiments = [
        # 实验1: 增加树数量
        ({**base_config, 'N_ESTIMATORS': 400}, "400棵树"),
        ({**base_config, 'N_ESTIMATORS': 500}, "500棵树"),
        
        # 实验2: 调整深度
        ({**base_config, 'MAX_DEPTH': 25}, "深度25"),
        ({**base_config, 'MAX_DEPTH': 30}, "深度30"),
        ({**base_config, 'MAX_DEPTH': None}, "深度无限制"),
        
        # 实验3: 调整叶节点最小样本
        ({**base_config, 'MIN_SAMPLES_LEAF': 5}, "叶节点5"),
        ({**base_config, 'MIN_SAMPLES_LEAF': 10}, "叶节点10"),
        ({**base_config, 'MIN_SAMPLES_LEAF': 15}, "叶节点15"),
        
        # 实验4: 组合优化
        ({**base_config, 'N_ESTIMATORS': 400, 'MAX_DEPTH': 25}, "400树+深度25"),
        ({**base_config, 'N_ESTIMATORS': 500, 'MAX_DEPTH': 25}, "500树+深度25"),
        
        # 实验5: 特征开关
        ({**base_config, 'USE_MACD': False}, "移除MACD"),
        ({**base_config, 'USE_BOLLINGER': False}, "移除布林带"),
        ({**base_config, 'USE_VOLATILITY_REGIME': False}, "移除波动率体制"),
        
        # 实验6: 阈值调整
        ({**base_config, 'THRESHOLD_UP': 2.0, 'THRESHOLD_DOWN': -2.0}, "阈值±2%"),
        ({**base_config, 'THRESHOLD_UP': 1.0, 'THRESHOLD_DOWN': -1.0}, "阈值±1%"),
        
        # 实验7: lookback调整
        ({**base_config, 'LOOKBACK_DAYS': 90}, "回看90天"),
        ({**base_config, 'LOOKBACK_DAYS': 150}, "回看150天"),
        ({**base_config, 'LOOKBACK_DAYS': 180}, "回看180天"),
    ]
    
    results = []
    for config, desc in experiments:
        accuracy = run_experiment(config, desc)
        if accuracy:
            results.append((desc, accuracy, config))
    
    # 排序并输出结果
    results.sort(key=lambda x: x[1], reverse=True)
    
    print("\n" + "="*60)
    print("实验结果排名")
    print("="*60)
    for i, (desc, acc, config) in enumerate(results[:10], 1):
        print(f"{i}. {desc}: {acc:.4f}")
    
    # 最优配置
    if results:
        best = results[0]
        print(f"\n最优配置: {best[0]}")
        print(f"准确率: {best[1]:.4f}")
        print(f"配置详情: {best[2]}")


if __name__ == "__main__":
    grid_search()
