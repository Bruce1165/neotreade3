# NeoTrade3 API - Modular Version (2.0)

## 概述

这是一个重构的模块化 API 版本，将原来的 `main.py`（8580行）拆分为多个小文件，提高可维护性和稳定性。

## 文件结构

```
apps/api/
├── main.py                    # 原版入口（保留备份，8580行）
├── main.py.backup.YYYYMMDD    # 自动备份
├── main_modular.py            # 新版模块化入口（336行）
├── README_MODULAR.md          # 本文件
├── utils/
│   ├── __init__.py
│   ├── errors.py              # 错误处理
│   └── cache.py               # 缓存工具
└── handlers/
    └── __init__.py            # API 处理器（待扩展）
```

## 使用方法

### 启动新版模块化服务

```bash
cd /Users/mac/NeoTrade3
./.venv/bin/python -m apps.api.main_modular --port 18031
```

### 启动原版服务（保持不变）

```bash
cd /Users/mac/NeoTrade3
./.venv/bin/python -m apps.api.main --port 18030
```

## 对比

| 特性 | 原版 main.py | 新版 main_modular.py |
|------|-------------|---------------------|
| 代码行数 | 8580 行 | 336 行 |
| 文件大小 | ~350 KB | ~12 KB |
| 模块数量 | 1 个 | 多个小模块 |
| 风险 | 单点故障 | 分散风险 |
| 功能完整度 | 完整 | 核心功能（待扩展）|

## 当前支持的端点

### GET 端点
- `/api/v1/health` - 健康检查
- `/api/v1/data/status` - 数据状态
- `/api/v1/sectors/hot` - 热门板块（待实现）
- `/api/v1/screeners` - 筛选器列表

### POST 端点
- `/api/v1/data/update` - 更新数据（待实现）
- `/api/v1/model/run` - 运行模型（待实现）
- `/api/v1/screeners/run-all` - 运行全部筛选器（待实现）

## 迁移计划

1. **Phase 1**: 核心功能迁移（当前）
2. **Phase 2**: 数据控制端点迁移
3. **Phase 3**: 筛选器端点迁移
4. **Phase 4**: 量化交易端点迁移
5. **Phase 5**: 完全替换原版

## 注意事项

- 原版 `main.py` 保持不变，可随时切换回原版
- 新版目前仅包含核心框架，功能正在逐步迁移
- 建议并行运行两个版本，逐步验证新版的稳定性
