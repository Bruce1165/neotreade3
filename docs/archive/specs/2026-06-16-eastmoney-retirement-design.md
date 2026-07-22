# NeoTrade3 东方财富接口退役（设计定稿）

日期：2026-06-16  
范围：NeoTrade3 中与东方财富接口相关的脚本、适配器与文档引用

## 1. 背景与目标

### 1.1 背景
- 当前仓库仍保留东方财富相关实现与文档说明，包括：
  - 独立补采脚本 `scripts/fetch_525_eastmoney.py`
  - 数据源适配器 `neotrade3/data_sources/eastmoney_concept_adapter.py`
  - 数据源适配器 `neotrade3/data_sources/eastmoney_guba_adapter.py`
  - `neotrade3/data_sources/__init__.py` 中的对应导出
  - 若干将东方财富描述为可用数据源的文档
- 其中 `scripts/fetch_525_eastmoney.py` 当前已存在语法损坏，不具备稳定执行条件。
- 已确认东方财富数据接口需要退役，相关编码、脚本与文档不应继续作为可用方案保留在仓库中。

### 1.2 目标
- 从仓库中删除东方财富相关可执行代码与脚本。
- 移除数据源包中的东方财富导出，避免继续暴露“可用 API”的错误信号。
- 清理文档中把东方财富描述为当前可用方案的内容。
- 本次只处理“东方财富接口退役”这一项，不顺带修改其它业务逻辑问题。

## 2. 现状与事实依据

### 2.1 当前可定位的东方财富代码对象
- `scripts/fetch_525_eastmoney.py`
- `neotrade3/data_sources/eastmoney_concept_adapter.py`
- `neotrade3/data_sources/eastmoney_guba_adapter.py`
- `neotrade3/data_sources/__init__.py`

### 2.2 当前引用情况
- 已核查仓库内对 `EastmoneyConceptAdapter`、`EastmoneyGubaAdapter`、`fetch_525_eastmoney` 的搜索结果。
- 当前主链代码未发现对上述两个 adapter 的直接业务调用。
- 因此本次删除主要影响“历史遗留代码暴露面”和“文档口径”，不影响当前主链的正常导入路径。

### 2.3 当前需要同步修正的文档
- `NeoTrade3实施交接文档.md` 中仍把东方财富写成可用补采方案。
- `docs/superpowers/specs/2026-06-02-v3-automation-theme-backtest-stockcheck-auto-optimization-design.md` 中仍把东方财富概念板块写成主题主源。
- 本次只清理这类会误导当前维护者的文档内容，不扩散修改无关文档。

## 3. 设计范围与非目标

### 3.1 本次范围
- 删除东方财富补采脚本。
- 删除东方财富 concept/guba 适配器。
- 更新 `neotrade3/data_sources/__init__.py`。
- 更新明确把东方财富标记为当前可用方案的文档。
- 通过搜索与测试确认清理结果。

### 3.2 非目标
- 不在本次补充新的替代数据源实现。
- 不在本次重构 `data_sources` 包结构。
- 不顺手修复前端显示、调度、测试基线等其它已识别问题。
- 不改动与东方财富无关的数据源逻辑。

## 4. 方案比较

### 4.1 方案 A：彻底删除
- 删除脚本、适配器、包导出与相关文档说明。
- 优点：
  - 语义最清晰，仓库不再暴露已退役能力。
  - 不会继续给后续维护者造成“还能使用”的误导。
  - 可直接消除损坏脚本带来的语法风险。
- 缺点：
  - 丢失仓库内历史实现参考。

### 4.2 方案 B：保留文件但停用
- 保留相关文件，在模块头部写明“已退役”，并让入口抛异常或返回不可用。
- 优点：
  - 历史实现仍可作为参考。
- 缺点：
  - 仓库继续存在无效代码。
  - 需要额外维护停用语义，仍可能被误导性导入。

### 4.3 方案 C：仅删除脚本，保留 adapter
- 删除独立脚本，保留两个 adapter。
- 优点：
  - 改动最少。
- 缺点：
  - 与“接口已退役”的仓库语义不一致。
  - 仍会保留可调用但不应再使用的外部接口实现。

### 4.4 结论
- 采用方案 A。
- 原因是当前已确认东方财富相关适配器未处于主链调用路径，同时补采脚本本身已经损坏；彻底删除的语义最一致、维护成本最低。

## 5. 实施设计

### 5.1 代码与脚本处理
- 删除 `scripts/fetch_525_eastmoney.py`
- 删除 `neotrade3/data_sources/eastmoney_concept_adapter.py`
- 删除 `neotrade3/data_sources/eastmoney_guba_adapter.py`
- 更新 `neotrade3/data_sources/__init__.py`：
  - 移除对应 import
  - 移除对应 `__all__` 项

### 5.2 文档处理
- 更新 `NeoTrade3实施交接文档.md`
  - 删除把东方财富写成当前可执行补采方案的内容
  - 若需要保留历史背景，则改为“已退役，不再使用”
- 更新 `docs/superpowers/specs/2026-06-02-v3-automation-theme-backtest-stockcheck-auto-optimization-design.md`
  - 移除将东方财富概念板块标记为主题主源的表述
  - 将内容调整为不再承诺东方财富为当前方案

### 5.3 保守处理原则
- 只改动明确属于东方财富退役范围的代码与文本。
- 不推测新的主题主源，也不在本次设计中扩大到数据源替代方案。
- 对文档中涉及历史背景的条目，优先改成“已退役/不再使用”，避免伪造新的业务事实。

## 6. 验证方案

### 6.1 搜索验证
- 全仓搜索 `eastmoney`、`东方财富`、`EastmoneyConceptAdapter`、`EastmoneyGubaAdapter`。
- 目标是：
  - 可执行代码中不再残留东方财富调用入口。
  - 文档中不再把东方财富表述为当前有效方案。

### 6.2 语法与测试验证
- 执行 `python3 -m compileall -q apps neotrade3 scripts`
- 执行 `python3 -m pytest tests -q`

### 6.3 预期结果
- 删除后的 `compileall` 不再因 `scripts/fetch_525_eastmoney.py` 报语法错误。
- 若测试仍失败，失败应来自本次范围外的既有问题，而不是东方财富删除本身。

## 7. 风险与回避

### 7.1 风险
- 个别历史文档可能仍存在零散东方财富字样。
- 若存在未被搜索命中的动态导入，删除后可能暴露隐藏依赖。

### 7.2 回避方式
- 删除前后都执行全仓搜索。
- 以 `compileall` 和 `pytest` 作为最小回归校验。
- 若发现删除会影响当前主链导入，再停止并重新确认范围。

## 8. 完成标准

- 东方财富相关脚本与适配器已从仓库删除。
- `neotrade3/data_sources/__init__.py` 不再导出东方财富对象。
- 明确把东方财富写成当前可用方案的文档已同步修正。
- 搜索、语法检查和测试结果已记录，可证明本次改动没有引入新的东方财富残留入口。
