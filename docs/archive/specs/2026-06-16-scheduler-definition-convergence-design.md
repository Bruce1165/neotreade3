# NeoTrade3 调度双定义收敛（设计定稿）

> 归档说明：本文记录的是当时调度口径收敛的设计基线。文中涉及 `update_daily_prices_tencent` 等旧正式任务名的表述，仅代表设计当时事实，不代表当前正式生产口径；当前正式日线任务名为 `update_daily_prices_authoritative`。

日期：2026-06-16  
范围：生产自动任务定义口径、调度文档口径、`task_scheduler.py` CLI/注释口径

## 1. 背景与问题

### 1.1 已确认事实
- 当前生产实际启用的自动任务只有 2 个：
  - `update_daily_prices_tencent`
  - `trade_execution_rt_0935`
- 这 2 个任务的真实生产触发源不是 APScheduler 常驻进程，而是 `launchd` 的 LaunchAgent：
  - `com.neotrade3.scheduler`
  - `com.neotrade3.trade_execution_rt`
- 当前 LaunchAgent 使用 `--run-once` 模式直接调用 `neotrade3.scheduler.task_scheduler`。
- `task_scheduler.py` 内仍保留一套 APScheduler 注册定义，并支持：
  - `--list-jobs`
  - `--run-now`
  - `--run-once`
  - `--run-forever`

### 1.2 当前问题
- 同一批任务同时存在两套“可见定义”：
  - `config/launchd/` 中的生产模板
  - `task_scheduler.py` 中的 APScheduler 注册
- 它们表达的是不同层级的信息，但当前文档和代码注释没有彻底分层，容易被误读成“二者都代表生产启用”。
- 已经出现过实际风险：
  - 生产时间由 LaunchAgent 控制，但 APScheduler 注释/注册使用了另一套时间口径。
  - 文档如果只看代码注册，很容易误判生产有哪些任务在自动运行。
  - 修改者可能只改了 APScheduler 或只改了 LaunchAgent，造成再次漂移。

### 1.3 本次要解决的问题
- 明确什么是“生产真相源”。
- 明确什么是“代码可执行入口”。
- 明确文档、代码注释、CLI 帮助应如何表达，避免再次混淆。

## 2. 根因分析

### 2.1 根因不是“多一份定义”本身
- `task_scheduler.py` 保留 APScheduler 注册并不天然错误。
- 问题在于当前没有给这两类定义建立明确层级：
  - 哪个代表“生产启用”
  - 哪个代表“代码能力/开发入口”

### 2.2 真正失控点
- 生产启用状态没有唯一口径。
- 代码注释与文档没有持续强调：
  - LaunchAgent 才是当前生产触发器。
  - APScheduler 注册只是代码内的可运行调度定义，不应默认等同于生产已启用。
- 因此出现了“代码存在”被误读为“生产在跑”的认知偏差。

## 3. 设计目标

### 3.1 目标
- 将 `config/launchd/` 明确为当前生产自动任务的第一真相源。
- 将 `docs/operations/production_task_registry.md` 明确为生产任务的人类可读总表。
- 将 `task_scheduler.py` 明确降格为：
  - 任务函数定义所在文件
  - 手工执行入口
  - 开发/调试用 APScheduler 注册入口
- 收敛代码注释、CLI 帮助和 runbook 文案，使三者不再暗示“APScheduler 注册等于生产启用”。

### 3.2 非目标
- 不取消 `task_scheduler.py` 中现有 `--run-once` 能力。
- 不删除 APScheduler 注册逻辑。
- 不新增新的生产 LaunchAgent。
- 不调整任何任务时间点。
- 不改变 `daily_pipeline`、`trade_execution_rt`、`fetch_news` 的业务语义。
- 不把当前生产模式改为 `--run-forever` 常驻进程。

## 4. 方案对比与选型

### 4.1 方案 A：以 `launchd` 为生产真相源，APScheduler 退化为代码/手工入口
- 定义：
  - 生产是否启用、什么时候跑，由 `config/launchd/` 决定。
  - APScheduler 只表示代码层“可注册的内部调度定义”。
- 优点：
  - 与当前真实生产状态一致。
  - 变更最小，不引入执行模型切换风险。
  - 能直接解决“代码定义”和“生产启用”混淆问题。
- 缺点：
  - 代码里仍会保留一套时间表达，需要靠注释和文档约束。

### 4.2 方案 B：删除 APScheduler 注册，只保留 `run-once`
- 优点：
  - 表面上最不易混淆。
- 缺点：
  - 会失去本地 `--list-jobs` / `--run-now` / `--run-forever` 的已有工具能力。
  - 对现有开发调试入口改动较大，收益不足。

### 4.3 方案 C：改为 APScheduler 常驻进程为唯一真相源
- 优点：
  - 理论上可把所有任务都收进同一代码调度器。
- 缺点：
  - 与当前生产实际不一致。
  - 需要重新设计进程托管、启动恢复、异常处理和观察方式。
  - 风险明显超出本轮范围。

### 4.4 结论
- 采用方案 A。
- 原因：它与当前生产现实一致，改动最小，且能直接解决本轮最关键的“口径混淆”问题。

## 5. 单一真相源定义

### 5.1 生产真相源
- 当前生产自动任务的唯一配置真相源是：
  - `config/launchd/`
- 当前生产自动任务的人类可读真相总表是：
  - `docs/operations/production_task_registry.md`

### 5.2 代码层真相
- `neotrade3/scheduler/task_scheduler.py` 不是生产启用清单。
- 它只负责表达以下内容：
  - 任务函数实现入口
  - `run-once` 手工执行入口
  - 开发/调试可用的 APScheduler 注册

