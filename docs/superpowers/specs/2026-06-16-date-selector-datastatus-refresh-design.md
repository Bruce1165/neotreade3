# NeoTrade3 DateSelector 数据状态刷新收敛（设计定稿）

日期：2026-06-16  
范围：`neotrade3-dashboard/src/components/DateSelector.jsx` 及其测试

## 1. 背景与目标

- 当前 `DateSelector` 在挂载时只调用一次 `getDataStatus()`。
- 组件后续会持续使用 `dataStatus` 参与“最新可用日期”“暂无本地数据”“自动回退到最新可用日期”的判断。
- 当用户切换日期或手动点击“刷新”后，`dataStatus` 可能仍是旧值，导致提示和自动回退依据陈旧。

目标：
- `selectedDate` 变化时重新拉取 `dataStatus`。
- 点击“刷新”按钮时也重新拉取 `dataStatus`。
- 保持改动局限在 `DateSelector` 内部，不扩散到父组件数据流。

## 2. 设计范围

本次范围：
- `neotrade3-dashboard/src/components/DateSelector.jsx`
- `neotrade3-dashboard/src/components/DateSelector.test.jsx`

非目标：
- 不把 `dataStatus` 提升到父组件管理。
- 不改变现有提示文案。
- 不重构交易日逻辑与自动回退策略。

## 3. 方案比较

### 3.1 方案 A：组件内收敛刷新逻辑
- 在 `DateSelector` 内抽取 `loadDataStatus()`。
- `selectedDate` 变化时调用。
- 点击“刷新”按钮时，先调用 `loadDataStatus()`，再调用外部 `onRefresh()`。
- 优点：改动最小，覆盖“日期变化 + 手动刷新”两个入口。

### 3.2 方案 B：父组件统一管理
- `DateSelector` 不自行拉取 `dataStatus`，由父组件传入。
- 优点：数据流更显式。
- 缺点：改动会扩散到页面层，超出本次范围。

### 3.3 方案 C：仅跟随日期变化
- 只把 `getDataStatus()` 绑定到 `selectedDate`。
- 缺点：不能解决手动刷新后状态仍陈旧的问题。

结论：
- 采用方案 A。

## 4. 实施设计

### 4.1 组件逻辑
- 抽取 `loadDataStatus()`，负责调用 `getDataStatus()` 并写入 `setDataStatus`。
- 删除当前仅挂载一次的 `useEffect([])`。
- 在 `selectedDate` 变化的 effect 中，保留 `getTradingDay(selectedDate)`，并额外调用 `loadDataStatus()`。
- 将刷新按钮改为使用组件内部 handler：
  - 先执行 `loadDataStatus()`
  - 再执行外部 `onRefresh()`

### 4.2 测试
- 保留现有测试。
- 新增测试验证：
  - 初次渲染时会调用 `getDataStatus()`
  - 点击“刷新”后会再次调用 `getDataStatus()`
  - 点击“刷新”后仍会调用外部 `onRefresh()`

## 5. 验证

- 执行 `npm run test -- --run`
- 执行 `npm run build`
- 执行 `npm run lint`

## 6. 完成标准

- `DateSelector` 不再只在挂载时拉一次 `dataStatus`。
- 日期变化与手动刷新都能更新 `dataStatus`。
- 组件测试、构建、lint 均通过。
