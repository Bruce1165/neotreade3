# Vite API Proxy Target Config 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-vite-api-proxy-target-config-design.md`

## 1. 目标

本计划只覆盖 `vite.config.js` 中开发代理 target 的可配置化收口：新增 `apiProxyTarget`，并让 `/api` 与 `/healthz` 共享该 target，不扩展到页面逻辑、Node 网关、部署文档或其他 Vite 配置主题。

本轮目标只有三个：

1. 在 `vite.config.js` 顶部新增 `apiProxyTarget`，接收 `NEOTRADE3_API_BASE_URL` 或回退到 `http://127.0.0.1:18030`。
2. 将 `/api` 与 `/healthz` 的 `target` 从字面量切到 `apiProxyTarget`。
3. 在不扩大主题的前提下，完成最小语法/结构安全验证并仅在相对 `HEAD` 可安全隔离时提交。

本轮必须得到的核心结果：

- `vite.config.js` 中存在 `apiProxyTarget`
- `/api` 与 `/healthz` 的 `target` 都引用 `apiProxyTarget`
- 提交中不包含其他 `proxy` path、页面、helper、网关或文档改动
- 提交中不包含格式化噪音或无关整理

## 2. 不在本轮完成

- 页面逻辑或页面测试调整
- `src/services/api.js` 改动
- `server/gateway.js` 改动
- `DEPLOY.md` 改动
- 新增代理 path
- `server.port`、`build`、`test` 配置改动
- 全量前端测试矩阵

## 3. 当前实施起点

### 3.1 已知事实

- 当前 [vite.config.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/vite.config.js) 相对 `HEAD` 的剩余 diff 只包含三点：
  - 顶部新增 `apiProxyTarget = process.env.NEOTRADE3_API_BASE_URL || 'http://127.0.0.1:18030'`
  - `/api` 的 `target` 改为 `apiProxyTarget`
  - `/healthz` 的 `target` 改为 `apiProxyTarget`
