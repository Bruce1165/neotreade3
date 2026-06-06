"""Minimal dashboard entrypoint for NeoTrade3 bootstrap."""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

DEFAULT_DASHBOARD_HOST = "0.0.0.0"
DEFAULT_DASHBOARD_PORT = 18031
DEFAULT_API_BASE_URL = "http://0.0.0.0:18030"

logger = logging.getLogger(__name__)


class DashboardPageBuilder:
    """Builds a static HTML shell that reads bootstrap data from the API."""

    def __init__(
        self, api_base_url: str, static_root: Optional[Union[str, Path]] = None
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.static_root = (
            Path(static_root)
            if static_root is not None
            else Path(__file__).parent / "static"
        )

    def health(self) -> dict[str, str]:
        return {
            "status": "ok",
            "service": "neotrade3-bootstrap-dashboard",
            "api_base_url": self.api_base_url,
        }

    def render_index(self) -> str:
        api_base_url = escape(self.api_base_url)
        css_version = 0
        js_version = 0
        try:
            css_version = int((self.static_root / "dashboard.css").stat().st_mtime)
        except OSError:
            css_version = 0
        try:
            js_version = int((self.static_root / "dashboard.js").stat().st_mtime)
        except OSError:
            js_version = 0
        try:
            enhanced_css_version = int((self.static_root / "neotrade3_enhanced.css").stat().st_mtime)
            css_version = max(css_version, enhanced_css_version)
        except OSError:
            pass
        try:
            enhanced_js_version = int((self.static_root / "neotrade3_enhanced.js").stat().st_mtime)
            js_version = max(js_version, enhanced_js_version)
        except OSError:
            pass
        return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>NeoTrade3 运营控制台</title>
    <link rel="stylesheet" href="/static/dashboard.css?v={css_version}">
    <link rel="stylesheet" href="/static/neotrade3_enhanced.css?v={css_version}">
  </head>
  <body data-api-base-url="{api_base_url}" data-dashboard-js-version="{js_version}">
    <div class="layout">
      <aside class="sidebar">
        <div class="sidebar-brand">
          <div class="sidebar-title">NeoTrade3</div>
          <div class="sidebar-subtitle">团队看板</div>
        </div>
        <nav class="sidebar-nav">
          <div class="sidebar-group-title">总览</div>
          <a href="#section-overview">今日总览</a>

          <div class="sidebar-group-title">低频交易</div>
          <a href="#section-lowfreq-today">今日快照</a>
          <a href="#section-lowfreq-portfolio">持仓监控</a>
          <a href="#section-lowfreq-candidates">候选池</a>
          <a href="#section-lowfreq-backtest">回测报告</a>
          <a href="#section-lowfreq-execution">执行约束</a>

          <div class="sidebar-group-title">工具</div>
          <a href="#section-screeners">筛选器</a>
          <a href="#section-stock">单股核验（CHECK）</a>

          <div class="sidebar-group-title">其它</div>
          <a href="#section-quant">量化交易</a>
          <a href="#section-strategy-pools">策略池管理</a>
          <a href="#section-diff">对照与变化</a>
        </nav>
      </aside>
      <div class="content">
        <header class="top-header">
          <div class="topbar">
            <div class="topbar-left">
              <h1 class="topbar-title">量化选股控制台（NeoTrade3）</h1>
              <div class="topbar-subtitle">团队控制台：执行 / 监控 / 复盘。</div>
            </div>
            <div class="topbar-right">
              <div class="topbar-meta">当前时间：<span id="current-time">--:--:--</span></div>
              <div id="meta-api-base" class="topbar-meta">API：<span id="api-base">{api_base_url}</span></div>
              <div class="topbar-meta">Dashboard：<span id="dashboard-version">{js_version}</span></div>
              <div id="meta-source-mode" class="topbar-meta">数据来源：<span id="source-mode">实时计算</span></div>
              <div class="topbar-meta">当前日期：<span id="current-date">--</span></div>
              <div id="data-status-bar" class="topbar-meta data-status-bar">
                <span class="data-status-bar__item">数据更新至：<span id="data-target-date">--</span></span>
                <span class="data-status-bar__item">数据管线：<span id="data-pipeline-status" class="data-pipeline-indicator"><span class="data-pipeline-dot data-pipeline-dot--unknown"></span>未知</span></span>
                <span id="data-anomaly-warning" class="data-status-bar__item data-anomaly-warning" hidden>&#9888; 数据异常，请检查数据管线</span>
              </div>
            </div>
          </div>
          <div class="controls">
            <label class="control">
              <span class="control-label">日期</span>
              <input id="control-date" type="date">
            </label>
            <button id="control-refresh" type="button">刷新</button>
            <span id="control-source-links" class="control-meta">
              数据来源：
              <a id="source-live" href="?source=live">实时计算</a>
              |
              <a id="source-stored" href="?source=stored">回放（已保存）</a>
            </span>
          </div>
        </header>
        <main>
      <section id="section-overview" class="section-wide" data-scope="result">
        <h2>今日分析总览</h2>
        <div id="global-status" class="status-banner">正在加载分析数据...</div>
        <div id="global-error" class="status-banner error-banner" hidden>—</div>

        <!-- 核心分析卡片 -->
        <div class="summary-grid">
          <article class="metric-card metric-card--wide">
            <div class="metric-label">市场阶段</div>
            <div id="summary-market-phase" class="metric-value metric-value--large">加载中...</div>
            <div id="summary-market-phase-detail" class="metric-detail"></div>
          </article>
          <article class="metric-card">
            <div class="metric-label">高确定性候选</div>
            <div id="summary-high-certainty" class="metric-value metric-value--large">加载中...</div>
            <div id="summary-certainty-detail" class="metric-detail"></div>
          </article>
          <article class="metric-card">
            <div class="metric-label">交易信号</div>
            <div id="summary-trading-signals" class="metric-value metric-value--large">加载中...</div>
            <div id="summary-signals-detail" class="metric-detail"></div>
          </article>
          <article class="metric-card">
            <div class="metric-label">Top 板块</div>
            <div id="summary-top-sectors" class="metric-value">加载中...</div>
          </article>
          <article class="metric-card">
            <div class="metric-label">筛选器命中</div>
            <div id="summary-screener-hits" class="metric-value">加载中...</div>
          </article>
        </div>

        <!-- 热门板块详细展示 -->
        <div id="sector-detail-section" class="section-box" style="margin-top: 12px;">
          <h3>热门板块详情</h3>
          <div id="sector-detail-loading" class="section-meta">加载中...</div>
          <div id="sector-detail-content"></div>
        </div>

        <!-- 快速操作 -->
        <div class="section-box" style="margin-top: 12px;">
          <div class="controls">
            <button id="overview-run-daily" type="button">运行今日分析</button>
            <div id="overview-run-status" class="control-meta">尚未执行。</div>
          </div>
        </div>

        <!-- 问题与告警（折叠） -->
        <details class="raw-payload" style="margin-top: 12px;">
          <summary>问题与告警 (<span id="summary-issue-count">0</span>)</summary>
          <div id="overview-issues-box">加载中...</div>
        </details>

        <!-- 运维指标（dev-only） -->
        <details class="raw-payload dev-only" style="margin-top: 12px;">
          <summary>运维指标</summary>
          <div class="summary-grid">
            <article class="metric-card">
              <div class="metric-label">运行通过</div>
              <div id="summary-run-ok" class="metric-value">—</div>
            </article>
            <article class="metric-card">
              <div class="metric-label">运行失败</div>
              <div id="summary-run-failed" class="metric-value">—</div>
            </article>
            <article class="metric-card">
              <div class="metric-label">A 股池总数</div>
              <div id="summary-pool-ashare" class="metric-value">—</div>
            </article>
            <article class="metric-card">
              <div class="metric-label">执行日期</div>
              <div id="summary-exec-date" class="metric-value">—</div>
            </article>
          </div>
          <pre id="overview-run-result" style="margin-top: 10px;">尚未执行。</pre>
        </details>

        <!-- 原始数据（dev-only） -->
        <details class="raw-payload dev-only">
          <summary>总览原始数据</summary>
          <pre id="overview">加载中...</pre>
        </details>
      </section>
      <section id="section-daily-workbench" class="section-wide" data-scope="result">
        <h2>团队操作</h2>
        <p class="summary-text">目标：让团队成员完成“更新池 → 跑筛选器 → 下载结果 → 复核单股”的闭环操作。</p>

        <div id="workbench-status" class="status-banner">加载中...</div>
        <div id="workbench-error" class="status-banner error-banner" hidden>—</div>

        <div class="section-box">
          <h3>运行与下载</h3>
          <div class="controls">
            <button id="wb-jump-latest" type="button">切换到最新交易日</button>
            <button id="wb-bulk-run" type="button">批量运行启用筛选器</button>
            <button id="wb-qm-run" type="button">生成量化矩阵（当日）</button>
          </div>
          <div class="control-meta" style="margin-top: 8px;">说明：运行与更新需要已设置 API Key；下载不需要。</div>
          <div class="control-meta" style="margin-top: 6px;">股票池维护入口：请到左侧「候选集」页面，在“手工监控池”区域上传/保存当日快照。</div>
        </div>

        <div id="team-screeners-runner" class="section-box">加载中...</div>
        <div id="team-screeners-runs" class="section-box">加载中...</div>

        <div class="section-box">
          <h3>执行结果</h3>
          <pre id="workbench-result">尚未执行。</pre>
        </div>

        <div class="section-box">
          <h3>量化矩阵 · 当日候选（Top）</h3>
          <div id="workbench-qm-summary" class="summary-text">加载中...</div>
          <div id="workbench-qm-table">加载中...</div>
        </div>

        <details class="raw-payload">
          <summary>工作台原始数据</summary>
          <pre id="workbench-raw">（开发者模式下显示）</pre>
        </details>
      </section>
      <section id="section-roadmap" class="section-wide dev-only" data-scope="ops">
        <h2>路线图（以 NeoTrade3 v1 架构方案为准）</h2>
        <div id="roadmap-box" class="section-box">加载中...</div>
        <details class="raw-payload">
          <summary>路线图原始数据</summary>
          <pre id="roadmap">加载中...</pre>
        </details>
      </section>
      <section id="section-management" class="section-wide" data-scope="ops">
        <h2>系统设置（Management）</h2>
        <div class="controls">
          <label class="control">
            <span class="control-label">API Key</span>
            <input id="control-api-key" type="password" autocomplete="off" placeholder="用于写入（POST：更新/运行/保存）">
            <button id="control-api-key-toggle" type="button">显示</button>
            <button id="control-api-key-clear" type="button">清空</button>
          </label>
          <div id="control-api-key-status" class="control-meta" style="flex-basis: 100%;">API Key：未设置</div>
          <label class="control checkbox">
            <input id="control-dev" type="checkbox">
            <span class="control-label">开发者模式（显示原始数据）</span>
          </label>
        </div>
        <div class="controls dev-only" style="margin-top: 10px;">
          <label class="control" style="flex: 1; min-width: 320px;">
            <span class="control-label">V2 数据源（可选）</span>
            <input id="control-v2-db-path" type="text" autocomplete="off" placeholder="例如：/path/to/v2/stock_data.db（或设置 NEOTRADE3_STOCK_DB_V2_PATH）">
          </label>
          <button id="control-sync-v2-daily-prices" type="button">从 V2 同步行情（可选）</button>
        </div>
        <div id="management-result" class="section-box dev-only" style="margin-top: 10px;">尚未执行同步。</div>
      </section>
      <section id="section-data-control" data-scope="ops">
        <h2>数据主链（采集 → 加工 → 发布）</h2>
        <div id="data-control-meta" class="section-meta">加载中...</div>
        <div id="data-control-stage-summary" class="section-box">加载中...</div>
        <details class="raw-payload">
          <summary>原始数据</summary>
          <pre id="data-control">加载中...</pre>
        </details>
      </section>
      <section id="section-orchestration" data-scope="ops">
        <h2>每日任务运行</h2>
        <div id="orchestration-meta" class="section-meta">加载中...</div>
        <div id="orchestration-blocked" class="section-box">加载中...</div>
        <details class="raw-payload">
          <summary>原始数据</summary>
          <pre id="orchestration">加载中...</pre>
        </details>
      </section>
      <section id="section-screeners" data-scope="ops">
        <h2>筛选器</h2>
        <div id="screeners-meta" class="section-meta">加载中...</div>
        <div class="screeners-bulk-action" style="margin-bottom: 12px;">
          <button id="screeners-bulk-run-highlight" type="button" class="btn btn--bulk-run">一键运行全部筛选器</button>
          <span id="screeners-bulk-run-hint" class="control-meta">运行所有已启用的筛选器并生成结果。</span>
        </div>
        <div class="screeners-layout">
          <div class="screeners-main">
            <div id="screeners-runner" class="section-box">加载中...</div>
            <div id="screeners-result-box" class="section-box">
              <h3>当日结果</h3>
              <div id="screeners-result-meta" class="section-meta">尚未选择筛选器结果。</div>
              <div id="screeners-result-view" style="margin-top: 10px;">—</div>
            </div>
            <div id="screeners-runs" class="section-box">加载中...</div>
          </div>
          <div class="screeners-side">
            <div id="screener-config-box" class="section-box">
              <h3>参数调整</h3>
              <div class="summary-line">点击筛选器表格中的「参数」按钮弹出配置窗口；保存后下一次运行生效。</div>
            </div>
          </div>
        </div>
        <details class="raw-payload">
          <summary>运行结果（最近一次）</summary>
          <pre id="screener-result">尚未选择</pre>
        </details>
        <details class="raw-payload">
          <summary>原始数据</summary>
          <pre id="screeners">加载中...</pre>
        </details>
      </section>
      <section id="section-cup-handle" data-scope="ops">
        <h2>杯柄</h2>
        <div id="cup-handle-meta" class="section-meta">加载中...</div>
        <div id="cup-handle-box" class="section-box">加载中...</div>
        <details class="raw-payload">
          <summary>原始数据</summary>
          <pre id="cup-handle-raw">加载中...</pre>
        </details>
      </section>
      <section id="section-five-flags" data-scope="ops">
        <h2>老鸭头五图</h2>
        <div id="five-flags-meta" class="section-meta">加载中...</div>
        <div id="five-flags-box" class="section-box">加载中...</div>
        <details class="raw-payload">
          <summary>原始数据</summary>
          <pre id="five-flags-raw">加载中...</pre>
        </details>
      </section>
      <section id="section-quant" data-scope="result">
        <h2>量化交易</h2>
        <div id="factor-matrix-meta" class="section-meta">加载中...</div>
        <div id="factor-matrix-box" class="section-box">加载中...</div>
        <div id="candidates-meta" class="section-meta">加载中...</div>
        <div id="candidates-qm-table" class="section-box">加载中...</div>
        <details class="raw-payload">
          <summary>原始数据</summary>
          <pre id="factor-matrix">加载中...</pre>
        </details>
      </section>
      <section id="section-strategy-pools" data-scope="result">
        <h2>策略池管理</h2>
        <p class="summary-text">老鸭头 / 三重滤网 / 海龟 / 强化杯柄 等策略池的维护与查看。</p>
        <div id="pools-meta" class="section-meta">加载中...</div>
        <div id="pools-box" class="section-box">加载中...</div>
        <div id="pool-members-box" class="section-box">
          <h3>池成员</h3>
          <div id="pool-members-meta" class="section-meta">尚未选择</div>
          <div id="pool-members-table">尚未选择</div>
        </div>
        <details class="raw-payload">
          <summary>池详情（最近一次查看）</summary>
          <pre id="pool-detail">尚未选择</pre>
        </details>
        <details class="raw-payload">
          <summary>原始数据</summary>
          <pre id="pools">加载中...</pre>
        </details>
      </section>
      <section id="section-diff" class="section-wide" data-scope="result">
        <h2>对照与变化</h2>
        <div class="section-box">
          <div class="summary-text">待实现：对比不同日期的量化候选变化、各策略池成员变化、以及关键 CHECK 结论变化。</div>
        </div>
      </section>
      <section id="section-stock" class="section-wide" data-scope="result">
        <h2>单股核验（CHECK）</h2>
        <div id="stock-matrix-box" class="section-box">尚未检查。</div>
        <div id="stock-check-box" class="section-box">
          <h3>股票 CHECK</h3>
          <div class="controls">
            <label class="control" style="flex: 1; min-width: 260px;">
              <span class="control-label">股票代码</span>
              <input id="stock-check-code" type="text" autocomplete="off" placeholder="例如：600000">
            </label>
            <button id="stock-check-run" type="button">检查</button>
          </div>
          <div id="stock-check-status" class="section-meta" style="margin-top: 8px;">尚未检查。</div>
          <div id="stock-check-result" class="section-box" style="margin-top: 10px;">尚未检查。</div>
          <!-- 增强信息：板块归属、分层、筛选器命中、RPS -->
          <div id="stock-enhanced-info" class="section-box" style="margin-top: 10px;" hidden>
            <h3>个股增强信息</h3>
            <div id="stock-sector-info" class="stock-info-block">
              <div class="stock-info-block__label">所属板块</div>
              <div id="stock-sector-value" class="stock-info-block__value">--</div>
            </div>
            <div id="stock-tier-info" class="stock-info-block">
              <div class="stock-info-block__label">个股分层</div>
              <div id="stock-tier-value" class="stock-info-block__value">--</div>
            </div>
            <div id="stock-rps-info" class="stock-info-block">
              <div class="stock-info-block__label">RPS 评分</div>
              <div id="stock-rps-value" class="stock-info-block__value">--</div>
            </div>
            <div id="stock-screener-hits-info" class="stock-info-block">
              <div class="stock-info-block__label">命中筛选器</div>
              <div id="stock-screener-hits-value" class="stock-info-block__value">--</div>
            </div>
          </div>
          <details class="raw-payload">
            <summary>原始数据</summary>
            <pre id="stock-check-raw">尚未检查。</pre>
          </details>
        </div>
      </section>
      <section id="section-issue-center" data-scope="ops">
        <h2>问题池</h2>
        <div id="issue-center-meta" class="section-meta">加载中...</div>
        <div id="issue-center-cases" class="section-box">加载中...</div>
        <details class="raw-payload">
          <summary>原始数据</summary>
          <pre id="issue-center">加载中...</pre>
        </details>
      </section>
      <section id="section-learning" class="dev-only" data-scope="ops">
        <h2>学习闭环</h2>
        <div id="learning-meta" class="section-meta">加载中...</div>
        <div id="learning-candidates" class="section-box">加载中...</div>
        <details class="raw-payload">
          <summary>原始数据</summary>
          <pre id="learning">加载中...</pre>
        </details>
      </section>
      <section id="section-migration" class="dev-only" data-scope="ops">
        <h2>迁移台账</h2>
        <div id="migration-coverage" class="section-box">加载中...</div>
        <div id="migration-focus" class="section-box">加载中...</div>
        <details class="raw-payload">
          <summary>迁移台账原始数据</summary>
          <pre id="migration">加载中...</pre>
        </details>
      </section>
      <section id="section-config-contracts" class="dev-only" data-scope="ops">
        <h2>配置契约</h2>
        <div id="config-contracts-box" class="section-box">加载中...</div>
        <details class="raw-payload">
          <summary>配置契约原始数据</summary>
          <pre id="config-contracts">加载中...</pre>
        </details>
      </section>
      <section id="section-labs" data-scope="ops">
        <h2>实验室</h2>
        <div id="labs-meta" class="section-meta">加载中...</div>
        <details class="raw-payload">
          <summary>原始数据</summary>
          <pre id="labs">加载中...</pre>
        </details>
      </section>

      <div id="screener-config-modal" class="modal-overlay" hidden>
        <div class="modal" role="dialog" aria-modal="true" aria-label="筛选器参数配置">
          <div class="modal-header">
            <div class="modal-title">筛选器参数配置</div>
            <button id="screener-config-close" class="btn secondary" type="button">关闭</button>
          </div>
          <div class="modal-body">
            <div class="screener-config-toolbar">
              <select id="screener-config-select" class="form-input"></select>
              <input id="screener-config-filter" class="form-input" type="text" autocomplete="off" placeholder="搜索筛选器（名称/ID）">
              <div id="screener-config-status" class="section-meta">尚未选择。</div>
            </div>
            <div id="screener-config-form" style="margin-top: 10px;">请选择上方筛选器。</div>
            <div class="controls" style="margin-top: 10px;">
              <button id="screener-config-save" type="button">保存</button>
              <button id="screener-config-reset" type="button">重置为默认</button>
            </div>
            <details class="raw-payload" style="margin-top: 10px;">
              <summary>原始参数（开发者模式）</summary>
              <textarea id="screener-config-json" class="code-editor" rows="12" spellcheck="false" placeholder="{{}}"></textarea>
            </details>
          </div>
        </div>
      </div>
      <section id="section-lowfreq-today" class="section-wide">
        <h2>低频交易 · 今日快照</h2>
        <div class="section-box">
          <div id="hot-sectors-panel"></div>
        </div>
      </section>

      <section id="section-lowfreq-portfolio" class="section-wide">
        <h2>低频交易 · 持仓监控</h2>
        <div class="section-box">
          <div id="lowfreq-portfolio-panel"></div>
        </div>
      </section>

      <section id="section-lowfreq-candidates" class="section-wide">
        <h2>低频交易 · 候选池</h2>
        <div class="section-box">
          <div id="lowfreq-candidates-panel"></div>
        </div>
      </section>

      <section id="section-lowfreq-backtest" class="section-wide">
        <h2>低频交易 · 回测报告</h2>
        <div class="section-box">
          <div id="lowfreq-backtest-panel"></div>
        </div>
      </section>

      <section id="section-lowfreq-execution" class="section-wide">
        <h2>低频交易 · 执行约束</h2>
        <div class="section-box">
          <h3>回测执行口径（成交假设）</h3>
          <ul class="constraint-list">
            <li>数据与价格：仅使用日线收盘价 close 作为成交价。</li>
            <li>前视校验：no-lookahead 强校验开启。</li>
            <li>涨停买不进：买入信号当日涨停则进入待买队列，最多尝试 3 个交易日。</li>
            <li>跌停卖不出：离场信号当日跌停则进入待卖出，顺延到首个非跌停日成交。</li>
            <li>执行顺序：待卖出 → 当日新离场 → 待买入 → 调仓日新买入。</li>
            <li>涨跌停阈值：ST ±4.8%；300/688 ±19.8%；其它 ±9.8%。</li>
          </ul>
        </div>
      </section>
        </main>
      </div>
    </div>
    <script src="/static/dashboard.js?v={js_version}"></script>
    <script src="/static/neotrade3_enhanced.js?v={js_version}"></script>
  </body>
</html>
"""

    def load_static_asset(self, relative_path: str) -> tuple[bytes, str]:
        file_path = self.static_root / relative_path
        content_type = (
            mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        )
        return file_path.read_bytes(), content_type


def build_handler(page_builder: DashboardPageBuilder) -> type[BaseHTTPRequestHandler]:
    class RequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                payload = (
                    json.dumps(
                        {
                            "status": "gone",
                            "service": "neotrade3-bootstrap-dashboard",
                            "message": "This dashboard has been retired. Use the NeoTrade3 V3 dashboard instead.",
                        },
                        indent=2,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8")
                self.send_response(int(HTTPStatus.GONE))
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            body = (
                "This dashboard has been retired. Use the NeoTrade3 V3 dashboard instead.\n"
            ).encode("utf-8")
            self.send_response(int(HTTPStatus.GONE))
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        def log_message(self, format: str, *args: object) -> None:
            return

    return RequestHandler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the NeoTrade3 bootstrap dashboard."
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_DASHBOARD_HOST,
        help=f"Bind host for the dashboard server (default: {DEFAULT_DASHBOARD_HOST}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_DASHBOARD_PORT,
        help=f"Bind port for the dashboard server (default: {DEFAULT_DASHBOARD_PORT}).",
    )
    parser.add_argument(
        "--api-base-url",
        default=DEFAULT_API_BASE_URL,
        help=f"Base URL for the bootstrap API (default: {DEFAULT_API_BASE_URL}).",
    )
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    parser = build_parser()
    args = parser.parse_args()
    logger.info(
        "%s",
        json.dumps(
            {
                "service": "neotrade3-bootstrap-dashboard",
                "status": "gone",
                "message": "This dashboard has been retired. Use the NeoTrade3 V3 dashboard instead.",
                "requested_host": args.host,
                "requested_port": args.port,
                "api_base_url": args.api_base_url,
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ),
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
