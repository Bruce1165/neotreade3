# NeoTrade3 V3 替代 V2 外网发布实施计划

日期：2026-06-17  
对应设计：`docs/superpowers/specs/2026-06-17-v3-replace-v2-external-release-design.md`

## 1. 目标

按已确认的设计，将 `sanford.vip.cpolar.cn` 的正式对外链路从旧 `V2 Flask + cpolar` 切换到：

- `cpolar -> V3 前端网关 -> V3 前端构建产物`
- `V3 前端网关 -> /api/* -> 127.0.0.1:18030`

本计划只处理外网发布替代，不处理模型逻辑或收益率问题。

## 2. 当前落地约束

### 2.1 已有可复用资产

- 前端构建命令已经存在：
  - `neotrade3-dashboard/package.json` 中已有 `build` 与 `preview`
- 仓库根目录已经存在一个“静态文件 + API 代理”脚本：
  - `dashboard_server.py`
  - 当前监听 `5174`
  - 能提供 `dist/` 并代理 `/api` 到 `127.0.0.1:18030`
- 当前仓库已有 `launchd` 模板管理体系：
  - `config/launchd/`
  - `scripts/install_launchagents.py`
  - `neotrade3/operations/launchd_sync.py`

### 2.2 当前缺口

- `dashboard_server.py` 是 Python 实现，不符合本次确认的 `Node 前端网关` 正式口径
- 当前 `launchd` 模板只管理：
  - `com.neotrade3.scheduler`
  - `com.neotrade3.trade_execution_rt`
- 仓库未纳入以下正式资产：
  - `V3 API` 的可复用 LaunchAgent 模板
  - `V3 前端网关` 的 LaunchAgent 模板
  - `cpolar` 对 `sanford.vip.cpolar.cn` 的 V3 指向配置
- `neotrade3-dashboard/DEPLOY.md` 仍然保留旧的 `Flask + Cpolar` 说明，需要改写

## 3. 实施原则

- 只保留一个正式外网入口：`sanford.vip.cpolar.cn`
- 只保留一个正式前端承载方式：`V3 前端网关`
- 不继续扩展 `dashboard_server.py` 为正式方案
- 不采用 `Vite dev server` 作为正式发布方案
- 所有守护资产优先纳入仓库管理，不接受“只在本机手工改”作为最终方案
- 切换必须可回退，但不以“双正式入口长期并行”为目标

## 4. 实施分解

### Phase 1：前端网关实现收敛

目标：
- 引入正式的 `Node 前端网关`
- 取代 `dashboard_server.py` 的角色

任务：
- 在仓库内新增一个正式前端网关实现
  - 建议位置：`neotrade3-dashboard/gateway/` 或 `neotrade3-dashboard/server/`
- 网关职责只保留两项：
  - 托管 `dist/`
  - 代理 `/api/*` 到 `127.0.0.1:18030`
- 增加网关启动脚本
  - 建议新增 `npm` script，例如：
    - `build`
    - `start:gateway`
- 网关需要具备：
  - SPA 路由回退到 `index.html`
  - 静态资源直接返回
  - `/api/*` 透明代理
  - 基本健康检查入口
  - 代理失败时明确返回网关错误

完成判定：
- 本机通过网关端口能访问 V3 页面
- 本机页面内 `/api/*` 可以正常返回 V3 数据

### Phase 2：LaunchAgent 资产补齐

目标：
- 把正式发布所需守护资产纳入仓库，而不是只靠本机手工状态

任务：
- 为 `V3 前端网关` 新增 LaunchAgent 模板
  - 建议标签：`com.neotrade3.frontend_gateway`
- 为 `V3 API` 补齐 LaunchAgent 模板或纳管方案
  - 由于 runbook 已将 `com.neotrade3.api` 作为现状描述，优先补齐该模板
- 扩展 `neotrade3/operations/launchd_sync.py`
  - 使其支持渲染/校验/安装新增的长期进程模板
- 扩展 `scripts/install_launchagents.py`
  - 确保新增 agent 可随仓库脚本统一安装与校验

完成判定：
- 仓库模板可以渲染出 API 与前端网关两个正式 plist
- 校验脚本能识别新增模板
- 不再出现“runbook 说有，但仓库模板不管理”的状态

### Phase 3：运维文档与部署文档收敛

目标：
- 让文档只保留当前正式发布方式

