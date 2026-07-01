# NeoTrade3 authoritative 数据源彻底收口与工作级整合设计

日期：2026-06-16  
范围：旧入口彻底收口、前端工作级表达、正式文档唯一真相源、历史文档归档标注

## 1. 背景

### 1.1 已完成的基础收敛
- `daily_prices` 的服务层已切为 authoritative 语义：
  - `Tushare` 主源
  - `Tencent` 仅作 `daily_prices` safety-net
- `Tushare` 唯一来源资源已支持 `authoritative_source_unavailable`
- 生产调度与 `launchd` 已切到：
  - `update_daily_prices_authoritative`
- 前端 `MarketIntelligence` 已具备最小错误展示：
  - 能显示 `authoritative_source_unavailable`
  - 能显示 `resource / provider / fallback_attempted / fallback_provider`

### 1.2 仍未达到“100% 整合到位”的原因
- 仍保留旧别名和旧工作入口，例如：
  - `update_daily_prices_tencent` scheduler 兼容别名
  - `update_daily_prices_tencent_view`
  - `update_daily_prices_tushare_view`
- 正式文档之外，仍存在多份旧口径文档引用腾讯主入口或旧任务 id。
- 前端虽然能报错，但还没有把“当前 authoritative 工作口径”明确提升为工作级显示标准。
- 历史/调试/spec 文档中，旧口径没有统一标注“历史归档，不代表当前生产”。

## 2. 本轮目标

### 2.1 总目标
- 达成“100% 整合到位，达到工作级别，文档同步”的可验证状态。

### 2.2 本轮对“100%”的严格定义
- 对外正式工作入口只有 authoritative 入口。
- 前端工作页只按 authoritative 口径解释和展示数据源状态。
- 正式运行文档只有一个生产真相源。
- 历史文档如继续保留，必须显式声明：
  - 历史口径
  - 归档用途
  - 不代表当前生产

## 3. 设计原则

### 3.1 彻底收口
- 用户已明确选择“彻底收口”。
- 因此本轮不采用“兼容但继续对外可用”的方案。
- 任何仍可被当成工作入口的旧路径，必须删除、封禁或降级为内部诊断能力。

### 3.2 工作级别
- “工作级别”不等于“技术上可以运行”。
- 它要求：
  - 人能理解当前系统实际使用哪条链路
  - 前端不会误导使用者
  - 文档不会给出多个互相冲突的答案
  - 运维不会因为旧入口残留而走错路径

### 3.3 文档同步硬约束
- 任何代码改动必须同步正式文档。
- 历史文档不要求重写历史内容，但必须追加清晰的归档声明。

## 4. 方案对比

### 4.1 方案 A：彻底收口并统一真相源
- 删除或下线旧正式入口。
- 前端只认 authoritative 语义。
- 正式文档全部统一。
- 历史文档显式降级为归档。
- 优点：
  - 唯一能满足“彻底收口”
  - 后续维护成本最低
- 缺点：
  - 需要同时修改代码、前端、文档

### 4.2 方案 B：旧入口保留但返回废弃提示
- 优点：
  - 对外破坏更小
- 缺点：
  - 仍保留多个入口壳子
  - 不满足“彻底收口”

### 4.3 结论
- 采用方案 A。

## 5. 工作入口彻底收口

### 5.1 scheduler
- 删除 `update_daily_prices_tencent` 兼容别名。
- `run_once_map` 只保留：
  - `update_daily_prices_authoritative`
- APScheduler local/dev job id 只保留：
  - `update_daily_prices_authoritative`

### 5.2 API router
- 移除旧的工作级 public 入口：
  - `update_daily_prices_tencent_view`
- `update_daily_prices_tushare_view` 不再作为工作入口暴露给常规运维。
- 若确有维护需要，保留为内部维护能力，但不再作为默认 public workflow。
- router 对外只保留 authoritative 日线入口。

### 5.3 service
- 内部私有实现函数允许保留，例如：
  - `update_daily_prices_tencent_view`
  - `update_daily_prices_tushare_view`
- 但它们只能被 authoritative 编排层调用，不能再构成外部正式工作入口。

## 6. 前端工作级整合

