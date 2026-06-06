#!/usr/bin/env python3
"""测试板块加权采样效果"""

import subprocess
import sys

def run_test(description, changes):
    """运行单次测试"""
    print(f"\n{'='*60}")
    print(f"测试: {description}")
    print(f"配置: {changes}")
    print(f"{'='*60}\n")
    
    # 读取原文件
    with open('neotrade3/ml/autore/train.py', 'r') as f:
        content = f.read()
    
    original = content
    
    # 应用变更
    for param, value in changes.items():
        pattern = rf"({param}\s*=\s*)[\d.a-zA-Z_]+"
        if isinstance(value, bool):
            replacement = rf"\g<1>{str(value)}"
        elif isinstance(value, (int, float)):
            replacement = rf"\g<1>{value}"
        else:
            replacement = rf"\g<1>{value}"
        import re
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
            timeout=900,  # 15分钟超时
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr[-500:])  # 只显示最后500字符
            
    except subprocess.TimeoutExpired:
        print("超时!")
    except Exception as e:
        print(f"错误: {e}")
    finally:
        # 恢复原文件
        with open('neotrade3/ml/autore/train.py', 'w') as f:
            f.write(original)

if __name__ == "__main__":
    # 测试1: universe=500 + 板块加权
    run_test("universe=500 + 板块加权", {
        "UNIVERSE_SIZE": 500,
        "USE_SECTOR_WEIGHTING": True,
        "SECTOR_BOOST_FACTOR": 2.0,
        "N_ESTIMATORS": 300,
        "MAX_DEPTH": 20,
        "MIN_SAMPLES_LEAF": 8,
        "THRESHOLD_UP": 1.5,
        "THRESHOLD_DOWN": -1.5,
        "USE_RSI": False,
    })
