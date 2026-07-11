# Specs Workspace

## 目的

本目录存放 NeoTrade3 的活跃 design / plan / task-list / contract-definition / repo-audit 文档。

## 允许文档类型

- `*-design.md`
- `*-plan.md`
- `*-task-list.md`
- `*-contract-definition.md`
- `*-repo-audit.md`

## 使用规则

- 命名应保持日期前缀，便于排序与追溯
- 新 spec 如果替代旧 spec，应在文内写明替代关系
- 如果某份 spec 只剩历史价值，不再服务当前活跃实施，应迁入 archive，而不是长期堆在活跃目录
- spec 不是当前状态真相源；当前边界仍以 `PROJECT_STATUS.md` 为准

## 退出条件

spec 文档在以下情况下应从活跃目录迁出：

- 已完成实现并且后续不再作为活跃约束使用
- 已被新的 design / plan 明确替代
- 只剩历史复盘价值
