# NeoTrade3 Code Wiki

## 目标

- 统一说明仓库目录语义，明确每一类文件的 SSOT（Single Source of Truth）与派生属性
- 基于可核验证据，输出“可清理候选清单”（本次不做任何实际删除）

## 文档索引

- [repo_tree.md](file:///Users/mac/NeoTrade3/docs/wiki/repo_tree.md)
- [cleanup_candidates.md](file:///Users/mac/NeoTrade3/docs/wiki/cleanup_candidates.md)

## 维护原则

- SSOT 优先：源码、配置、契约、验收与交接文档属于真相源，默认不清理
- 可再生优先：缓存、构建产物、测试产物、临时文件属于派生物，只给出“候选+重建方式”
- 风险分级：清单中按“低风险/中风险/高风险”标注；高风险项仅给出证据与边界，不给“默认建议”
- 证据闭环：每个候选项必须能回答“为什么可以删 / 怎么重建 / 影响是什么”

## 最近一次审计快照（仓库根目录）

- 审计时间：2026-07-19
- 目录占用（du 摘要）
  - `neotrade3-dashboard/` ≈ 194M（包含前端依赖与构建产物）
  - `./.venv/` ≈ 164M（Python 虚拟环境）
  - `./.git/` ≈ 41M（版本库元数据）
- `var/` 当前为符号链接：`var -> /Volumes/Data/NeoTradeDB/var`，不属于仓库本体空间占用范围（但可能是主要磁盘占用来源之一）

