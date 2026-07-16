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

## 退出条件

当策略版本体系完成统一并具备更高阶的注册/分发机制后，本目录可被替代并进入归档流程。
