#!/usr/bin/env python3
"""
模型参数优化脚本 v2 - 直接修改配置文件
"""

import subprocess
import sys
import re
import json
from pathlib import Path
from datetime import datetime

def run_experiment(config_changes, description):
    """运行单次实验 - 通过修改 train.py 中的配置"""
    print(f"\n{'='*60}")
    print(f"实验: {description}")
    print(f"配置变更: {config_changes}")
    print(f"{'='*60}")
    
    # 读取原文件
    train_path = Path('neotrade3/ml/autore/train.py')
    content = train_path.read_text()
    original = content
    
    # 安全地替换配置值
    # 策略：找到 "PARAM = value" 这一行，整行替换
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        new_line = line
        for param, value in config_changes.items():
            # 匹配 "PARAM = value" 或 "PARAM = value  # comment"
            pattern = rf'^({param}\s*=\s*)[^#\n]+(.*)$'
            if re.match(pattern, line):
                if isinstance(value, bool):
                    val_str = str(value)
                elif isinstance(value, str):
                    val_str = f'"{value}"'
                elif value is None:
                    val_str = 'None'
                else:
                    val_str = str(value)
                new_line = f'{param} = {val_str}'
                if re.search(r'#.*$', line):
                    comment = re.search(r'(#.*$)', line).group(1)
                    new_line += f'  {comment}'
                break
        new_lines.append(new_line)
    
    # 写回文件
    train_path.write_text('\n'.join(new_lines))
    
    try:
        # 运行训练
        result = subprocess.run(
            [sys.executable, str(train_path)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        
        # 解析结果
        output = result.stdout + result.stderr
        match = re.search(r'out_of_sample_accuracy\s*=\s*(\d+\.\d+)', output)
        if not match:
            match = re.search(r'Out-of-sample accuracy:\s*(\d+\.\d+)', output)
        
        if match:
            accuracy = float(match.group(1))
            print(f"✓ 准确率: {accuracy:.4f}")
            return accuracy
        else:
            print("✗ 无法解析结果")
            if "SyntaxError" in output:
                print("语法错误！")
            return None
            
    except subprocess.TimeoutExpired:
        print("✗ 超时!")
        return None
    except Exception as e:
        print(f"✗ 错误: {e}")
        return None
    finally:
        # 恢复原文件
        train_path.write_text(original)


def main():
    """主函数 - 运行关键实验"""
    
    # 当前最优配置 (76.67%)
    base_config = {
        'N_ESTIMATORS': 300,
        'MAX_DEPTH': 20,
        'MIN_SAMPLES_LEAF': 8,
        'LOOKBACK_DAYS': 120,
        'THRESHOLD_UP': 1.5,
        'THRESHOLD_DOWN': -1.5,
        'USE_RSI': False,
        'USE_MACD': True,
        'USE_BOLLINGER': True,
        'USE_VOLATILITY_REGIME': True,
        'USE_MARKET_BREADTH': True,
    }
    
    # 精选实验（减少数量，提高质量）
    experiments = [
        # 实验1: 增加树数量
        ({**base_config, 'N_ESTIMATORS': 500}, "500棵树"),
        
        # 实验2: 调整深度
        ({**base_config, 'MAX_DEPTH': 25}, "深度25"),
        ({**base_config, 'MAX_DEPTH': 15}, "深度15"),
        
        # 实验3: 叶节点样本
        ({**base_config, 'MIN_SAMPLES_LEAF': 5}, "叶节点5"),
        ({**base_config, 'MIN_SAMPLES_LEAF': 12}, "叶节点12"),
        
        # 实验4: 最优组合
        ({**base_config, 'N_ESTIMATORS': 500, 'MAX_DEPTH': 25}, "500树+深度25"),
        ({**base_config, 'N_ESTIMATORS': 400, 'MAX_DEPTH': 25, 'MIN_SAMPLES_LEAF': 5}, "400树+深度25+叶节点5"),
        
        # 实验5: 特征优化
        ({**base_config, 'USE_MACD': False}, "移除MACD"),
        ({**base_config, 'USE_BOLLINGER': False}, "移除布林带"),
        
        # 实验6: 阈值
        ({**base_config, 'THRESHOLD_UP': 2.0, 'THRESHOLD_DOWN': -2.0}, "阈值±2%"),
        
        # 实验7: lookback
        ({**base_config, 'LOOKBACK_DAYS': 90}, "回看90天"),
        ({**base_config, 'LOOKBACK_DAYS': 150}, "回看150天"),
    ]
    
    results = []
    for config, desc in experiments:
        accuracy = run_experiment(config, desc)
        if accuracy:
            results.append((desc, accuracy, config))
    
    # 排序输出
    results.sort(key=lambda x: x[1], reverse=True)
    
    print("\n" + "="*60)
    print("实验结果排名")
    print("="*60)
    for i, (desc, acc, _) in enumerate(results[:10], 1):
        print(f"{i}. {desc}: {acc:.4f}")
    
    # 保存结果
    if results:
        best = results[0]
        print(f"\n🏆 最优配置: {best[0]}")
        print(f"   准确率: {best[1]:.4f}")
        
        # 保存到文件
        result_file = Path('var/optimization_results.json')
        result_file.parent.mkdir(parents=True, exist_ok=True)
        with open(result_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'best_config': best[2],
                'best_accuracy': best[1],
                'best_description': best[0],
                'all_results': [{'desc': d, 'accuracy': a} for d, a, _ in results]
            }, f, indent=2, default=str)
        print(f"\n结果已保存: {result_file}")


if __name__ == "__main__":
    main()
