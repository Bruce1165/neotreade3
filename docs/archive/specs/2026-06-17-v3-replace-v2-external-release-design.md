# NeoTrade3 V3 替代 V2 外网发布方案

日期：2026-06-17  
范围：`V3` 替代 `V2` 的整套对外访问口径，外网域名保留为 `sanford.vip.cpolar.cn`

## 1. 背景

- 当前用户明确要求落实三件事，其中本子项目只处理第 1 项：
  - 用 `V3` 把 `V2` 替代下来，并发布到外网 `sanford.vip.cpolar.cn`
- 用户已明确约束：
  - 只保留外网域名 `sanford.vip.cpolar.cn`
  - 运行位置仍是本机
  - 外网页面必须是动态页面
  - 页面按同域方式取数
  - 不强制继续使用 Flask
- 当前 `NeoTrade3` 的正式运行口径已经与旧 `V2` 不同：
  - 正式前端为 `neotrade3-dashboard`
  - 正式 API 为 `apps/api/main.py`
  - 旧 `apps/dashboard/main.py` 已退役

## 2. 旧 V2 发布证据

### 2.1 本机 Flask 进程

旧 `V2` 的本机外网承载链路有明确证据：

- 本机 LaunchAgent `com.neotrade2.flask` 启动：
  - `python3 app.py --port 8765`
  - 工作目录：`/Users/mac/NeoTrade2/backend`
