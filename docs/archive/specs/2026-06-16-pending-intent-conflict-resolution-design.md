# NeoTrade3 pending 意图冲突消解：旧意图优先（设计定稿）

日期：2026-06-16  
范围：NeoTrade3 低频模拟交易意图生成与执行链路

## 1. 背景与目标

### 1.1 背景问题
- 当前系统允许历史缺失补跑。若某个交易日未执行的 `pending` 意图被顺延到下一交易日，而下一交易日的 `daily_pipeline` 又生成了同 `code`、同方向的新意图，则两批意图会同时存在于 `manual.intents` 中。
- 之后执行 `trade_execution_rt` 时，旧意图可能先执行成功，而新意图继续尝试执行，最终触发 `position_missing`、重复买入判断或其他语义冲突。
- 这说明当前系统缺少“待执行意图冲突消解”规则。

### 1.2 目标
- 为 `pending` 意图建立明确的冲突消解规则。
- 采用“旧意图优先”的业务口径。
- 从意图生成阶段阻止重复语义进入状态机，而不是等到执行阶段事后补救。
- 保证补跑历史缺口后，不会因为重复意图再次制造执行失败。

## 2. 当前事实

### 2.1 意图生成位置
- 当前新意图在低频策略生成阶段写入 `manual.intents`。
- 已有辅助函数 `_lowfreq_find_pending_intent(...)`，但它当前只按 `intent_type + code + requested_date` 查找，无法解决“旧意图顺延到今天，而今天新信号又生成同 code 同方向意图”的冲突。

### 2.2 意图执行位置
- `trade_execution_rt_run_view(...)` 会收集所有 `status=pending` 且 `execute_date=target_date` 的意图执行。
- 当前执行前不会做“同 code 同方向重复 pending” 的归并或裁决。

### 2.3 当前已暴露的问题
- 缺失日补跑后，旧 `sell_intent` 顺延到今天并执行成功。
- 同天新生成的同 code `sell_intent` 继续执行时，触发 `position_missing`。
- 这说明冲突应在“生成新意图之前”解决，而不应仅依赖执行阶段兜底。

## 3. 设计原则

### 3.1 旧意图优先
- 只要旧意图仍为 `pending`，且业务方向相同，就优先保留旧意图。
- 新意图不覆盖旧意图，不取消旧意图，不重写旧意图的执行日。

### 3.2 源头阻断
- 冲突处理放在“生成新意图前”。
- 不将执行阶段作为主处理点。

### 3.3 最小必要范围
- 本轮只解决：
  - 同 `code`
  - 同 `intent_type`
  - 同为 `pending`
  - 且旧意图的 `execute_date` 不早于新意图的 `execute_date`
- 本轮不解决更复杂的跨方向反转问题。

## 4. 方案对比

### 4.1 方案 A：生成前去重（推荐）
- 在写入新意图前扫描现有 `pending` 意图。
- 命中冲突时，不生成新意图，只记录“跳过生成”原因。

优点：
- 从源头避免重复语义进入状态机。
- 能最大程度保持 `trade_execution_rt` 简洁。
- 最符合“旧意图优先”的业务定义。

缺点：
- 需要在意图生成路径加入额外的冲突检查逻辑。

### 4.2 方案 B：执行前去重
- 在 `trade_execution_rt` 收集 `execute_date=当日` 的 pending 时，按 `code + intent_type` 分组，只保留最早一条。

优点：
- 改动点集中在执行入口。

缺点：
- 重复意图已经进入状态，日间观察与账面语义仍被污染。
- 不适合作为主方案。

### 4.3 方案 C：生成前 + 执行前双重防护
- 生成阶段阻断大多数重复，执行阶段再做兜底。

优点：
- 最稳。

缺点：
- 第一轮修复不需要同时引入双层复杂度。

## 5. 采用方案

采用 `方案 A：生成前去重`。

原因：
- 用户已明确选择“旧意图优先”。
- 该方案最符合业务直觉：既然旧动作尚未完成，就不应让新动作在同方向上重复占位。
- 能直接阻止重复意图进入 `manual.intents`。

