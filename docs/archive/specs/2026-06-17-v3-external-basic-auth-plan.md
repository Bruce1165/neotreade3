# NeoTrade3 V3 外网 Basic Auth 认证实施计划

日期：2026-06-17  
对应设计：`docs/superpowers/specs/2026-06-17-v3-external-basic-auth-design.md`

## 1. 目标

按已确认设计，为当前 `V3` 正式外网入口增加与旧 `V2` 同类的 `HTTP Basic Auth` 密码保护：

- 认证点只放在 `neotrade3-dashboard/server/gateway.js`
- 浏览器通过 `401 + WWW-Authenticate` 触发原生密码框
- 密码来源为 `DASHBOARD_PASSWORD`
- 页面、静态资源、`/api/*`、`/healthz`、`/_gateway/healthz` 全部统一受保护

本计划只处理外网入口认证增强，不处理业务登录、模型逻辑、收益分析。

## 2. 当前落地约束

### 2.1 已有可复用资产

- 当前正式外网入口已经统一到 `Node` 前端网关：
  - `neotrade3-dashboard/server/gateway.js`
- 当前网关已具备：
  - 静态资源托管
  - SPA 路由回退
  - `/api/*` 反向代理
  - `/healthz` 反向代理
  - `/_gateway/healthz` 自身健康检查
- 当前仓库已经具备正式 `launchd` 模板与安装脚本：
  - `config/launchd/com.neotrade3.frontend_gateway.plist.template`
  - `neotrade3/operations/launchd_sync.py`
  - `scripts/install_launchagents.py`

### 2.2 当前缺口

- 网关当前没有任何 Basic Auth 逻辑
- `frontend_gateway` 模板当前未注入 `DASHBOARD_PASSWORD`
- `launchd_sync.py` 的模板校验当前未覆盖该密码变量
- 部署文档与 runbook 尚未说明：
  - 外网入口已要求 Basic Auth
  - `DASHBOARD_PASSWORD` 为网关启动硬前提
- 仓库还没有针对网关认证的回归测试

## 3. 实施原则

- 认证只做在网关层，不扩散到 React 业务代码与 API 业务层
- 沿用旧变量名 `DASHBOARD_PASSWORD`，不引入新变量名
- 不做 loopback 白名单，本机与外网统一要求密码
- `DASHBOARD_PASSWORD` 缺失时，网关必须显式启动失败
- 不接受“页面受保护但 API 未受保护”的分裂状态
- 改动完成后，必须保证现有 V3 外网链路仍保持同域访问结构

## 4. 实施分解

### Phase 1：网关认证逻辑落地

目标：
- 在当前正式网关中加入全站 Basic Auth

任务：
- 在 `neotrade3-dashboard/server/gateway.js` 增加：
  - 读取 `DASHBOARD_PASSWORD`
  - 启动时缺失即失败
  - 解析 `Authorization: Basic ...`
  - 只校验密码，不关心用户名
  - 未认证时返回 `401`
  - 返回 `WWW-Authenticate: Basic realm="NeoTrade3 Dashboard"`
- 认证校验必须发生在：
  - 静态资源返回之前
  - SPA 回退之前
  - `/api/*` 代理之前
  - `/healthz` 与 `/_gateway/healthz` 返回之前

完成判定：
- 未认证访问网关任一路径都返回 `401`
- 正确密码访问时，页面和代理都恢复正常

### Phase 2：LaunchAgent 与配置注入补齐

目标：
- 让正式 `frontend_gateway` 进程通过 `launchd` 持有 `DASHBOARD_PASSWORD`

任务：
- 更新 `config/launchd/com.neotrade3.frontend_gateway.plist.template`
  - 增加 `DASHBOARD_PASSWORD` 注入
- 更新 `neotrade3/operations/launchd_sync.py`
  - 校验 `frontend_gateway` 模板必须包含 `DASHBOARD_PASSWORD`
  - 其他 agent 不应被要求包含该变量
- 如有必要，更新 `scripts/install_launchagents.py`
  - 确保渲染与安装流程不破坏现有模板校验

完成判定：
- `frontend_gateway` 模板渲染后包含 `DASHBOARD_PASSWORD`
- 模板校验通过
- `API/scheduler/trade_execution_rt` 不被错误要求携带该密码

### Phase 3：回归测试补齐

目标：
- 为网关认证行为建立最低必要回归保护

