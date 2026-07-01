# NeoTrade3 数值 0 显示为空占位修复（设计定稿）

日期：2026-06-16  
范围：当前主前端 `neotrade3-dashboard` 与旧 `apps/dashboard` 中把数值 `0` 误显示为占位符的问题

## 1. 背景与目标

- 当前主前端 `neotrade3-dashboard/src/pages/Overview.jsx` 中，`SimpleCard` 使用 `value || '--'` 作为显示逻辑。
- 旧 dashboard `apps/dashboard/static/dashboard.js` 中，`row.score ? ... : '-'`、`row.certainty ? ... : '-'` 也使用 truthy/falsy 语义判断是否显示数值。
- 这会把合法业务值 `0` 错误显示为 `--` 或 `-`，造成“0 个信号/0 个告警/0 分值”与“无数据”语义混淆。

目标：
- 保证合法数值 `0` 正常显示。
- 仅对真正缺失值显示占位符。
- 本次同时修复当前主前端和旧 dashboard 的同类问题，不扩大到其它数值格式化逻辑。

## 2. 设计范围

本次范围：
- `neotrade3-dashboard/src/pages/Overview.jsx`
- `apps/dashboard/static/dashboard.js`

非目标：
- 不重构为全局格式化工具函数。
- 不顺带修改其它页面中的格式化逻辑。
- 不改变占位符样式，只修正判空语义。

## 3. 方案比较

### 3.1 方案 A：显式缺失值判断
- 只在 `null`、`undefined`、空字符串时显示占位符。
- 数值 `0`、字符串 `"0"`、布尔值 `false` 不被误判为空。
- 改动最小，最贴合当前代码结构。

### 3.2 方案 B：统一先格式化为字符串再判空
- 先把输入都转成展示字符串，再判断是否为空串。
- 可行，但对这个问题偏重。

### 3.3 方案 C：抽公共格式化函数
- 为多个页面建立共享工具。
- 对当前单点修复来说改动超范围。

结论：
- 采用方案 A。

## 4. 实施设计

### 4.1 主前端
- 修改 `Overview.jsx` 中 `SimpleCard` 的显示逻辑。
- 不再使用 `value || '--'`。
- 改为显式判断缺失值后再显示占位符，确保 `0` 正常显示。

### 4.2 旧 dashboard
- 修改 `dashboard.js` 中 `row.score`、`row.certainty` 的显示逻辑。
- 只有在值为 `null/undefined` 时才显示 `-`。
- 有数值时继续使用 `toFixed(2)`，因此 `0` 应显示为 `0.00`。

## 5. 验证

- 主前端执行：
  - `npm run test -- --run`
  - `npm run build`
- 旧 dashboard 无独立测试时，以代码级校验为主，确保不会对缺失值调用 `toFixed()`。

## 6. 完成标准

- `Overview.jsx` 中 `SimpleCard` 遇到 `0` 时显示 `0`，不再显示 `--`。
- `dashboard.js` 中 `score=0`、`certainty=0` 时显示 `0.00`，不再显示 `-`。
- 前端测试与构建通过。
