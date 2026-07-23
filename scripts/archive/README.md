# scripts/archive — 已归档脚本

本目录存放**不再被活代码、配置、CI、launchd 或现行文档引用**的脚本。归档 ≠ 删除：全部仍在 git 历史与工作树中，可随时 `git mv` 回 `scripts/` 恢复。

## 归档口径（2026-07-22 清理周期确立）

归档前逐项完成引用闭包检查，范围包括：仓库全量代码与配置、`tests/`、`.github/workflows/`、用户域与系统域 launchd plist、`docs/` 现行文档（`docs/archive/specs/` 历史归档不计入活引用）、脚本间交叉 import。

符合以下任一条件方可归档：

1. 全仓库零外部引用，且无脚本间相互 import；
2. 明确的一次性任务（日期型补采、版本迁移），任务已完成；
3. 引用仅存在于历史交接文档的记述性内容（非现行操作流程）。

## 注意事项

- 多数脚本用 `Path(__file__).resolve().parents[1]` 推导 `PROJECT_ROOT`。移入 `archive/` 后该推导会指向 `scripts/` 而非仓库根，**原地直接运行可能取错路径**；需要重跑时请先移回 `scripts/`。
- `neotrade3` 包以 `pip install -e` 方式安装，脚本对 `neotrade3.*` 的 import 不受归档位置影响。

## 2026-07-22 批次（6 项，引用证据见对应提交信息）

| 脚本 | 归档理由 |
|------|----------|
| `fetch_20260525_data.py` | 日期型一次性补采（2026-05-25 腾讯接口）；写死 TRAE 会话路径已失效；仅被实施交接文档历史记述提及 |
| `sync_v2_param_metadata_to_v3.py` | v2→v3 参数元数据迁移一次性脚本，迁移早已完成，零引用 |
| `brainstorm_server.py` | 独立 HTTP 服务，零引用，不在任何 launchd plist 中 |
| `start-server.sh` | 零引用启动便利脚本（dashboard 另有 npm scripts） |
| `backfill_chaos_daily_snapshot_all_a_share.py` | 混沌快照全 A 回填，owner 确认回填已完成，零引用 |
| `backfill_stock_top_hazard_labels_t2.py` | 风险标签 T+2 回填，同上 |

## 早期批次（2026-07-22 第一轮清理）

`run_autore.py`、`sector_rotation.py`（根目录移入）、`generate_handover.js` — 孤儿脚本，引用证据见提交 `c9d2896`。

## 既有归档子目录

`backtest/`、`lowfreq/`、`research/`、`standalone/` 及 `optimize_model.py`、`optimize_model_v2.py`、`test_sector_weighted.py` 为 wip 分支合并带回的历史归档，维持原状。