任务：
- 新增或补充针对 `gateway.js` 的测试
- 至少覆盖：
  - 未认证访问首页返回 `401`
  - 未认证访问 `/api/*` 返回 `401`
  - 错误密码返回 `401`
  - 正确密码访问首页返回 `200`
  - 正确密码访问 `/healthz` 与 `/_gateway/healthz` 返回 `200`
  - `DASHBOARD_PASSWORD` 缺失时启动失败

完成判定：
- 认证相关测试可稳定运行并通过

### Phase 4：部署文档与 runbook 收敛

目标：
- 让仓库文档只保留当前正式认证口径

任务：
- 更新 `neotrade3-dashboard/DEPLOY.md`
  - 加入 Basic Auth 说明
  - 记录 `DASHBOARD_PASSWORD` 为必需变量
- 更新 `docs/operations/bootstrap_runbook.md`
  - 记录 `frontend_gateway` 已开启 Basic Auth
  - 记录本机与外网的认证验证命令
  - 记录 `401` 为未认证正常行为

完成判定：
- 不再存在“当前 V3 外网入口无认证”的文档口径
- 运维可按文档复现认证验证

### Phase 5：本机与外网验收

目标：
- 证明认证行为在本机与外网两侧都准确生效

任务：
- 本机验收：
  - 未认证访问 `/` 返回 `401`
  - 响应头含 `WWW-Authenticate`
  - 带正确密码访问 `/` 返回 `200`
  - 带正确密码访问 `/healthz` 与 `/_gateway/healthz` 返回 `200`
  - 带正确密码访问 V3 页面后动态数据正常
- 外网验收：
  - 未认证访问 `https://sanford.vip.cpolar.cn/` 返回 `401`
  - 带正确密码访问页面返回 `200`
  - 带正确密码访问外网 `/healthz` 与 `/_gateway/healthz` 正常
- 记录验收结果

完成判定：
- 认证行为通过本机与外网双路径验证
- 当前 V3 外网入口保持可用

## 5. 代码变更清单

本子项目预期涉及以下区域：

- 修改：
  - `neotrade3-dashboard/server/gateway.js`
  - `config/launchd/com.neotrade3.frontend_gateway.plist.template`
  - `neotrade3/operations/launchd_sync.py`
  - `scripts/install_launchagents.py`
  - `neotrade3-dashboard/DEPLOY.md`
  - `docs/operations/bootstrap_runbook.md`
- 新增：
  - 认证相关测试文件，或补充现有测试覆盖

## 6. 测试与验收

### 6.1 本地验证

- 未认证请求：
  - `/`
  - `/healthz`
  - `/_gateway/healthz`
  - `/api/...`
  全部返回 `401`
- 响应头包含：
  - `WWW-Authenticate: Basic realm="NeoTrade3 Dashboard"`
- 正确密码访问：
  - 页面返回 `200`
  - 静态资源返回正常
  - 健康检查返回 `200`
  - 页面动态数据正常

### 6.2 配置验证

- `DASHBOARD_PASSWORD` 缺失时，网关启动失败
- `frontend_gateway` 模板渲染后包含密码变量
- 其他 `launchd` 模板不强制包含此变量

### 6.3 外网验证

- 未认证访问 `https://sanford.vip.cpolar.cn/` 返回 `401`
- 带认证访问返回 `200`
- 外网 `/healthz` 与 `/_gateway/healthz` 带认证返回 `200`

## 7. 风险与控制

### 风险 1：认证只保护页面，未保护 API

控制：
- 认证校验必须发生在代理逻辑之前
- 测试明确覆盖 `/api/*` 未认证返回 `401`

### 风险 2：缺失密码时服务意外裸奔

控制：
- 网关启动前强校验 `DASHBOARD_PASSWORD`
- 缺失时直接退出

### 风险 3：本机联调因统一认证变得困难

控制：
- 明确本机也走 Basic Auth
- 在 runbook 中提供带认证的验证方式
- 不为了联调便利引入 loopback 白名单

### 风险 4：修改 launchd 模板后影响现有正式外网入口

控制：
- 先做本机验证，再重载 `frontend_gateway`
- 外网验收失败时，优先回退到修改前模板与网关代码

## 8. 执行顺序

严格顺序如下：

1. 实现网关 Basic Auth 逻辑
2. 补齐 `frontend_gateway` 的 `launchd` 密码注入
3. 补齐回归测试
4. 更新部署与运维文档
5. 完成本机认证联调
6. 重载正式 `frontend_gateway`
7. 完成外网验收

## 9. 非目标重申

本计划不处理：

- 自定义登录页
- cookie / session / token 体系
- API 内部业务鉴权
- 模型逻辑与收益率分析
- 第 2 项与第 3 项中的任何业务差异修复
