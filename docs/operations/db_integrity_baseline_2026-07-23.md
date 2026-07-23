# 数据库完整性基线（2026-07-23）

> 首次基线。目的：为 NEO 外挂盘上的生产数据库建立"可比对、可回退"的完整性参照点。
> 检查方式：复制副本后离线校验（活库零交互、零锁定风险）；校验时间窗口 10:35–10:45（远离 15:45 / 16:25 计划写入）。

## 卷信息

- 路径：`/Volumes/NEO/NeoTradeDB/var`（仓库内 `var` 为指向此处的符号链接）
- 文件系统：APFS（USB 外接），owners disabled
- 各库 journal mode 不一：`stock_data.db` 为 WAL，其余为 delete（rollback journal）

## 基线指纹

| 数据库 | 大小 | journal | 表数 | 校验结果 | SHA-256 |
|--------|------|---------|------|----------|---------|
| `db/stock_data.db` | 3.81 GB | wal | 49 | `integrity_check` **ok** (26s) | `5c656ddc…817eb4aca` |
| `db/chaos_factor_matrix.db` | 577 MB | delete | 3 | `integrity_check` **ok** (4s) | `cf66ff8c…79d1aaa5` |
| `db/chaos_factor_matrix_a_share.db` | 22.48 GB | delete | 3 | 小表 ok；大表见下注 | `574a18f6…3ced1657` |
| `data/paper_trading.db` | 32 KB | delete | 3 | `quick_check` **ok** | `a1e53670…59a1e54c` |

**注（a_share 大库）**：`chaos_factor_registry`（1 行）与 `chaos_daily_snapshot`（227 万行）`quick_check` ok；`chaos_factor_values`（**8591 万行**）单次结构校验超出 5 分钟前台窗口未完成，已取得证据：全表 `COUNT(*)` 通读 43.9s 无错（全部叶子页可读）。建议在维护窗口对该表跑一次完整 `quick_check('chaos_factor_values')`。

## 分层快照策略（取代"每次写前都快照"的过度方案）

| 写操作类型 | 快照要求 | 理由 |
|------------|----------|------|
| 例行增量写（调度器 15:45、v2 16:25/16:35、API 日常写入） | **不做** | sqlite 事务 + WAL/rollback journal 已保证崩溃原子性；这些是跑了数周的成熟路径 |
| 批量回填（如 chaos 全 A 回填级） | **做，滚动单份** | 大批量、长耗时、难肉眼复核；出错代价高 |
| 结构变更（DDL / migration） | **做，滚动单份** | schema 级风险 |
| 新写路径首次上线 | **做，滚动单份** | 未经生产验证 |

滚动单份规则：快照固定存放于 `/Volumes/NEO/NeoTradeDB/var/_snapshots/<库名>.pre_bulk.db`，**新的覆盖旧的**，任何时刻每个库最多一份，不产生累积。用 `sqlite3 <db> ".backup '<path>'"` 在线备份（WAL 下安全）。

## 例行复核建议

- 每月或每次大批量写入后：对比 SHA-256 是否变化 + `quick_check` 抽查（大库只对 `chaos_daily_snapshot` 及更小表）。
- 发现 `integrity_check` 报错时：不要修，先复制副本隔离，再评估恢复方案。

## 附带发现（待 owner 处置）

- `db/_tmp_seed_test.db`（403 MB，2026-05-20 TRAE 时代遗留的测试种子库，WAL 模式，含 stocks/daily_prices 等 6 表）——非本次协作产物，疑似废弃，待确认后清理。
- NEO 卷上存在 macOS AppleDouble 垃圾文件（`._*`），无害但可在磁盘整理时一并清。