任务：
- 更新 `neotrade3-dashboard/DEPLOY.md`
  - 从 `Flask + Cpolar` 改成 `Node 前端网关 + API + cpolar`
- 更新 `docs/operations/bootstrap_runbook.md`
  - 明确本机长期进程、端口、切换顺序、验收方式
- 如有必要，新增独立运维文档
  - 例如：`docs/operations/v3_external_release_runbook.md`
- 明确记录：
  - `sanford.vip.cpolar.cn` 应指向前端网关端口
  - `8765` 不再承接正式外网职责
  - `cpolar` 的切换与回退步骤

完成判定：
- 不再存在“正式文档仍指导使用 Flask 托管 V3”的说法
- 运维按仓库文档可复现切换动作

### Phase 4：本机联调与切换前验证

目标：
- 在不切换外网域名前，先证明本机链路闭合

任务：
- 构建前端产物
- 启动 `V3 API`
- 启动 `V3 前端网关`
- 验证：
  - 网关首页
  - 静态资源
  - `/api/healthz`
  - 页面关键动态数据
- 记录联调结果

完成判定：
- 本机已经满足“可切外网”的最小条件

### Phase 5：cpolar 切换与外网验收

目标：
- 将 `sanford.vip.cpolar.cn` 从旧 `8765` 切到新网关端口

任务：
- 记录切换前状态
  - 当前本机目标端口
  - 当前旧进程状态
- 切换 `cpolar` 指向到前端网关端口
- 执行外网验收
  - `https://sanford.vip.cpolar.cn/`
  - 页面资源加载
  - 页面动态取数
  - 关键接口返回
- 若失败，按回退步骤恢复旧指向

完成判定：
- 外网访问进入 V3 页面
- 数据来自当前 V3 API
- `8765` 不再承接正式流量

## 5. 代码变更清单

本子项目预期涉及以下区域：

- 新增：
-  - `neotrade3-dashboard/server/...`
  - `config/launchd/com.neotrade3.api.plist.template`
  - `config/launchd/com.neotrade3.frontend_gateway.plist.template`
  - 可能新增一份外网发布 runbook
- 修改：
  - `neotrade3-dashboard/package.json`
  - `neotrade3/operations/launchd_sync.py`
  - `scripts/install_launchagents.py`
  - `docs/operations/bootstrap_runbook.md`
  - `neotrade3-dashboard/DEPLOY.md`
- 退役或降级为历史参考：
  - `dashboard_server.py`

## 6. 测试与验收

### 6.1 本地验证

- 前端构建成功
- 网关进程可启动
- 网关首页返回成功
- `/api/healthz` 通过网关代理返回成功
- 关键页面动态数据能在本机显示

### 6.2 资产验证

- `launchd` 模板渲染成功
- `install_launchagents.py check` 能校验新增模板
- 新增文档与 runbook 与实现一致

### 6.3 外网验证

- `sanford.vip.cpolar.cn` 打开的是 V3 页面
- 页面不是旧 V2 页面
- 页面动态数据正常
- 外网链路故障时，能明确区分：
  - `cpolar`
  - 网关
  - API

## 7. 风险与控制

### 风险 1：API 现有守护方式不在仓库模板里

控制：
- 实施时优先补齐 `com.neotrade3.api` 模板
- 不允许继续只在 runbook 里口头描述

### 风险 2：旧 `dashboard_server.py` 与新网关并存造成双口径

控制：
- 实施后将其标记为历史参考或退役
- 文档中只保留新网关口径

### 风险 3：cpolar 切换是本机状态，不完全在仓库内

控制：
- 把切换步骤、检查项、回退步骤写进 runbook
- 在实施时记录切换前后状态

### 风险 4：前端动态页面依赖接口较多

控制：
- 本机联调阶段先验证首页与关键 API
- 不在外网切换后才第一次发现页面取数问题

## 8. 执行顺序

严格顺序如下：

1. 实现正式 `Node 前端网关`
2. 补齐 `launchd` 模板与安装/校验能力
3. 更新部署与运维文档
4. 完成本机联调
5. 执行 `cpolar` 切换
6. 完成外网验收
7. 视结果决定是否回退

## 9. 非目标重申

本计划不处理：

- 交易逻辑总结与历史材料比对
- 收益率降低原因分析
- 止损阈值从当前值改到 `-5%`
- 任何模型收益优化动作

这些内容属于后续第 2、第 3 子项目。