### 5.3 口径判定规则
- 当用户问“生产现在有哪些自动任务在跑”，先看：
  - `config/launchd/`
  - `production_task_registry.md`
- 当用户问“代码里有哪些可调度任务”，再看：
  - `task_scheduler.py`
- 若两者不一致，不得默认以 APScheduler 覆盖生产口径，必须先核对 LaunchAgent 模板与实际安装状态。

## 6. 代码层收敛设计

### 6.1 文件级注释
- 更新 `task_scheduler.py` 顶部模块说明，明确写出：
  - 本文件提供任务函数、`run-once` 入口和开发用 APScheduler 注册。
  - 当前生产启用任务仍以 `launchd` LaunchAgent 为准。

### 6.2 注册区注释
- 对 `_init_scheduler()` 中每个 `add_job(...)` 的注释做两类区分：
  - 生产已启用任务，但此处仅表示代码内调度定义
  - 当前未生产启用的开发/预留任务
- 至少要避免再出现“读者只看这里就以为这是生产配置”的误导。

### 6.3 CLI 帮助文案
- 调整 `build_parser()` 中参数 help，使其明确区分：
  - `--run-once`：手工执行一个任务，不依赖 APScheduler
  - `--list-jobs` / `--run-now` / `--run-forever`：查看或运行代码内 APScheduler 注册，不代表生产 LaunchAgent 配置

### 6.4 不做的代码改动
- 不改 `run_once_map` 的任务集合。
- 不改 APScheduler 的注册时间。
- 不为 APScheduler 增加“自动同步 LaunchAgent”逻辑。

## 7. 文档层收敛设计

### 7.1 `production_task_registry.md`
- 继续作为“生产任务真相总表”。
- 在文档中进一步明确：
  - “是否生产启用”只看生产触发器，不看代码里是否注册。
  - `task_scheduler.py` 只代表代码能力，不代表生产启用事实。

### 7.2 `bootstrap_runbook.md`
- 继续保留两部分内容，但明确边界：
  - LaunchAgents：当前生产入口
  - Scheduler 定义：代码内 APScheduler 注册
- 在 Scheduler 小节中补充一句明确约束：
  - 任何生产任务的时间、工作日、启停状态，均不得只通过 APScheduler 注册来判断。

### 7.3 后续文档维护规则
- 涉及生产任务新增、下线、时间调整、工作日调整时：
  1. 先改 `config/launchd/`
  2. 再改 `production_task_registry.md`
  3. 若代码注释或 CLI 帮助受影响，再改 `task_scheduler.py`
- 不允许只更新代码注册说明而不更新生产文档。

## 8. 任务分类与表达规范

### 8.1 生产启用任务
- 当前只有：
  - `update_daily_prices_tencent`
  - `trade_execution_rt_0935`
- 这类任务在代码和文档中必须显式标注“当前由 `launchd` 生产启用”。

### 8.2 代码已定义但当前未生产启用任务
- 当前包括：
  - `update_financial_data`
  - `fetch_news`
  - `warm_tushare_theme_cache`
- 这类任务在文档中必须显式标注“当前未见生产 LaunchAgent”。

### 8.3 禁止的模糊表达
- 禁止只写“系统每天会自动运行以下任务”，却不说明触发源。
- 禁止只写“Scheduler 定时任务清单”，却不说明这是代码层还是生产层。
- 禁止把“代码注册存在”写成“生产已启用”。

## 9. 本轮实施内容

### 9.1 要做
- 新增本设计文档。
- 更新 `task_scheduler.py` 的模块说明、注册区注释和 CLI help 文案。
- 视需要补充 `production_task_registry.md` 与 `bootstrap_runbook.md` 的措辞，使其与本设计完全一致。

### 9.2 不做
- 不修改 LaunchAgent 模板内容。
- 不安装或重载 LaunchAgent。
- 不更改任何任务执行时间。
- 不更改业务逻辑或交易日门禁。

## 10. 验收标准

1. `task_scheduler.py` 的顶部说明、关键注释和 CLI help 明确区分“生产入口”和“代码入口”。
2. `production_task_registry.md` 明确写出生产启用与代码注册是两套不同口径。
3. `bootstrap_runbook.md` 不再让读者误解 APScheduler 是当前生产真实调度器。
4. 文档中能明确回答以下问题，且答案不冲突：
   - 生产当前到底跑哪些任务
   - 这些任务由谁触发
   - 代码里还定义了哪些未启用任务
   - 以后调生产时间该改哪里

## 11. 风险与边界

### 11.1 本次接受的剩余风险
- APScheduler 与 LaunchAgent 仍然会同时存在两套“时间表达”。
- 本次通过明确分层来控制认知风险，而不是通过删掉其中一套来消除结构差异。

### 11.2 后续可独立处理的议题
- 是否把 APScheduler 的时间表达改成与 LaunchAgent 一致，仅用于减少阅读偏差。
- 是否把 `09:35` 调整为业务真正要求的 `09:30`。
- 是否进一步下沉出一份机器可读的“生产任务注册配置”，让文档由配置自动生成。
- 是否最终收敛为单一执行模型，例如完全 `launchd run-once` 化或完全常驻 scheduler 化。

## 12. 实施后预期结果

- 生产口径查询路径固定：
  - 先看 `config/launchd/`
  - 再看 `production_task_registry.md`
- 代码口径查询路径固定：
  - 看 `task_scheduler.py`
- 后续再出现调度问题时，可以先区分：
  - 是“生产没有启用”
  - 还是“代码虽然有定义，但并未接入生产”
- 文档、注释和 CLI 说明保持一致，不再把“双定义”误写成“双生产入口”。
