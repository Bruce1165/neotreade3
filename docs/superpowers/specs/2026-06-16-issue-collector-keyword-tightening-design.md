# NeoTrade3 Issue Collector 关键词误判收敛（设计定稿）

日期：2026-06-16  
范围：`neotrade3/issue_center/collector.py` 中 `db/path` 两类根因分类关键词匹配

## 1. 背景与目标

- 当前 `collector.py` 使用简单子串匹配：
  - `"db" in message`
  - `"path" in message`
- 这会导致误判：
  - 例如 `debug` 会命中 `db`
  - 普通描述里包含 `path` 也会被误归类为文件系统/路径问题

目标：
- 只修复 `db/path` 两类明显过宽的匹配规则。
- 保留真实数据库/路径类错误的识别能力。
- 不扩大到其它分类规则。

## 2. 设计范围

本次范围：
- `neotrade3/issue_center/collector.py`
- 最小单元测试

非目标：
- 不重构整套根因分类体系。
- 不修改 `config/not implemented/timeout` 等其它分类规则。
- 不引入外部规则配置文件。

## 3. 方案比较

### 3.1 方案 A：精确短语 + 词边界匹配
- 数据库类：
  - 保留 `database`、`sqlite`
  - `db` 改为词边界匹配
- 路径类：
  - 保留 `file not found`
  - 新增 `no such file`、`directory not found`、`invalid path`
  - 去掉裸 `path` 子串匹配
- 优点：既修误判，又保留真实场景识别能力。

### 3.2 方案 B：直接删掉 `db/path`
- 去掉 `db` 和 `path` 两条规则，只保留更长关键词。
- 缺点：会丢掉一部分真实错误匹配能力。

### 3.3 方案 C：规则表重构
- 把关键词迁到统一规则表。
- 对这次单点修复超范围。

结论：
- 采用方案 A。

## 4. 实施设计

### 4.1 分类逻辑
- 在 `collector.py` 中引入更精确的消息匹配：
  - 数据库类：
    - `database`
    - `sqlite`
    - `db` 仅在独立词出现时匹配
  - 路径类：
    - `file not found`
    - `no such file`
    - `directory not found`
    - `invalid path`
- 不再使用裸 `"path" in message"`。

### 4.2 测试
- 新增最小单元测试，直接调用 `_analyze_root_cause(...)`。
- 覆盖以下情形：
  - `debug mode enabled` 不应归类为数据库问题
  - 普通包含 `path` 的非文件系统描述不应归类为路径问题
  - `sqlite database locked` 仍应归类为数据库问题
  - `file not found` / `invalid path` 仍应归类为路径问题

## 5. 验证

- 执行新增测试文件
- 执行 `python3 -m pytest tests -q`

## 6. 完成标准

- `db/path` 两类误判被消除。
- 真实数据库/路径类错误仍能正确分类。
- 后端全量测试通过。
