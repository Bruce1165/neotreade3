# NeoTrade3 V3 外网 Basic Auth 认证方案

日期：2026-06-17  
范围：为 `V3` 当前正式外网入口增加“只输入密码”的 `HTTP Basic Auth` 认证，沿用旧 `V2` 的认证方式与密码变量名。

## 1. 背景

- 当前 `V3` 外网入口已经切换到：
  - `cpolar -> Node 前端网关 -> neotrade3-dashboard/dist`
  - `/api/*` 与 `/healthz` 由前端网关再代理到 `127.0.0.1:18030`
- 用户明确要求：
  - 给 `V3` 外网访问增加一个“只需要输入密码”的安全认证机制
- 用户已确认的口径：
  - 认证方式：沿用旧 `V2` 的 `HTTP Basic Auth`
  - 认证行为：浏览器弹原生密码框
  - 密码来源：继续使用旧变量名 `DASHBOARD_PASSWORD`

## 2. 旧 V2 认证证据

### 2.1 服务端口径

- 旧 `V2` 后端强依赖环境变量 `DASHBOARD_PASSWORD`
- 若缺失该变量，服务直接启动失败
- 认证逻辑只校验密码，不关心用户名
- 证据见：
  - [backend.md](file:///Users/mac/NeoTrade2/TECHNICAL_DOCS/reference/code_wiki/backend.md#L12-L16)
  - [app.py](file:///Users/mac/NeoTrade2/backend/app.py#L493-L500)

### 2.2 浏览器行为

- 旧 `V2` 的对外行为是：
  - 返回 `401`
  - 触发浏览器原生 Basic Auth 密码框
- 调试文档中明确把 `401 Basic Auth challenge` 视为正常入口行为
- 证据见：
  - [debug-cpolar-dashboard-down.md](file:///Users/mac/NeoTrade2/debug-cpolar-dashboard-down.md#L42-L42)
  - [debug-dashboard-404.md](file:///Users/mac/NeoTrade2/debug-dashboard-404.md#L28-L28)

## 3. 当前 V3 入口证据

- 当前正式外网入口只有前端网关：
  - [gateway.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/server/gateway.js)
- 当前网关负责：
  - 提供前端静态资源
  - 代理 `/api/*`
  - 代理 `/healthz`
  - 提供 `/_gateway/healthz`
- 因此 Basic Auth 必须落在网关层，而不是前端 React 页面层

## 4. 目标

- 让 `V3` 外网入口具备和旧 `V2` 一致的“只输入密码”访问体验
- 让页面、静态资源、接口、健康检查全部统一受保护
- 不引入登录页、session、token、cookie 等新机制
- 不把认证扩散到 API 内部业务层

## 5. 方案比较

### 5.1 方案 A：网关层全站 Basic Auth，推荐

- 在 `neotrade3-dashboard/server/gateway.js` 增加 Basic Auth
- 所有进入网关的请求，先认证，再决定是静态返回还是代理到 API

优点：
- 与旧 `V2` 最接近
- 安全边界最清晰
- 改动范围最小
- 不会出现“页面有密码但 API 没密码”的漏洞

缺点：
- 本机访问 `127.0.0.1:5174` 同样需要密码

### 5.2 方案 B：只对外网请求启用 Basic Auth

- 本机 loopback 放行，外网请求认证

优点：
- 本机联调更方便

缺点：
- 需要定义“什么算外网请求”
- 比旧 `V2` 口径更复杂
- 容易引入错误的白名单假设

### 5.3 方案 C：只保护页面，不保护 API

- 首页和静态资源要求密码，API 不要求

优点：
- 实现最省

缺点：
- 安全边界错误
- 不能接受

### 5.4 结论

- 采用方案 A。
- 原因：
  - 最接近旧 `V2`
  - 实现边界最清楚
  - 安全上没有“页面/API 分裂”漏洞

## 6. 认证作用范围与放行规则

### 6.1 必须受保护的路径

- `/`
- 所有静态资源路径
- 所有前端 SPA 路由回退到的 `index.html`
- 所有 `/api/*`
- `/healthz`
- `/_gateway/healthz`

### 6.2 认证规则

- 只校验密码，不关心用户名
- 密码来自 `Authorization: Basic ...`
- 实际校验值来自环境变量 `DASHBOARD_PASSWORD`
- 若 `DASHBOARD_PASSWORD` 缺失，网关必须启动失败

### 6.3 失败行为

- 缺失 `Authorization`：
  - 返回 `401 Unauthorized`
  - 返回 `WWW-Authenticate: Basic realm="NeoTrade3 Dashboard"`
- 密码错误：
  - 同样返回 `401 Unauthorized`
  - 不泄露更细错误原因
- 认证失败时：
  - 不返回页面
  - 不返回静态资源
  - 不代理到 API
  - 不暴露健康检查详情

### 6.4 放行策略

- 不保留 loopback 白名单
- 本机访问与外网访问都统一要求 Basic Auth
- 这样与旧 `V2` 的整站密码保护更一致

## 7. 认证数据流与兼容方式

### 7.1 浏览器行为

- 浏览器首次访问页面时未携带 Basic Auth
- 网关返回 `401 + WWW-Authenticate`
- 浏览器弹出原生用户名/密码输入框
- 用户输入后，浏览器重新发起请求，并带上 `Authorization: Basic ...`
- 网关校验通过后，页面、静态资源、`/api/*`、健康检查统一放行

### 7.2 与前端代码的关系

- 不修改 React 业务代码
- 不新增登录页
- 不新增 cookie / session / token
- 认证是浏览器与网关之间的 HTTP 协议层行为
- 前端只继续使用当前相对路径 `/api`

### 7.3 与旧 V2 的兼容目标

- 行为上保持：
  - 打开域名
  - 输入密码
  - 通过后访问页面与数据
- 本次兼容的是认证行为，而不是复用旧 Flask 代码

## 8. 环境变量与运行约束

### 8.1 密码变量

- 继续使用 `DASHBOARD_PASSWORD`
- 不新增新变量名
- 不做双变量兼容

### 8.2 启动约束

- `frontend_gateway` 启动时必须读取 `DASHBOARD_PASSWORD`
- 若缺失：
  - 直接启动失败
  - 不允许无密码模式启动

### 8.3 职责边界

- 密码保护职责只放在 `frontend_gateway`
- 不要求 `API`、`scheduler`、`trade_execution_rt` 持有外网密码
- `API` 不因为 `DASHBOARD_PASSWORD` 缺失而失败

### 8.4 launchd 注入

- `DASHBOARD_PASSWORD` 必须注入：
  - `com.neotrade3.frontend_gateway.plist.template`
- 不注入：
  - `com.neotrade3.api.plist.template`
  - `com.neotrade3.scheduler.plist.template`
  - `com.neotrade3.trade_execution_rt.plist.template`

## 9. 实施边界

- 本次只做网关层 Basic Auth 增强
- 允许修改：
  - `neotrade3-dashboard/server/gateway.js`
  - `config/launchd/com.neotrade3.frontend_gateway.plist.template`
  - `neotrade3/operations/launchd_sync.py`
  - `scripts/install_launchagents.py`
  - `neotrade3-dashboard/DEPLOY.md`
  - `docs/operations/bootstrap_runbook.md`
  - 必要的回归测试
- 不允许扩大到：
  - React 前端业务逻辑
  - 登录页 / session / token
  - API 业务鉴权
  - 模型逻辑与收益问题

## 10. 验收设计

### 10.1 未认证访问

- 本机访问 `http://127.0.0.1:5174/`
  - 返回 `401`
  - 带 `WWW-Authenticate: Basic realm="NeoTrade3 Dashboard"`
- 外网访问 `https://sanford.vip.cpolar.cn/`
  - 返回 `401`

### 10.2 正确密码访问

- 本机带认证访问：
  - `/` 返回 `200`
  - 静态资源返回正常
  - `/healthz` 返回 `200`
  - `/_gateway/healthz` 返回 `200`
- 外网带认证访问：
  - 页面返回 `200`
  - 动态数据正常
  - `/healthz` 与 `/_gateway/healthz` 正常

### 10.3 错误密码访问

- 仍返回 `401`
- 不泄露更细错误原因

### 10.4 配置缺失

- `DASHBOARD_PASSWORD` 缺失时：
  - `frontend_gateway` 启动失败
  - 不能以无认证模式继续运行

## 11. 完成标准

- `V3` 外网入口具备旧 `V2` 同类 Basic Auth 认证行为
- 页面、静态资源、API、健康检查统一受保护
- `DASHBOARD_PASSWORD` 缺失时网关无法启动
- 前端 React 业务代码保持不变
- 认证行为通过本机与外网双路径验收
