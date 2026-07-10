# Vite Healthz Proxy Contract Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `vite.config.js` 中 `/healthz` 的开发代理 contract，对齐当前前端 API helper 与部署文档的约定，不改 `/api` 代理目标收口、不改页面逻辑、不改 Node 网关实现。

目标是：

- 为 [vite.config.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/vite.config.js) 增加 `/healthz` 到后端 API 的开发代理
- 让 [api.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/services/api.js#L174) 的 `checkHealth()` 在 Vite 开发环境下具备一致的代理路径语义
- 将 `vite.config.js` 当前相对 `HEAD` 的配置漂移收口为单点 proxy contract 主题

本切片不是：

- `apiProxyTarget` 环境变量收口
- `/api` 代理目标可配置化
- `server/gateway.js` 行为调整
- `DEPLOY.md` 文档改写
- 前端页面、测试或交互改动

## 2. Scope

Included:

- `neotrade3-dashboard/vite.config.js`
- 只针对 `/healthz` 的 dev proxy contract

Excluded:

- `neotrade3-dashboard/src/pages/*`
- `neotrade3-dashboard/src/services/api.js`
- `neotrade3-dashboard/server/gateway.js`
- `apiProxyTarget` 常量化
- `/api` target 从字面量切到常量

## 3. Existing Context

当前代码与文档已给出可核验证据：

- [api.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/services/api.js#L174) 暴露 `checkHealth()`，其调用路径是 `/healthz`
- [DEPLOY.md](file:///Users/mac/NeoTrade3/neotrade3-dashboard/DEPLOY.md) 明确记录：
  - `/api/* 或 /healthz -> 127.0.0.1:18030`
  - 通过网关访问 `/healthz` 应返回 API 的 `status=ok`
- [vite.config.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/vite.config.js) 当前工作区改动同时包含两类主题：
  1. `apiProxyTarget` 常量与 `/api` target 可配置化
  2. `/healthz` dev proxy
- [server/gateway.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/server/gateway.js) 已支持 `/healthz` 路径，但这属于网关主题，不应混入本轮

现状风险：

- 如果把 `/healthz` proxy 与 `apiProxyTarget` 常量化一起提交，本轮会从“proxy contract”扩大成“配置收口”
- 如果顺手修改 API helper、页面探活逻辑或文档，本轮会失去单一目的
- 如果跳过 `/healthz` proxy，这条路径在 Vite dev server 下与既有 helper / 文档契约不一致

## 4. Approach Options

### Option A: 只补 `/healthz` dev proxy（推荐）

仅处理：

- `vite.config.js` 中 `/healthz` 的代理声明

Pros:

- 边界最窄，直接对齐现有 helper 与部署文档
- 不引入页面或网关主题
- 提交目的单一，容易与 `HEAD` 对照说明

Cons:

- `apiProxyTarget` 常量化将留待后续独立处理

### Option B: `/healthz` proxy + `apiProxyTarget` 常量化一起做

Pros:

- 一次把 Vite 代理配置“看起来”整理完整

Cons:

- 混合了“路径 contract”和“target 可配置化”两类主题
- 不符合窄切片原则

### Option C: 暂不处理 Vite，转去页面主题

Pros:

- 优先处理视觉上更显眼的页面漂移

Cons:

- 放弃当前最窄、最可解释的配置入口
- `/healthz` 在 dev 环境下继续缺少与文档一致的代理 contract

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `vite.config.js`
  - 为 Vite dev server 暴露 `/healthz` 到 API 的透明代理
- `/healthz`
  - 在开发环境下与既有 helper / 部署文档保持一致路径语义
- `apiProxyTarget`
  - 继续视作独立配置主题，不在本轮处理

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. `server.proxy` 中新增 `/healthz`
2. `/healthz` target 直接指向既有 API 地址字面量

本轮不允许顺手改动：

- `/api` target 从字面量切到常量
- 新增 `apiProxyTarget`
- 其他 dev server 选项
- API helper 与页面探活逻辑

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改 `src/services/api.js`
- 不修改 `server/gateway.js`
- 不修改 `DEPLOY.md`
- 不修改页面与测试文件
- 若验证暴露的是环境变量、网关或页面主题问题，应暂停并报告边界问题，不能静默扩大范围

## 6. Testing Design

验证优先采用：

1. `vite.config.js` 最小语法/结构检查

如存在现成配置或 API helper 测试且能低成本复用，可再做最小验证，但默认不要求新增测试。

默认不要求：

- 新增独立测试文件
- 修改页面测试
- 全量前端测试矩阵

原因：

- 本轮是 Vite 配置 contract，对语法与结构安全的要求高于新增测试职责

## 7. Validation

预期验证方式：

- 检查 `vite.config.js` 最近编辑后无语法/结构错误
- 如必要，再复用与 `/healthz` 相关的最小现有验证

如编辑过程中出现最近文件的明显语法/结构错误，再做最小修正。

## 8. Commit Boundary

目标提交应限制为：

- `vite.config.js` 中 `/healthz` proxy 的最小 hunk

必须排除：

- `apiProxyTarget` 常量
- `/api` target 可配置化
- 页面、helper、网关与文档改动

若相对 `HEAD` 无法将 `/healthz` proxy 与 `apiProxyTarget` 收口安全隔离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