- `HEAD` 当前已经包含 `/healthz` 的 dev proxy，因此本轮不是路径 contract 新增，而是 target 来源收口
- [api.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/services/api.js#L174) 已使用 `/healthz`
- [server/gateway.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/server/gateway.js#L37) 已读取 `NEOTRADE3_API_BASE_URL`

### 3.2 结构性风险

- 最大风险不是新增常量本身，而是顺手改动其他 `server` 配置，导致本轮从“target 来源收口”扩大成“Vite 配置整理”
- 如果只修改 `/api` 不修改 `/healthz`，会把同一 API target 来源拆成两套语义
- 如果把页面、网关或文档问题一起处理，本轮会失去单文件、单主题边界

## 4. 实施原则

- 只改 `neotrade3-dashboard/vite.config.js`
- 只做 `apiProxyTarget` 与 `/api`、`/healthz` target 切换
- 不改 `changeOrigin`
- 不改 `server.port`
- 不改其他 `server` / `build` / `test` 配置
- 不改页面、helper、网关、部署文档
- 若相对 `HEAD` 无法安全隔离该主题，本轮结论应为“不提交”，不能静默扩大范围

## 5. 建议改动边界

允许改动文件：

- `neotrade3-dashboard/vite.config.js`

允许改动逻辑：

- 新增：
  - `const apiProxyTarget = process.env.NEOTRADE3_API_BASE_URL || 'http://127.0.0.1:18030'`
- 修改：
  - `proxy['/api'].target`
  - `proxy['/healthz'].target`

明确不改：

- `proxy['/api'].changeOrigin`
- `proxy['/healthz'].changeOrigin`
- 其他 proxy path
- `server.port`
- `test` / `build` 配置
- `neotrade3-dashboard/src/services/api.js`
- `neotrade3-dashboard/server/gateway.js`
- `neotrade3-dashboard/DEPLOY.md`

## 6. 总体分段

本计划建议分为四段执行：

- `VPT-R1`：冻结 target 收口的精确边界
- `VPT-R2`：只实施 `apiProxyTarget` 与两个 `target` 切换
- `VPT-R3`：做最小语法/结构安全验证
- `VPT-R4`：复核 staged diff 并提交

## 7. 分段实施计划

### VPT-R1：冻结 target 收口的精确边界

目标：

- 明确 `vite.config.js` 中哪些点位属于本轮 target 来源收口，哪些相邻改动必须排除。

任务：

- 读取当前 [vite.config.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/vite.config.js)
- 用 `git diff HEAD -- neotrade3-dashboard/vite.config.js` 检查当前剩余 diff
- 只标记以下目标点位：
  - `apiProxyTarget`
  - `/api` 的 `target`
  - `/healthz` 的 `target`
- 显式排除：
  - `changeOrigin`
  - 其他 `server` 配置项
  - 页面、helper、网关与文档主题

完成判定：

- include / exclude 列表明确
- `HEAD`-relative diff 中只剩本轮 target 收口主题

### VPT-R2：只实施 `apiProxyTarget` 与两个 `target` 切换

目标：

- 在不扩大配置主题的前提下，为 `/api` 与 `/healthz` 提供统一的 target 来源。

任务：

- 在文件顶部新增 `apiProxyTarget`
- 将 `/api` 的 `target` 从字面量切到 `apiProxyTarget`
- 将 `/healthz` 的 `target` 从字面量切到 `apiProxyTarget`

关键约束：

- 不调整 `changeOrigin`
- 不修改其他 `proxy` path
- 不调整 `server.port`
- 不修改其他文件

完成判定：

- `vite.config.js` 中新增 `apiProxyTarget`
- `/api` 与 `/healthz` 的 `target` 都引用 `apiProxyTarget`
- 文件其他区域无边界外改动

### VPT-R3：做最小语法/结构安全验证

目标：

- 证明本轮只影响 Vite 代理 target 来源，不引入语法或结构错误。

任务：

- 检查最近编辑文件是否存在明显语法或结构问题
- 如有低成本方式，运行最小配置级语法校验
- 若失败原因暴露的是环境变量约定、网关或页面主题，则停止并报告边界问题

完成判定：

- `vite.config.js` 无明显语法或结构错误
- 未引入额外边界外修改

### VPT-R4：复核 staged diff 并提交

目标：

- 生成一个单一目的的切片，只表达 `vite.config.js` 中 proxy target 来源收口。

任务：

- 检查 `git diff HEAD -- neotrade3-dashboard/vite.config.js`
- 暂存本轮目标 hunk
- 复核 staged diff 只包含：
  - `apiProxyTarget`
  - `/api` target 切换
  - `/healthz` target 切换
- 仅在纯度满足时提交

完成判定：

- staged diff 不包含其他 `server` / `build` / `test` 改动
- staged diff 不包含页面、helper、网关或文档改动
- staged diff 不包含格式化噪音

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先对照当前 `vite.config.js` 与相对 `HEAD` 的剩余 diff
2. 明确只有 `apiProxyTarget` 与两个 `target` 切换属于本轮
3. 实施最小改动
4. 做最小语法/结构检查
5. 复核 staged diff 纯度
6. 再决定是否提交

原因：

- 先冻结边界再改配置，可以避免把同文件里的其他整理需求误带入
- 先验证结构安全，再提交，可以把配置收口切片保持在最小可解释范围内

## 9. 建议提交切分

建议单一提交：

### Commit VPT：vite api proxy target config

范围：

- `vite.config.js` 中 `apiProxyTarget` 与 `/api`、`/healthz` target 切换的最小 hunk

目的：

- 让 Vite 开发代理中的 `/api` 与 `/healthz` 共享同一 API target 来源

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成配置整理混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `vite.config.js` 已包含 `apiProxyTarget`
2. `/api` 与 `/healthz` 的 `target` 都引用 `apiProxyTarget`
3. `vite.config.js` 无明显语法或结构错误
4. 提交中不包含其他 `server` / `build` / `test` 改动
5. 提交中不包含页面、helper、网关、文档或格式化噪音

## 11. 风险提示

- 主要风险是把这条线误扩成“Vite 配置整理”，因此必须限制在单文件、单主题
- 第二风险是若只切 `/api` 不切 `/healthz`，会造成 target 来源重新分裂
- 第三风险是如果验证失败后顺手去补网关或文档，会越过当前批准边界

## 12. 结论

本计划不是 Vite 配置升级计划，而是一条更窄的单点收口线，目标只有三件事：

- 只新增 `apiProxyTarget`
- 只把 `/api` 与 `/healthz` 的 `target` 切到该常量
- 只做最小语法/结构安全验证，并在可安全隔离时提交