## 6. 冲突定义

### 6.1 冲突检查对象
- 仅检查现有 `manual.intents` 中满足以下条件的记录：
  - `status = pending`
  - `intent_type` 与候选新意图相同
  - `code` 与候选新意图相同

### 6.2 冲突成立条件
- 现有旧意图满足：
  - `status = pending`
  - `intent_type` 相同
  - `code` 相同
  - `execute_date >= 新意图的 execute_date`

### 6.3 不纳入本轮冲突的情况
- `status` 为 `executed`、`failed`、`cancelled`
- 同 `code` 但 `intent_type` 不同
- 无法识别 `code` 或 `intent_type` 的脏数据（仍按现有容错处理）

## 7. 数据流设计

### 7.1 新意图生成前
对每一条候选新意图：

1. 计算新意图的 `execute_date`
2. 扫描现有 `manual.intents`
3. 查找是否存在满足冲突条件的旧 `pending` 意图
4. 若存在：
   - 不写入新意图
   - 记录“跳过生成”结果
5. 若不存在：
   - 正常写入新意图

### 7.2 旧意图的处理
- 旧意图保持原状态不变
- 不修改其 `execute_date`
- 不追加额外 `attempt_count`
- 不因新意图出现而自动取消

## 8. 可观测性设计

### 8.1 跳过生成记录
- 当候选新意图因旧意图优先而被阻止生成时，必须留下结构化记录，至少包含：
  - `code`
  - `intent_type`
  - `requested_date`
  - `candidate_execute_date`
  - `blocked_by_intent_id`
  - `blocked_by_execute_date`
  - `reason = pending_conflict_older_intent_wins`

### 8.2 使用场景
- 便于在 `daily_pipeline` 或后续 ledger 中解释“为什么今天没有新生成这条意图”
- 便于排查是否存在误拦截

## 9. 边界处理

### 9.1 同 code 反方向
- 本轮不作为冲突处理。
- 例如：
  - 旧的是 `sell_intent`
  - 新的是 `buy_intent`
- 这类情况反映的是更高层业务反转，不在本轮最小修复范围。

### 9.2 已顺延到今天的旧意图
- 仍然由旧意图优先。
- 这是本次修复要保护的核心场景。

### 9.3 已失败或已取消的旧意图
- 不阻止新意图生成。
- 原因：这类旧动作已经终结，不应继续占用业务语义。

### 9.4 已执行的旧意图
- 不构成 `pending` 冲突。
- 若未来业务要求“同日已执行后不得再次生成同 code 同方向意图”，应单独设计第二阶段规则。

## 10. 验收标准

1. 当存在旧 `pending sell_intent` 顺延到今天时，今日 `daily_pipeline` 不再生成同 `code` 的新 `sell_intent`。
2. 当存在旧 `pending buy_intent` 顺延到今天时，今日 `daily_pipeline` 不再生成同 `code` 的新 `buy_intent`。
3. 若旧意图状态为 `executed / failed / cancelled`，不阻止新意图生成。
4. 补跑历史缺口后，再跑今日 `trade_execution_rt` 时，不应再因“同 code 同方向重复 pending”触发 `position_missing`。
5. 跳过生成必须留下结构化原因记录。

## 11. 建议测试用例

### 11.1 必测
- 旧 `pending sell_intent` 顺延到今天，新 `sell_intent` 生成时被拦截
- 旧 `pending buy_intent` 顺延到今天，新 `buy_intent` 生成时被拦截
- 旧意图为 `failed`，新意图允许生成
- 旧意图为 `cancelled`，新意图允许生成
- 旧意图为 `executed`，新意图允许生成

### 11.2 边界
- 同 `code` 但方向相反，不被本轮规则拦截
- 多条旧 `pending` 并存时，只要存在一条满足条件，即阻止新意图生成

## 12. 非目标

- 不在本轮处理跨方向冲突
- 不在本轮重写 `trade_execution_rt` 主执行流程
- 不在本轮引入“同日已执行后禁止同方向再生成”的扩展规则
- 不在本轮自动清洗历史脏状态