- 证据见：
  - [com.neotrade2.flask.plist](file:///Users/mac/Library/LaunchAgents/com.neotrade2.flask.plist#L8-L18)

### 2.2 本机 cpolar watchdog

- 本机 LaunchAgent `com.neotrade2.cpolar_watchdog` 会检查：
  - 外网：`https://sanford.vip.cpolar.cn`
  - 本机：`http://127.0.0.1:8765`
- 证据见：
  - [com.neotrade2.cpolar_watchdog.plist](file:///Users/mac/Library/LaunchAgents/com.neotrade2.cpolar_watchdog.plist#L8-L21)

### 2.3 旧系统对外口径

- 旧系统技术文档明确说明：
  - `Flask` 作为 Dashboard 与 API 承载层
  - 生产态前端通常由 Flask 同域提供静态文件
- 证据见：
  - [runbook.md](file:///Users/mac/NeoTrade2/TECHNICAL_DOCS/reference/code_wiki/runbook.md#L9-L42)
  - [architecture.md](file:///Users/mac/NeoTrade2/TECHNICAL_DOCS/reference/code_wiki/architecture.md#L7-L38)
  - [backend.md](file:///Users/mac/NeoTrade2/TECHNICAL_DOCS/reference/code_wiki/backend.md#L1-L20)

## 3. 当前 V3 运行证据

### 3.1 正式前端

- 当前正式前端是 `neotrade3-dashboard`
- 旧 `apps/dashboard/main.py` 已退役，不再作为正式前端入口
- 证据见：
  - [README.md](file:///Users/mac/NeoTrade3/README.md#L41-L50)
  - [apps/dashboard/main.py](file:///Users/mac/NeoTrade3/apps/dashboard/main.py#L654-L678)

### 3.2 正式 API

- 当前正式 API 入口是 `apps/api/main.py`
- 默认监听 `127.0.0.1:18030`
- 证据见：
  - [apps/api/main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L24244-L24309)

### 3.3 当前前端取数方式

- 当前前端使用相对路径 `/api/...`
- 开发态通过 Vite 代理到 `127.0.0.1:18030`
- 这意味着正式外网发布时，如果要保持动态页面，就必须提供“同域页面 + 同域 API 代理”
- 证据见：
  - [api.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/services/api.js#L11-L17)
  - [vite.config.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/vite.config.js#L10-L17)

## 4. 本次设计边界

- 本子项目只处理：`V3` 替代 `V2` 的整套对外访问口径
- 本子项目只覆盖：
  - `sanford.vip.cpolar.cn` 的正式承载链路切换
  - `V3` 前端页面对外入口
  - 页面同域动态取数
  - 本机守护方式
  - 运维切换与验收
- 本子项目不处理：
  - 模型交易逻辑调整
  - 收益率下降原因修复
  - 历史 `1000%` 结果复原
  - `V3` 与既有材料的完整业务对齐
  - 前端功能新增或页面重构

## 5. 方案比较

### 5.1 方案 A：单端口前端网关，推荐

- 本机新增一个 `V3 前端网关服务`
- 该服务负责：
  - 提供 `neotrade3-dashboard` 的生产构建产物
  - 反向代理 `/api/*` 到 `127.0.0.1:18030`
- `cpolar` 只暴露该网关端口到 `sanford.vip.cpolar.cn`

优点：
- 保留单域名单入口体验
- 兼容当前前端相对路径 `/api` 取数方式
- 不需要把 API 作为独立公网产品暴露
- 与当前 `V3` 正式技术栈一致

缺点：
- 需要新增一层正式网关服务
- 需要补齐守护、日志、切换与验收口径

### 5.2 方案 B：继续用 Flask 托管 V3 页面

- 保留 Flask 对外承载角色
- Flask 只负责静态资源托管和 `/api` 代理

优点：
- 最接近旧 `V2` 运维习惯

缺点：
- 会把旧 `V2` 的承载壳继续带入 `V3`
- 形成新的双口径：`V3 正式前端` 与 `Flask 承载壳`
- 不利于后续运维收敛

### 5.3 方案 C：直接外放 Vite dev/preview

- 直接将开发态或预览态端口暴露给 `cpolar`

优点：
- 搭建最快

缺点：
- 不适合作为正式外网入口
- 守护、日志、稳定性和升级策略都不符合正式要求

### 5.4 结论

- 采用方案 A。
- 原因：
  - 保留外网域名与单入口体验
  - 不继续依赖 Flask
  - 不把开发态进程伪装成正式发布方案
  - 与当前 `NeoTrade3` 前后端分层口径一致

## 6. 目标架构

- 对外唯一入口保持为 `https://sanford.vip.cpolar.cn`
- 本机保留 `V3 API 服务`：
  - `apps/api/main.py`
  - 监听 `127.0.0.1:18030`
- 新增 `V3 前端网关服务`
  - 监听一个专用本机端口
  - 该端口在实施阶段确定
  - 该端口不得与 `18030`、`8765` 或其他正式服务端口冲突
  - 提供前端构建产物
  - 同域代理 `/api/*` 到 `127.0.0.1:18030`
- `cpolar` 不再直连旧 `V2` Flask `8765`
- `cpolar` 改为直连 `V3 前端网关`

对外访问链路定义为：

- 浏览器访问 `sanford.vip.cpolar.cn`
- `cpolar` 转发到本机 `V3 前端网关`
- `V3 前端网关` 返回 `V3` 页面
- 页面内 `/api/*` 请求仍回到同一域名
- `V3 前端网关` 再将 `/api/*` 代理到 `127.0.0.1:18030`

## 7. 进程与端口设计

### 7.1 保留进程

- `V3 API 服务`
  - 入口：`apps/api/main.py`
  - 端口：`127.0.0.1:18030`
  - 角色：唯一后端数据接口

- `V3 Worker/调度链`
  - 入口：`apps/worker/main.py` 与现有调度体系
  - 角色：继续负责数据更新、执行链与后台任务

### 7.2 新增进程

- `V3 前端网关服务`
  - 端口：一个专用本机端口
  - 角色：
    - 托管 `neotrade3-dashboard` 构建产物
    - 代理 `/api/*` 到 `127.0.0.1:18030`

### 7.3 退出正式公网职责的旧进程

- `com.neotrade2.flask`
  - 可以临时保留在本机
  - 但不得继续作为 `sanford.vip.cpolar.cn` 的目标服务

- `127.0.0.1:8765`
  - 视为旧 `V2` 历史端口
  - 不再承担 `V3` 外网正式职责

### 7.4 端口原则

- `18030` 固定为 `V3 API` 内部服务端口
- `8765` 为旧 `V2` 端口，不再承接该域名正式流量
- 一个专用本机端口专属于 `V3 前端网关`
- 该端口在实施阶段确定，但必须独占使用
- 外部只感知 `sanford.vip.cpolar.cn`，不感知任何本机端口

## 8. 请求流与同域取数设计

### 8.1 页面访问

- 浏览器访问 `https://sanford.vip.cpolar.cn/`
- `cpolar` 转发到本机 `V3 前端网关`
- `V3 前端网关` 返回 `index.html`
- 浏览器继续请求 `js/css/assets`
- 这些静态资源由 `V3 前端网关` 直接返回

### 8.2 动态取数

- 前端继续使用当前相对路径 `/api/...`
- 浏览器请求 `/api/*`
- `cpolar` 将请求转发到本机 `V3 前端网关`
- `V3 前端网关` 将 `/api/*` 反向代理到 `127.0.0.1:18030`
- `V3 API` 返回 JSON
- `V3 前端网关` 原样回传

### 8.3 健康检查

- 外网第一层：
  - `/`
  - 用于验证 `cpolar -> 前端网关 -> 静态资源`
- 外网第二层：
  - `/api/healthz` 或当前正式健康检查路径
  - 用于验证 `cpolar -> 前端网关 -> API`

### 8.4 错误语义

- 静态资源不存在：
  - 由前端网关返回静态资源错误
- `/api/*` 代理失败：
  - 由前端网关返回明确代理错误
- API 业务错误：
  - 由 `18030` 返回原始业务错误结构
  - 前端网关不改写业务语义
- `cpolar` 断链：
  - 归因到外网入口层，而不是前端业务层

## 9. 替代与退役范围

### 9.1 被替代的对象

- 被替代的是 `V2` 的整套对外访问口径，而不是要求立即删除全部 `V2` 代码
- 替代的核心对象包括：
  - `sanford.vip.cpolar.cn` 对外网页入口
  - 旧外网访问链路中的 `Flask + cpolar -> V2 页面`
  - 旧用户通过该域名访问本机系统的方式

### 9.2 必须停止承担公网角色的旧入口

- `com.neotrade2.flask`
- `127.0.0.1:8765`
- 任何旧 `V2` 页面入口
- 任何将 `sanford.vip.cpolar.cn` 再次指回 `V2` 的旧 `cpolar` 指向

### 9.3 可暂留但不再承担正式职责的旧组件

- `NeoTrade2` 仓库本身
- 旧 `V2` 本机进程
- 旧脚本与旧文档

它们可以继续用于：
- 历史对照
- 运维审计
- 回归核对

但不能继续代表当前正式外网入口。

## 10. 发布运行方式

### 10.1 不再使用 Flask

- 本设计明确不再让 Flask 承担 `V3` 的正式外网页面承载角色。

原因：
- 当前正式前端已经是 `React + Vite`
- 若继续沿用 Flask，只会把旧 `V2` 承载壳继续带入 `V3`
- 会形成新的双口径，增加后续维护与排障复杂度

### 10.2 新方式

- 推荐新增一个 `Node.js` 前端网关服务
- 该服务只承担两项职责：
  - 提供 `neotrade3-dashboard` 的构建产物
  - 反向代理 `/api/*`

### 10.3 守护原则

- `V3 API`
- `V3 前端网关`
- `cpolar`

三者都是独立进程，不合并为单进程方案。

- 正式守护机制继续采用本机 `launchd`
- 任一进程异常时应支持独立重启

### 10.4 明确不采用的方式

- 不采用 `Vite dev server` 作为正式外网承载
- 不采用“前端跨域访问 API”的双域名方案
- 不采用“继续让 Flask 仅做 V3 页面壳”的过渡方案

## 11. 运维切换与验收

### 11.1 切换顺序

- 先确认 `V3 API` 本机可用
- 再确认 `V3 前端网关` 本机可用
- 再将 `cpolar` 目标切换到 `V3 前端网关`
- 最后进行外网验证

### 11.2 本机验收

- `127.0.0.1:18030` 健康检查可用
- `V3 前端网关` 首页可访问
- 静态资源能正常返回
- `/api/*` 代理可成功到 `18030`
- `cpolar` 已不再指向 `127.0.0.1:8765`

### 11.3 外网验收

- `https://sanford.vip.cpolar.cn/` 返回的是 `V3` 页面
- 页面静态资源加载正常
- 页面动态数据展示正常
- 页面发起的 `/api/*` 请求正常

### 11.4 切换完成判定

- 访问 `sanford.vip.cpolar.cn` 时，进入的是 `V3` 页面
- 页面数据来自 `V3 API`
- `8765` 不再承担该域名正式职责
- 即使不依赖 `V2 Flask` 外网承载，`V3` 外网入口仍稳定可用

### 11.5 回退原则

- 若切换后外网验收失败，允许短期回退 `cpolar` 指向
- 但回退只作为故障处置手段
- 不把“双正式入口长期并行”作为设计目标

## 12. 实施边界与非目标

- 本子项目只解决“对外发布替代”
- 不与以下事项混做：
  - 模型交易逻辑调整
  - 收益率下降分析与修复
  - 历史结果复原
  - 前端功能改造
  - `NeoTrade2` 全量清理

允许在本子项目中触及的修改，仅限：
- 为正式发布所必需的前端构建与托管配置
- 为同域代理所必需的网关配置
- 为 `launchd / cpolar` 切换所必需的守护配置

这些修改必须只服务于“外网发布替代”，不得扩大为模型或业务重构。

## 13. 完成标准

- `sanford.vip.cpolar.cn` 正式进入 `V3` 页面
- 页面保持动态展示能力
- 页面按同域 `/api` 方式取数
- `cpolar` 正式目标服务已切换到 `V3 前端网关`
- 旧 `V2 Flask` 不再承接该域名正式流量
- 发布、切换、验收和回退口径都已明确定义
