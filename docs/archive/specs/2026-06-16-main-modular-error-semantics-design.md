# NeoTrade3 `main_modular.py` 未实现接口错误语义修复（设计定稿）

日期：2026-06-16  
范围：`apps/api/main_modular.py` 中 4 个未实现入口与 1 个异常路径的对外返回语义

## 1. 背景与目标

- 当前 `main_modular.py` 中以下入口尚未实现，但仍返回 `_meta.status = "ok"`：
  - `_hot_sectors`
  - `_update_data`
  - `_run_model`
  - `_run_all_screeners`
- 同时，`_list_screeners` 在异常分支中也返回 `_meta.status = "ok"`、空数组和 `error` 字段。
- 这种返回会把“未实现”或“执行失败”伪装成“成功”，容易误导前端、自动化流程与调用方。

目标：
- 让未实现入口明确返回错误语义。
- 让 `_list_screeners` 的异常分支也明确返回错误语义。
- 保持修复范围局限在 `main_modular.py` 及其最小测试。

## 2. 设计范围

本次范围：
- `apps/api/main_modular.py`
- 新增针对该文件的最小单元测试

非目标：
- 不迁移或补全这些入口的真实实现。
- 不修改 `apps/api/main.py` 主链 API。
- 不扩展 `main_modular.py` 到更多端点。

## 3. 方案比较

### 3.1 方案 A：200 + 错误状态体
- 保持 HTTP 200，但将 `_meta.status` 改为 `error` 或 `not_implemented`。
- 缺点：对自动化调用方仍不够明确，容易被当作成功响应处理。

### 3.2 方案 B：抛 `ApiError`
- 对 4 个未实现入口直接抛 `ApiError`。
- `_list_screeners` 异常时也抛 `ApiError`。
- 由统一错误处理转换为非 200 响应和标准错误结构。
- 优点：语义最清晰，也与当前文件已有错误处理机制一致。

### 3.3 方案 C：保留 `ok`，仅增强提示
- 仅补充 `note` / `warning`。
- 缺点：并未真正修复语义问题。

结论：
- 采用方案 B。

## 4. 实施设计

### 4.1 未实现入口
- 对以下 4 个入口抛出 `ApiError(HTTPStatus.NOT_IMPLEMENTED, ...)`：
  - `_hot_sectors`
  - `_update_data`
  - `_run_model`
  - `_run_all_screeners`
- 错误码使用稳定、可识别的值。
- `message` 明确说明该能力尚未在模块化版本中实现。

### 4.2 异常路径
- `_list_screeners` 的 `except` 分支改为抛出 `ApiError(HTTPStatus.INTERNAL_SERVER_ERROR, ...)`。
- 不再返回 `status: ok + screeners: [] + error`。

### 4.3 测试
- 新增一份最小测试文件，直接实例化 handler 并调用目标方法。
- 覆盖以下断言：
  - 4 个未实现入口抛 `ApiError`
  - 4 个未实现入口的 `status_code` 为 `HTTPStatus.NOT_IMPLEMENTED`
  - `_list_screeners` 在 registry 加载异常时抛 `ApiError`
  - 该异常路径 `status_code` 为 `HTTPStatus.INTERNAL_SERVER_ERROR`

## 5. 验证

- 执行新增测试文件
- 执行 `python3 -m pytest tests -q`

## 6. 完成标准

- 5 个问题入口不再对外返回成功语义。
- 新增测试覆盖该行为。
- 后端测试全量通过。
