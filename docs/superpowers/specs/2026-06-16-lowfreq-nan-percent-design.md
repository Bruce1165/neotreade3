# NeoTrade3 Lowfreq 百分比缺失值显示修复（设计定稿）

日期：2026-06-16  
范围：`neotrade3-dashboard/src/pages/Lowfreq.jsx` 中已确认的两处 `NaN%` 风险及对应测试

## 1. 背景与目标

- 当前 `Lowfreq.jsx` 在“市场阶段”区域直接渲染：
  - `market_breadth * 100`
  - `market_return_20d * 100`
- 当后端字段缺失或为非数值时，乘法会先得到 `NaN`，最终页面显示为 `NaN%`。
- 这会把“字段缺失”误显示成像是合法计算结果的数值文本。

目标：
- 只修复当前已确认的两处 `NaN%` 风险。
- 有效数值保持当前展示格式。
- 缺失值显示占位符，不扩大到同文件其它百分比逻辑。

## 2. 设计范围

本次范围：
- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`

非目标：
- 不统一重构 `Lowfreq.jsx` 中所有百分比输出。
- 不抽公共格式化工具。
- 不调整颜色、文案或布局。

## 3. 方案比较

### 3.1 方案 A：局部显式判空
- 只对 `market_breadth` 和 `market_return_20d` 做显式数值有效性检查。
- 有值时再格式化，无值时显示占位符。
- 改动最小，最贴合本次范围。

### 3.2 方案 B：抽本文件局部格式化函数
- 在 `Lowfreq.jsx` 内新增小型百分比格式化函数。
- 可减少重复，但对本次“两处修复”来说略超需求。

### 3.3 方案 C：抽全局工具函数
- 为多个页面建立共享格式化能力。
- 本次单点修复不需要。

结论：
- 采用方案 A。

## 4. 实施设计

### 4.1 页面逻辑
- 仅修改“市场宽度”和“20日收益”两处。
- 使用显式判断确保值为有限数值后，才做 `* 100` 和 `toFixed(...)`。
- 若值缺失或不是有限数值，显示占位符 `--`。

### 4.2 测试
- 保留现有 `Lowfreq.test.jsx`。
- 新增一条定点测试：
  - 当 `market_breadth` 与 `market_return_20d` 缺失时
  - 页面不应出现 `NaN%`
  - 页面应显示占位符

## 5. 验证

- 执行 `npm run test -- --run src/pages/Lowfreq.test.jsx`
- 执行 `npm run test -- --run`
- 执行 `npm run build`
- 执行 `npm run lint`

## 6. 完成标准

- `Lowfreq.jsx` 中两处已确认的百分比字段不再显示 `NaN%`。
- 字段缺失时显示占位符。
- 前端测试、构建、lint 均通过。
