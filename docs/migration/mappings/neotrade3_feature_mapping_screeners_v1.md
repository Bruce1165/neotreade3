## NeoTrade3 Feature Mapping (Screeners v1)

### Scope
- Domain: `screeners`
- Inventory source: `docs/migration/neotrade2_feature_inventory.v3.json`
- Mapping file: `docs/migration/mappings/neotrade3_feature_mapping_screeners_v1.json`

### What This Covers (NeoTrade2)
- 筛选器算法集合与统一运行契约（`BaseScreener`）
- 筛选器目录/注册与配置管理（catalog + config read/write）
- 单次运行与批量运行
- 结果查询与导出
- 监控摘要（筛选器过期/停滞/异常提示）
- 单只股票检查与 K 线图表复核

### NeoTrade3 Landing (Current Plan)
- `orchestration`: 统一运行入口（单次/批量）与可追溯的运行台账语义
- `issue_center`: 失败/停滞/过期结果等需要形成可追溯问题项的部分
- `learning`: 筛选器/策略的效果评估与结果归档（不直接复刻 2.0 dashboard.db 结构）
- `api/dashboard`: 提供只读浏览与受控触发入口（UI 结构后续独立设计，不照搬 2.0）

### Confirmation Questions (Next)
1) 已确认：3.0 需要保留“用户可独立触发筛选器运行”的入口，同时筛选器应按需成为因子矩阵的一部分。
2) 结果导出在 3.0 是否仍需要“浏览器端导出”（2.0 模式），还是统一为“服务端产物 + 下载”？
3) `stock.check-and-chart` 在 3.0 应作为独立能力保留，还是归并为“结果复核工具”模块的一部分？
