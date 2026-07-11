# Docs Index

## 目的

本目录承载 NeoTrade3 的第一方文档。

当前正式文档按以下层级理解：

1. `PROJECT_STATUS.md`
   - 当前状态真相源
2. `docs/handoffs/`
   - 会话续接层
3. `docs/superpowers/specs/`
   - design / plan / task-list / contract-definition
4. `docs/archive/`
   - 历史留存层

## 子目录说明

- `architecture/`
  - 架构与迁移总图
- `governance/`
  - 文档与目录治理规范
- `handoffs/`
  - 当前活跃续接文档
- `superpowers/specs/`
  - 活跃 design / plan / task-list 文档池
- `archive/`
  - 已退出活跃路径的历史材料
- `operations/`
  - 运行说明、runbook、维护记录
- `migration/`
  - 迁移映射、功能盘点、独立性原则

## 使用规则

- 当前边界、当前真相、当前下一步，以 `PROJECT_STATUS.md` 为准
- handoff 不能替代当前状态真相源
- archive 材料不能作为当前正式口径直接引用
- 新增目录必须带 `README.md`，并写明 owner、用途与退出条件
