# NeoTrade3 Dashboard - Deployment Guide

## Official V3 Release Path

当前正式发布方式不再使用 Flask 承载页面。  
正式链路为：

- `cpolar -> Node 前端网关 -> neotrade3-dashboard/dist`
- `Node 前端网关 -> /api/* 或 /healthz -> 127.0.0.1:18030`

其中：

- `apps/api/main.py` 提供 API，默认监听 `127.0.0.1:18030`
- `server/gateway.js` 提供前端静态资源与同域代理，默认监听 `127.0.0.1:5174`
- 正式外网入口统一由 `server/gateway.js` 承担 `HTTP Basic Auth`
- `DASHBOARD_PASSWORD` 是前端网关启动硬前提，缺失时必须启动失败

## 1. Build Dashboard Assets

```bash
cd neotrade3-dashboard
npm install
npm run build
```

构建产物输出到 `dist/`。

## 2. Start The Frontend Gateway

本机前端网关入口：

```bash
cd neotrade3-dashboard
DASHBOARD_PASSWORD='your-dashboard-password' node server/gateway.js \
  --host 127.0.0.1 \
  --port 5174 \
  --api-base http://127.0.0.1:18030 \
  --dist-dir /Users/mac/NeoTrade3/neotrade3-dashboard/dist
```

也可以直接使用：

```bash
export DASHBOARD_PASSWORD='your-dashboard-password'
npm run start:gateway
```

默认行为：

- `/` 返回 `index.html`
- 未认证访问任一路径返回 `401 Unauthorized`
- 响应头带 `WWW-Authenticate: Basic realm="NeoTrade3 Dashboard"`
- 静态资源直接从 `dist/` 返回
- `/api/*` 透明代理到 `127.0.0.1:18030`
- `/healthz` 透明代理到 `127.0.0.1:18030/healthz`
- `/_gateway/healthz` 返回前端网关自身状态
- `/_gateway/healthz` 返回前端网关自身状态

## 3. Local Verification

在切外网前，先验证本机链路：

```bash
curl http://127.0.0.1:18030/healthz
curl -i http://127.0.0.1:5174/
curl -u user:$DASHBOARD_PASSWORD http://127.0.0.1:5174/_gateway/healthz
curl -u user:$DASHBOARD_PASSWORD http://127.0.0.1:5174/healthz
curl -I -u user:$DASHBOARD_PASSWORD http://127.0.0.1:5174/
```

预期结果：

- API `healthz` 返回 `status=ok`
- 未认证访问网关返回 `401`，这是正常行为
- 网关 `/_gateway/healthz` 返回 `status=ok`
- 通过网关访问 `/healthz` 能返回 API 的 `status=ok`
- 首页返回 `200`

## 4. cpolar Target

对外域名 `sanford.vip.cpolar.cn` 应指向前端网关端口，而不是旧 `V2` Flask 端口。

正式目标应为：

- `http://127.0.0.1:5174`

不再使用：

- `http://127.0.0.1:8765`

## 5. Launchd Assets

当前正式模板应包括：

- `config/launchd/com.neotrade3.api.plist.template`
- `config/launchd/com.neotrade3.frontend_gateway.plist.template`
- `config/launchd/com.neotrade3.scheduler.plist.template`
- `config/launchd/com.neotrade3.trade_execution_rt.plist.template`

统一渲染/安装脚本：

```bash
export DASHBOARD_PASSWORD='your-dashboard-password'
python3 scripts/install_launchagents.py render --output-dir /tmp/neotrade3-launchagents
python3 scripts/install_launchagents.py check --target-dir ~/Library/LaunchAgents
python3 scripts/install_launchagents.py install --target-dir ~/Library/LaunchAgents
```

如需指定解释器路径：

```bash
export DASHBOARD_PASSWORD='your-dashboard-password'
python3 scripts/install_launchagents.py install \
  --target-dir ~/Library/LaunchAgents \
  --python-bin /Users/mac/NeoTrade3/.venv/bin/python \
  --node-bin /opt/homebrew/bin/node
```

## 6. Notes

- 不要再为 V3 新增 Flask 页面承载壳
- 不要把 `vite dev` 或 `vite preview` 当作正式外网入口
- 前端继续使用相对路径 `/api`，正式发布不需要改成跨域 API 地址
- `legacy/runtime/dashboard_server.py` 仅保留为历史参考，不再作为正式发布方案
- `DASHBOARD_PASSWORD` 只注入 `frontend_gateway`，不要扩散到 API 或调度进程

## 7. Troubleshooting

**首页打不开：**

- 检查 `cpolar` 是否仍指向旧端口
- 检查前端网关是否已启动
- 检查 `dist/` 是否已构建
- 若返回 `401`，先确认是否已经通过 Basic Auth 携带密码

**页面能开但数据为空：**

- 检查 `http://127.0.0.1:18030/healthz`
- 检查 `http://127.0.0.1:5174/healthz`
- 检查网关代理参数中的 `--api-base`

**网关自身异常：**

- 检查 `http://127.0.0.1:5174/_gateway/healthz`
- 检查 `var/log/neotrade3_frontend_gateway.out.log`
- 检查 `var/log/neotrade3_frontend_gateway.err.log`
- 若日志提示缺少 `DASHBOARD_PASSWORD`，先补齐环境变量后再重载网关
