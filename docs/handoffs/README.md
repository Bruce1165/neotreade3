# Active Handoffs

## 目的

本目录只存放当前仍有续接价值的 handoff 文档。

handoff 的职责是：

- 记录事实
- 记录约束
- 记录证据路径
- 提供下一会话恢复顺序

handoff 不是当前状态真相源；当前正式边界仍以 `PROJECT_STATUS.md` 为准。

## 使用规则

- handoff 文档应尽量保持命名格式：
  - `YYYY-MM-DD_主题_handoff.md`
- handoff 只写 NeoTrade3 当前主题，不整段复制 NeoTrade2 运行说明
- 如果 handoff 已失去续接价值，只剩历史价值，应迁入 `docs/archive/handover/`

## 退出条件

以下任一成立时，handoff 应考虑迁出活跃目录：

- 内容已被 `PROJECT_STATUS.md` 吸收
- 已被新的 handoff 明确替代
- 只剩历史参考价值，不再用于新会话恢复
