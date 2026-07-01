# NeoTrade3 Bootstrap Runbook CORS 说明对齐（设计定稿）

日期：2026-06-16  
范围：`docs/operations/bootstrap_runbook.md` 中已确认与实现不一致的 CORS 说明

## 1. 背景与目标

- 当前 `bootstrap_runbook.md` 中的 CORS 说明仍写为：
  - `Access-Control-Allow-Origin: *`
  - `Access-Control-Allow-Methods: GET, OPTIONS`
- 但实际实现 `apps/api/http.py` 已经表现为：
  - `Access-Control-Allow-Origin` 按允许来源反射
  - `Vary: Origin`
  - `Access-Control-Allow-Methods: GET, POST, OPTIONS`
  - `Access-Control-Allow-Headers: Content-Type, X-API-Key`

目标：
- 仅修正文档口径，使其与当前实现一致。
- 不改动运行时代码行为。
- 不扩大到 `docs/operations/` 其它文档。

## 2. 设计范围

本次范围：
- `docs/operations/bootstrap_runbook.md`

非目标：
- 不修改 `apps/api/http.py`
- 不统一扫描和修改同目录其它文档
- 不调整 CORS 策略本身

## 3. 方案比较

### 3.1 方案 A：按实现精确改文档
- 直接把当前 CORS 说明改成与实现一致的 header 行为。
- 优点：信息最完整，联调和排障最直接。

### 3.2 方案 B：改成抽象描述
- 仅写“支持独立端口前端访问”。
- 缺点：信息不足，不利于排障。

### 3.3 方案 C：按旧文档回退实现
- 不属于文档修复范围。

结论：
- 采用方案 A。

## 4. 实施设计

- 更新 `bootstrap_runbook.md` 中“当前响应头行为”小节。
- 将旧表述替换为：
  - `Access-Control-Allow-Origin` 为按允许来源反射的值
  - `Vary: Origin`
  - `Access-Control-Allow-Methods: GET, POST, OPTIONS`
  - `Access-Control-Allow-Headers: Content-Type, X-API-Key`

## 5. 验证

- 对读 `docs/operations/bootstrap_runbook.md` 与 `apps/api/http.py`
- 搜索确认该 runbook 中这段表述已与实现一致

## 6. 完成标准

- runbook 中该段 CORS 说明已与实现对齐
- 不引入其它文档或代码改动
