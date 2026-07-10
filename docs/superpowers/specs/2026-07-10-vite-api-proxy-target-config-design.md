# Vite API Proxy Target Config Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `vite.config.js` 中开发代理 target 的可配置化收口：引入 `NEOTRADE3_API_BASE_URL` 对应的单点 `apiProxyTarget`，并让 `/api` 与 `/healthz` 共享该 target，不改页面逻辑、不改 Node 网关实现、不改部署文档。

目标是：

- 为 [vite.config.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/vite.config.js) 的 dev proxy 提供单点 target 配置入口
- 让 `/api` 与 `/healthz` 在 Vite 开发环境下共享同一 API 基地址来源
- 将当前 `vite.config.js` 相对 `HEAD` 的剩余配置漂移收口为单一“proxy target configurable”主题

本切片不是：

- 新增或修改页面、测试、API helper 逻辑
- 修改 [server/gateway.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/server/gateway.js) 的代理行为
- 改写 [DEPLOY.md](file:///Users/mac/NeoTrade3/neotrade3-dashboard/DEPLOY.md) 文档口径
- 调整 Vite 的其他 `server` / `build` / `test` 选项
- 继续处理 `App.jsx` 缩进噪音或页面大主题

## 2. Scope

Included:

- `neotrade3-dashboard/vite.config.js`
- `apiProxyTarget` 常量
- `/api` 与 `/healthz` 的 `target` 从字面量切到共享常量

Excluded:

- `neotrade3-dashboard/src/pages/*`
- `neotrade3-dashboard/src/services/api.js`
- `neotrade3-dashboard/server/gateway.js`
- `neotrade3-dashboard/DEPLOY.md`
- 新增测试文件或页面断言

## 3. Existing Context

当前代码与文档已给出可核验证据：

- 当前 [vite.config.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/vite.config.js) 工作区剩余 diff 只包含：
  1. 新增 `apiProxyTarget = process.env.NEOTRADE3_API_BASE_URL || 'http://127.0.0.1:18030'`
  2. 将 `/api` target 改为 `apiProxyTarget`
  3. 将 `/healthz` target 改为 `apiProxyTarget`
- [api.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/services/api.js#L174) 已暴露 `checkHealth()`，其调用路径是 `/healthz`
- [server/gateway.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/server/gateway.js#L37) 已存在 `process.env.NEOTRADE3_API_BASE_URL || DEFAULT_API_BASE`，说明同名环境变量在前端网关侧已有客观使用场景
- [DEPLOY.md](file:///Users/mac/NeoTrade3/neotrade3-dashboard/DEPLOY.md) 当前仍以 `127.0.0.1:18030` 为基线路径说明，但本轮不改文档

现状风险：

- 如果继续保留两处字面量 target，Vite 配置里的 API 地址来源会分散在多个字段，后续调整成本更高
- 如果顺手把网关、helper 或文档一起改掉，本轮会从“配置收口”扩大成跨层主题
- 如果只切 `/api` 不切 `/healthz`，会把同一 target 来源拆成两个不一致的职责点

## 4. Approach Options

### Option A: 用 `apiProxyTarget` 同时收口 `/api` 与 `/healthz`（推荐）

仅处理：

- `vite.config.js` 顶部新增 `apiProxyTarget`
- `/api` target 切到 `apiProxyTarget`
- `/healthz` target 切到 `apiProxyTarget`

Pros:

- 边界仍保持单文件、单主题
- `/api` 与 `/healthz` 的 target 来源保持一致
- 与当前工作区剩余 diff 完全对齐，容易解释相对 `HEAD` 的变化

Cons:

- 会把已提交过的 `/healthz` 字面量 target 再切换到常量，需要再次明确这属于“配置来源收口”而非“路径 contract”

### Option B: 只收口 `/api` target

Pros:

- 看起来改动更少

Cons:

- `/api` 与 `/healthz` 会重新分裂成两种 target 来源
- 违反当前 diff 已呈现出的单一配置主题

### Option C: 暂不处理 Vite，转回页面主题

Pros:

- 可以优先处理视觉或交互更显眼的问题

Cons:

- 放弃当前最窄、最可解释的剩余配置线
- `vite.config.js` 继续保留未完成的配置收口

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `vite.config.js`
  - 维护 Vite dev proxy 的共享 API target 来源
- `apiProxyTarget`
  - 负责解析 `NEOTRADE3_API_BASE_URL`，并在未设置时回退到 `http://127.0.0.1:18030`
- `/api` 与 `/healthz`
  - 继续保留原有路径语义，只共享 target 来源，不改变路径 contract

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. 顶部新增 `apiProxyTarget`
2. `/api` 的 `target` 从字面量切到 `apiProxyTarget`
3. `/healthz` 的 `target` 从字面量切到 `apiProxyTarget`

本轮不允许顺手改动：

- `changeOrigin`
- `server.port`
- 其他 `proxy` path
- `test` / `build` 配置
- 页面、helper、网关与文档

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改 `src/services/api.js`
- 不修改 `server/gateway.js`
- 不修改 `DEPLOY.md`
- 不修改页面与测试文件
- 若验证暴露的是环境变量约定缺失、网关语义或部署文档问题，应暂停并报告边界问题，不能静默扩大范围

## 6. Testing Design

验证优先采用：

1. `vite.config.js` 的最小语法/结构检查

如存在低成本的配置级验证手段，可再做最小补充，但默认不要求新增测试。

默认不要求：

- 新增独立测试文件
- 修改页面测试
- 全量前端测试矩阵

原因：

- 本轮是配置来源收口，核心风险在语法与边界，而不是页面行为

## 7. Validation

预期验证方式：

- 检查 `vite.config.js` 最近编辑后无语法/结构错误
- 检查 staged diff 只包含 `apiProxyTarget` 与两个 `target` 切换

如编辑过程中出现最近文件的明显语法/结构错误，再做最小修正。

## 8. Commit Boundary

目标提交应限制为：

- `vite.config.js` 中 `apiProxyTarget` 与 `/api`、`/healthz` target 的最小 hunk

必须排除：

- 其他 `proxy` path 或 `server` 选项改动
- 页面、helper、网关与文档改动
- 格式化噪音与无关整理

若相对 `HEAD` 无法将该主题安全隔离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