### 6.1 当前不足
- `MarketIntelligence` 已能显示 authoritative 错误，但仍是最小级表达。
- 当前还缺少“当前工作口径”的稳定显式表达。

### 6.2 本轮要求
- 前端工作页必须满足：
  - 用户能直接看到当前主源口径
  - 用户在失败时能识别这是 authoritative 失败，而不是普通请求失败
  - 用户不会再从 UI 上理解成“腾讯仍是主入口”

### 6.3 最小工作级表达
- 在 `MarketIntelligence` 保留现有主源说明。
- 若条件允许，在数据状态或总览页补一个简洁 authoritative 状态区：
  - `daily_prices 主源：Tushare`
  - `daily_prices safety-net：Tencent`
  - 若后端返回资源级失败，显示最近失败资源与时间
- 不扩展为复杂监控后台。

## 7. 正式文档唯一真相源

### 7.1 必须同步更新的正式文档
- `docs/operations/bootstrap_runbook.md`
- `docs/operations/production_task_registry.md`
- `PROJECT_STATUS.md`
- `docs/superpowers/specs/2026-06-16-tushare-authoritative-source-safety-net-design.md`
- 本文档

### 7.2 同步后的正式文档要求
- 不能再把 `update_daily_prices_tencent` 描述为当前正式任务名
- 不能再把腾讯表述为 `daily_prices` 主源
- 不能再把旧 public 入口表述为常规工作流入口

## 8. 历史文档归档标注

### 8.1 需要处理的历史文档类型
- debug 文档
- 已过时 spec
- migration inventory / feature inventory
- 历史运行记录

### 8.2 处理规则
- 不改写历史事实本身。
- 在文件头或显著位置加统一标注：
  - 本文件为历史/归档口径
  - 可能包含旧任务名或旧数据源路径
  - 不代表当前生产真相源

### 8.3 优先处理对象
- `debug-scheduler-missed-day.md`
- 引用 `update_daily_prices_tencent` 为当前生产入口的旧 spec
- `PROJECT_STATUS.md` 中与当前生产口径冲突的段落

## 9. 测试与验收

### 9.1 代码验收
- scheduler 中不再存在可工作的旧正式 job id
- router 中不再暴露旧正式日线入口
- authoritative 路径仍通过现有回归

### 9.2 前端验收
- `MarketIntelligence` 在成功场景下显示 authoritative 主源口径
- `MarketIntelligence` 在 authoritative 失败时显示结构化错误
- 前端不会再展示与“腾讯主源”一致的旧描述

### 9.3 文档验收
- 正式运行文档之间不再互相冲突
- 历史文档已带归档标记
- 仓库内搜索“`update_daily_prices_tencent` 作为当前正式入口”时，不应再出现在正式文档中

## 10. 分阶段执行

### 10.1 第 1 阶段：代码入口收口
- 删除 scheduler 兼容别名
- 收紧 router public 入口
- 更新对应测试

### 10.2 第 2 阶段：前端工作级表达补齐
- 保持 authoritative 说明可见
- 保证错误表达结构化且不误导

### 10.3 第 3 阶段：文档彻底收口
- 更新正式文档
- 为历史文档加归档标记
- 跑一次全文搜索复核旧口径残留

## 11. 非目标

- 不重写历史 migration 内容本身
- 不新增复杂监控后台
- 不重构 `market-intelligence` 排序、推荐、主题逻辑
- 不引入新的配置中心

## 12. 风险与边界

### 12.1 接受的风险
- 内部私有实现函数名仍可能保留“tencent/tushare”字样，只要它们不再构成正式工作入口即可接受。

### 12.2 不接受的风险
- 不接受旧入口仍可被当成正式操作路径。
- 不接受正式文档继续引用旧正式任务名。
- 不接受历史文档继续以未标注状态混在当前生产口径里。

## 13. 验收标准

1. 对外正式工作入口只剩 authoritative。
2. scheduler / launchd / router / 前端 / 正式文档全部统一为 authoritative 口径。
3. 旧正式入口不再作为可工作路径存在。
4. 历史文档全部带归档标记，不再冒充当前真相源。
5. 回归测试、语法校验和关键搜索检查全部通过。
