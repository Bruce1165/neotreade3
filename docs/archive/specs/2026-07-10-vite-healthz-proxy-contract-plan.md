# Vite Healthz Proxy Contract 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-vite-healthz-proxy-contract-design.md`

## 1. 目标

本计划只覆盖 `vite.config.js` 中 `/healthz` 的开发代理 contract，对齐现有前端 helper 与部署文档对该路径的既有约定，不扩展到 `/api` target 可配置化、环境变量收口、页面逻辑或 Node 网关主题。

本轮目标只有三个：

1. 在 `server.proxy` 中新增 `/healthz` 到后端 API 的最小代理声明。
2. 在不扩大配置主题的前提下，完成最小语法/结构安全验证。
3. 仅在相对 `HEAD` 能隔离 `/healthz` 这一单点 contract 时提交。

本轮必须得到的核心结果：

- `vite.config.js` 中存在 `/healthz` proxy
- `/healthz` target 继续使用 API 地址字面量，不引入 `apiProxyTarget`
- 提交中不包含 `/api` target 可配置化
- 提交中不包含页面、helper、网关或文档改动

## 2. 不在本轮完成

- `apiProxyTarget` 常量化
- `/api` target 从字面量切到常量
- `NEOTRADE3_API_BASE_URL` 环境变量接入
- `src/services/api.js` 改动
- `server/gateway.js` 改动
- `DEPLOY.md` 改动
- 页面逻辑、健康检查交互或测试文件改动
- 全量前端测试矩阵

## 3. 当前实施起点

### 3.1 已知事实

- `HEAD` 版本的 [vite.config.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/vite.config.js) 只包含 `/api` 字面量代理，不包含 `/healthz`，也不包含 `apiProxyTarget`
- 当前工作区的 [vite.config.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/vite.config.js) 同时混有两类改动：
  - `apiProxyTarget` 常量化与 `/api` target 可配置化
  - `/healthz` dev proxy
