# NeoTrade3 收尾对齐项批量修复（设计定稿）

日期：2026-06-16  
范围：最后一批与当前实现逻辑明显不一致、且低风险可一次收口的问题

## 1. 本次范围

本次只处理以下 3 项：
- `five_flags_lab` 配置与运行时语义漂移
- `scripts/start-server.sh` 在后台启动失败时仍返回 0
- `neotrade3-dashboard/vite.config.js` 中悬空的 `scheduler` 别名

## 2. 背景与目标

### 2.1 `five_flags_lab`
- 运行时 `neotrade3/labs/runtime.py` 已明确声明 `five_flags_lab` 已整合到 `quant_trading_lab`，不再独立运行。
- 但 `config/labs/labs_registry.json` 与 `config/orchestrator/daily_master_orchestrator.json` 仍把它作为启用任务注册。
- 目标：让配置层与运行时语义一致。

### 2.2 `start-server.sh`
- 当前脚本在未找到 `server-info` 时输出错误 JSON 后仍 `exit 0`。
- 目标：让失败退出码与实际启动结果一致。

### 2.3 Vite 悬空别名
- `vite.config.js` 中存在 `scheduler -> scheduler/index.js` 别名，但仓库内并无对应文件，且当前代码无任何使用方。
- 目标：移除无效配置，避免未来误用时才暴露构建错误。

## 3. 方案与结论

- `five_flags_lab`：
  - 将 lab registry 中该 lab 标记为禁用
  - 从 orchestrator 配置中移除对应任务
  - 同步更新测试断言到当前配置口径
- `start-server.sh`：
  - 在 `server-info not found` 时返回非零退出码
- `vite.config.js`：
  - 删除悬空的 `scheduler` alias

结论：
- 采用以上最小改动，不改主链实现，不扩大到环境/部署体系重构。

## 4. 验证

- 后端全量：`python3 -m pytest tests -q`
- 前端全量：`npm run test -- --run`
- 前端构建：`npm run build`
- 前端 lint：`npm run lint`

## 5. 完成标准

- `five_flags_lab` 不再在启用配置中以独立任务存在
- `start-server.sh` 启动失败时返回非零退出码
- `vite.config.js` 不再包含无效别名
- 前后端回归验证通过
