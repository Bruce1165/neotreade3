# 策略配置（Strategy Configs）

Owner: NeoTrade3
Scope: `config/strategies/*.json`
Canonical: yes
Last_reviewed: 2026-07-16

## 目的

提供统一的策略配置入口，使同一份配置可驱动系统内的信号生成、回测与报告产物（版本体系统一的前置基础）。

## 文件规则

- 文件命名：`<strategy_id>.json`
- 文件内必须包含字段：`strategy_id`，且必须与文件名一致

## 允许内容

- JSON 配置文件（策略元信息 + parameters）

## CLI 用法

本仓库提供一个显式可审计的“导出/刷新策略配置”入口，用于把 `lowfreq_model_store.params_json` 写回到 `config/strategies/lowfreq_v16.json`。

```bash
python3 -m neotrade3.strategies.cli export-lowfreq-model-store-to-strategy \
  --project-root /path/to/NeoTrade3 \
  --model-id lowfreq_engine_v16_advanced \
  --strategy-id lowfreq_v16
```

- 默认参数：
  - `--project-root`：仓库根目录
  - `--model-id`：`lowfreq_engine_v16_advanced`
  - `--strategy-id`：`lowfreq_v16`（当前仅允许导出该策略）
- 输出：标准输出打印 JSON（包含导出路径与导出的参数 keys 列表），非 0 返回码代表 fail-closed 失败。

## 退出条件

当策略版本体系完成统一并具备更高阶的注册/分发机制后，本目录可被替代并进入归档流程。