- [api.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/services/api.js#L174) 已暴露 `checkHealth()`，调用路径是 `/healthz`
- [DEPLOY.md](file:///Users/mac/NeoTrade3/neotrade3-dashboard/DEPLOY.md) 已记录 `/healthz` 应透明代理到 API

### 3.2 结构性风险

- 最大风险不是新增 `/healthz` 本身，而是把 `apiProxyTarget` 与 `/api` 改动一起带入提交
- 如果顺手改动 helper、页面或网关，本轮会从“Vite proxy contract”扩大成跨层配置主题
- 如果因为隔离困难而直接接受整文件提交，本轮会丢失相对 `HEAD` 的单点可解释性

## 4. 实施原则

- 只改 `neotrade3-dashboard/vite.config.js`
- 只做 `/healthz` proxy contract
- `/healthz` target 使用既有 API 地址字面量：`http://127.0.0.1:18030`
- 不引入 `apiProxyTarget`
- 不改 `/api` 代理语义
- 不改页面、helper、网关、部署文档
- 若相对 `HEAD` 无法安全隔离 `/healthz` hunk，本轮结论应为“不提交”，不能静默扩大范围

## 5. 建议改动边界

允许改动文件：

- `neotrade3-dashboard/vite.config.js`

允许改动逻辑：

- `server.proxy` 下新增：
  - `'/healthz'`
  - `target: 'http://127.0.0.1:18030'`
  - `changeOrigin: true`

明确不改：

- 顶部新增 `apiProxyTarget`
- `/api` 的 `target` 写法
- 其他 `server` 配置项
- `test` / `build` 配置
- `neotrade3-dashboard/src/services/api.js`
- `neotrade3-dashboard/server/gateway.js`
- `neotrade3-dashboard/DEPLOY.md`

## 6. 总体分段

本计划建议分为四段执行：

- `VHP-R1`：冻结 `/healthz` contract 的精确边界
- `VHP-R2`：只实施 `/healthz` 字面量代理块
- `VHP-R3`：做最小语法/结构安全验证
- `VHP-R4`：隔离 `/healthz` hunk 并提交

## 7. 分段实施计划

### VHP-R1：冻结 `/healthz` contract 的精确边界

目标：

- 明确 `vite.config.js` 中哪些点位属于本轮 `/healthz` proxy，哪些相邻改动必须排除。

任务：

- 读取当前 [vite.config.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/vite.config.js)
- 用 `git show HEAD:neotrade3-dashboard/vite.config.js` 查看基线版本
- 用 `git diff HEAD -- neotrade3-dashboard/vite.config.js` 检查当前剩余 diff
- 只标记以下目标点位：
  - `proxy['/healthz']`
  - `target: 'http://127.0.0.1:18030'`
  - `changeOrigin: true`
- 显式排除：
  - `apiProxyTarget`
  - `/api` target 可配置化
  - 其他配置格式化噪音

完成判定：

- include / exclude 列表明确
- `HEAD`-relative diff 中 `/healthz` 与 `apiProxyTarget` 已清楚分开

### VHP-R2：只实施 `/healthz` 字面量代理块

目标：

- 在不扩大配置主题的前提下，为 Vite dev server 增加 `/healthz` 的最小代理能力。

任务：

- 在 `server.proxy` 中新增 `'/healthz'` 配置块
- 使用字面量 target：`'http://127.0.0.1:18030'`
- 保持 `/api` 现有写法不变

关键约束：

- 不引入 `apiProxyTarget`
- 不修改 `/api` block
- 不调整 `server.port`
- 不修改 `test` / `build` 配置
- 不修改任何其他文件

完成判定：

- `vite.config.js` 存在 `/healthz` 代理块
- `/api` block 保持 `HEAD` 语义
- 文件其他区域无边界外改动

### VHP-R3：做最小语法/结构安全验证

目标：

- 证明本轮只影响 Vite 代理 contract，不引入配置语法或结构错误。

任务：

- 检查最近编辑文件是否存在明显语法或结构问题
- 如有低成本方式，可运行最小配置相关验证
- 若失败原因暴露的是环境变量、网关或页面主题，则停止并报告边界问题

完成判定：

- `vite.config.js` 无明显语法或结构错误
- 未引入额外边界外修改

### VHP-R4：隔离 `/healthz` hunk 并提交

目标：

- 生成一个单一目的的切片，只表达 `vite.config.js` 中 `/healthz` 的 dev proxy contract。

任务：

- 检查 `git diff HEAD -- neotrade3-dashboard/vite.config.js`
- 只暂存 `/healthz` 的最小 hunk
- 排除 `apiProxyTarget` 与 `/api` target 可配置化
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含 `/healthz` proxy
- staged diff 不包含 `apiProxyTarget`
- staged diff 不包含 `/api` target 改写
- staged diff 不包含其他文件改动

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先对照 `HEAD` 与工作区版本的 `vite.config.js`
2. 明确 `/healthz` 与 `apiProxyTarget` 的 diff 分界
3. 只构造 `/healthz` 字面量代理块
4. 做最小语法/结构检查
5. 再复核 `HEAD`-relative diff
6. 只暂存 `/healthz` hunk

原因：

- 先冻结边界再改配置，可以避免把“看起来更整洁”的常量化一起带入提交
- 先确认结构安全，再决定是否提交，可以把配置主题失真风险压到最低

## 9. 建议提交切分

建议单一提交：

### Commit VHP：vite /healthz proxy contract

范围：

- `vite.config.js` 中 `/healthz` 代理块的最小 hunk

目的：

- 让 Vite 开发环境下的 `/healthz` 路径与现有 helper / 部署文档保持一致

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成 `/healthz` + `apiProxyTarget` 的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `vite.config.js` 已包含 `/healthz` 代理块
2. `/healthz` target 使用 `http://127.0.0.1:18030` 字面量
3. `vite.config.js` 无明显语法或结构错误
4. 提交中不包含 `apiProxyTarget` 与 `/api` target 改写
5. 提交中不包含页面、helper、网关或文档改动

## 11. 风险提示

- 主要风险是当前工作区里 `/healthz` 与 `apiProxyTarget` 同时存在，隔离时必须逐 hunk 对照 `HEAD`
- 第二风险是如果为了“顺手整理”而把 `/api` 一起收口，本轮会从路径 contract 扩大成配置治理
- 第三风险是若验证失败被误判为需要修改 helper 或网关，会越过当前批准边界

## 12. 结论

本计划不是 Vite 配置整理计划，而是一条更窄的单点 contract 线，目标只有三件事：

- 只补 `/healthz` 字面量代理块
- 只做最小语法/结构安全验证
- 只在相对 `HEAD` 可安全隔离时提交
