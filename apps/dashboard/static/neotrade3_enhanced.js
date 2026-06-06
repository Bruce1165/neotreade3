/**
 * NeoTrade3 Enhanced Dashboard Module
 * 
 * 功能：
 * 1. 一键触发：本地数据更新/模型/筛选器运行
 * 2. 人气板块：龙头/中军/跟随 + 确定值 + 买入信号
 * 3. 筛选器管理：可折叠结果 + CSV下载 + 参数调整
 * 4. 股票CHECK：输入代码返回通过/未通过的筛选器
 */

(function() {
  'use strict';

  const apiBaseUrl = document.body.dataset.apiBaseUrl || 'http://localhost:18030';
  let apiKey = '';
  try {
    apiKey = window.localStorage.getItem("neo_api_key") || "";
  } catch (e) { apiKey = ''; }

  const storage = {
    get(key, fallback) {
      try {
        const raw = window.localStorage.getItem(key);
        if (raw === null || raw === undefined) return fallback;
        return raw;
      } catch (e) {
        return fallback;
      }
    },
    set(key, value) {
      try {
        window.localStorage.setItem(key, String(value));
      } catch (e) {}
    }
  };

  const lowfreqUiState = {
    todayBuyOnly: storage.get('lowfreq.today.buy_only', '1') !== '0',
    candidatesMode: storage.get('lowfreq.candidates.mode', 'buy_only') || 'buy_only',
    backtestStart: storage.get('lowfreq.backtest.start', '') || '',
    backtestEnd: storage.get('lowfreq.backtest.end', '') || '',
    lastReportId: storage.get('lowfreq.backtest.last_report_id', '') || '',
  };

  let lowfreqSnapshotCache = null;

  // ==================== 工具函数 ====================
  function $(id) { return document.getElementById(id); }
  function formatDate(date) {
    if (!date) return '--';
    return new Date(date).toLocaleDateString('zh-CN');
  }
  function formatNumber(num, decimals = 2) {
    if (num === null || num === undefined) return '--';
    return Number(num).toFixed(decimals);
  }
  function formatPercent(num) {
    if (num === null || num === undefined) return '--';
    return (num > 0 ? '+' : '') + Number(num).toFixed(2) + '%';
  }

  // ==================== API 调用 ====================
  async function apiGet(endpoint) {
    const resp = await fetch(`${apiBaseUrl}${endpoint}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }

  async function apiPost(endpoint, data = {}) {
    const resp = await fetch(`${apiBaseUrl}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey
      },
      body: JSON.stringify(data)
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }

  async function fetchLowfreqSnapshot() {
    const data = await apiGet('/api/v1/sectors/hot');
    lowfreqSnapshotCache = data;
    return data;
  }

  // ==================== 1. 一键触发区域 ====================
  function initQuickActions() {
    const container = $('quick-actions-panel');
    if (!container) return;

    container.innerHTML = `
      <div class="quick-actions-grid">
        <div class="action-card">
          <h4>数据更新</h4>
          <div class="action-status" id="data-update-status">就绪</div>
          <button class="btn primary" onclick="updateLocalData()">更新本地数据</button>
          <div class="action-meta">最新交易日: <span id="latest-trade-date">--</span></div>
        </div>
        <div class="action-card">
          <h4>模型运行</h4>
          <div class="action-status" id="model-run-status">就绪</div>
          <button class="btn primary" onclick="runModel()">运行量化模型</button>
          <div class="action-meta">上次运行: <span id="last-model-run">--</span></div>
        </div>
        <div class="action-card">
          <h4>筛选器运行</h4>
          <div class="action-status" id="screener-run-status">就绪</div>
          <button class="btn primary" onclick="runAllScreeners()">运行全部筛选器</button>
          <div class="action-meta">命中数量: <span id="screener-hits-count">--</span></div>
        </div>
      </div>
    `;

    // 加载最新交易日
    loadLatestTradeDate();
  }

  async function loadLatestTradeDate() {
    try {
      const data = await apiGet('/api/v1/data/status');
      $('latest-trade-date').textContent = formatDate(data.latest_trade_date);
    } catch (e) {
      $('latest-trade-date').textContent = '获取失败';
    }
  }

  // 全局函数供按钮调用
  window.updateLocalData = async function() {
    const status = $('data-update-status');
    status.textContent = '更新中...';
    status.className = 'action-status running';
    try {
      const result = await apiPost('/api/v1/data/update');
      status.textContent = '完成';
      status.className = 'action-status success';
      loadLatestTradeDate();
      showNotification('数据更新完成', 'success');
    } catch (e) {
      status.textContent = '失败: ' + e.message;
      status.className = 'action-status error';
      showNotification('数据更新失败: ' + e.message, 'error');
    }
  };

  window.runModel = async function() {
    const status = $('model-run-status');
    status.textContent = '运行中...';
    status.className = 'action-status running';
    try {
      const result = await apiPost('/api/v1/model/run');
      status.textContent = '完成';
      status.className = 'action-status success';
      $('last-model-run').textContent = new Date().toLocaleString('zh-CN');
      showNotification('模型运行完成', 'success');
      // 刷新人气板块显示
      loadHotSectors();
    } catch (e) {
      status.textContent = '失败: ' + e.message;
      status.className = 'action-status error';
      showNotification('模型运行失败: ' + e.message, 'error');
    }
  };

  window.runAllScreeners = async function() {
    const status = $('screener-run-status');
    status.textContent = '运行中...';
    status.className = 'action-status running';
    try {
      const result = await apiPost('/api/v1/screeners/run-all');
      status.textContent = '完成';
      status.className = 'action-status success';
      $('screener-hits-count').textContent = result.total_hits || 0;
      showNotification(`筛选器运行完成，共命中 ${result.total_hits || 0} 只股票`, 'success');
      // 刷新筛选器结果
      loadScreenerResults();
    } catch (e) {
      status.textContent = '失败: ' + e.message;
      status.className = 'action-status error';
      showNotification('筛选器运行失败: ' + e.message, 'error');
    }
  };

  // ==================== 2. 人气板块展示 ====================
  function initHotSectors() {
    const container = $('hot-sectors-panel');
    if (!container) return;

    container.innerHTML = `
      <div class="sectors-header">
        <h3>今日快照（热门板块）</h3>
        <div class="header-actions">
          <label class="toggle">
            <input id="lowfreq-today-only-buy" type="checkbox">
            <span>仅看买入</span>
          </label>
          <button class="btn secondary" onclick="loadHotSectors()">刷新</button>
        </div>
      </div>
      <div id="sectors-content" class="sectors-content">
        <div class="loading">加载中...</div>
      </div>
    `;

    const buyOnly = $('lowfreq-today-only-buy');
    if (buyOnly) {
      buyOnly.checked = !!lowfreqUiState.todayBuyOnly;
      buyOnly.addEventListener('change', () => {
        lowfreqUiState.todayBuyOnly = !!buyOnly.checked;
        storage.set('lowfreq.today.buy_only', lowfreqUiState.todayBuyOnly ? '1' : '0');
        if (lowfreqSnapshotCache && Array.isArray(lowfreqSnapshotCache.sectors)) {
          renderHotSectors(lowfreqSnapshotCache.sectors);
          renderLowfreqCandidatesFromSnapshot(lowfreqSnapshotCache);
        }
      });
    }

    loadHotSectors();
  }

  window.loadHotSectors = async function() {
    const content = $('sectors-content');
    content.innerHTML = '<div class="loading">加载中...</div>';
    
    try {
      const data = await fetchLowfreqSnapshot();
      renderHotSectors(data.sectors || []);
      renderLowfreqPortfolio(data.portfolio);
      renderLowfreqCandidatesFromSnapshot(data);
    } catch (e) {
      content.innerHTML = `<div class="error">加载失败: ${e.message}</div>`;
    }
  };

  function renderHotSectors(sectors) {
    const content = $('sectors-content');
    if (!sectors.length) {
      content.innerHTML = '<div class="empty">暂无热门板块数据</div>';
      return;
    }

    const buyOnly = !!lowfreqUiState.todayBuyOnly;
    content.innerHTML = sectors.map(sector => `
      <div class="sector-card" data-sector="${sector.code}">
        <div class="sector-header">
          <span class="sector-name">${sector.name}</span>
          <span class="sector-heat">热度: ${formatNumber(sector.heat_score, 1)}</span>
        </div>
        <div class="sector-stocks">
          ${renderStockTier(sector.leaders, '龙头', 'leader', buyOnly)}
          ${renderStockTier(sector.middle, '中军', 'middle', buyOnly)}
          ${renderStockTier(sector.followers, '跟随', 'follower', buyOnly)}
          ${buyOnly && !hasBuySignals(sector) ? '<div class="empty">无买入信号</div>' : ''}
        </div>
      </div>
    `).join('');
  }

  function hasBuySignals(sector) {
    for (const group of ['leaders', 'middle', 'followers']) {
      const items = Array.isArray(sector && sector[group]) ? sector[group] : [];
      for (const item of items) {
        if (item && item.buy_signal) return true;
      }
    }
    return false;
  }

  function renderStockTier(stocks, tierName, tierClass, buyOnly) {
    const list = Array.isArray(stocks) ? stocks : [];
    const filtered = buyOnly ? list.filter(s => s && s.buy_signal) : list;
    if (!filtered.length) return '';
    
    return `
      <div class="stock-tier ${tierClass}">
        <div class="tier-label">${tierName}</div>
        <div class="tier-stocks">
          ${filtered.map(stock => `
            <div class="stock-item ${stock.buy_signal ? 'buy-signal' : ''}" data-code="${stock.code}">
              <div class="stock-info">
                <span class="stock-code">${stock.code}</span>
                <span class="stock-name">${stock.name}</span>
                ${stock.buy_signal ? '<span class="buy-badge">买入</span>' : ''}
              </div>
              <div class="stock-metrics">
                <span class="certainty" title="确定性评分">确: ${formatNumber(stock.certainty, 0)}</span>
                <span class="return-5d" title="5日涨幅">5日: ${formatPercent(stock.return_5d)}</span>
                ${stock.suggested_entry ? `<span class="entry-time">建议: ${stock.suggested_entry}</span>` : ''}
              </div>
              ${Array.isArray(stock.reasons) && stock.reasons.length ? `<div class="stock-reasons">${stock.reasons.slice(0, 3).map(r => `<span class="reason-pill" title="${escapeHtml(String(r))}">${escapeHtml(String(r))}</span>`).join('')}</div>` : ''}
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ==================== 2.1 模拟交易状态 ====================
  function initLowfreqPortfolio() {
    const container = $('lowfreq-portfolio-panel');
    if (!container) return;

    container.innerHTML = `
      <div class="sectors-header">
        <h3>持仓监控</h3>
        <button class="btn secondary" onclick="loadLowfreqPortfolio()">刷新</button>
      </div>
      <div id="lowfreq-portfolio-content" class="sectors-content">
        <div class="loading">加载中...</div>
      </div>
    `;

    loadLowfreqPortfolio();
  }

  window.loadLowfreqPortfolio = async function() {
    const content = $('lowfreq-portfolio-content');
    if (!content) return;
    content.innerHTML = '<div class="loading">加载中...</div>';
    try {
      const data = await fetchLowfreqSnapshot();
      renderLowfreqPortfolio(data.portfolio);
    } catch (e) {
      content.innerHTML = `<div class="error">加载失败: ${e.message}</div>`;
    }
  };

  function renderLowfreqPortfolio(portfolio) {
    const content = $('lowfreq-portfolio-content');
    if (!content) return;
    if (!portfolio) {
      content.innerHTML = '<div class="empty">暂无数据</div>';
      return;
    }

    const openPositions = portfolio.open_positions || [];
    const summaryHtml = `
      <div class="action-meta">截至：${formatDate(portfolio.as_of)}</div>
      <div class="action-meta">总资产：${formatNumber(portfolio.total_value, 2)}（${formatPercent(portfolio.total_return_pct)}）</div>
      <div class="action-meta">现金：${formatNumber(portfolio.cash, 2)}，持仓市值：${formatNumber(portfolio.positions_value, 2)}</div>
      <div class="action-meta">持仓：${openPositions.length}，已平仓：${portfolio.closed_trades_count || 0}</div>
    `;

    const rows = openPositions.map(p => `
      <tr class="${p.sell_signal ? 'row-sell-signal' : ''}">
        <td>${p.code}</td>
        <td>${p.name}</td>
        <td>${p.sector || '--'}</td>
        <td>${p.role || '--'}</td>
        <td>${p.buy_date || '--'}</td>
        <td>${formatNumber(p.buy_score, 0)}</td>
        <td>${formatNumber(p.buy_price, 3)}</td>
        <td>${formatNumber(p.current_price, 3)}</td>
        <td class="${p.unrealized_pnl >= 0 ? 'pos' : 'neg'}">${formatNumber(p.unrealized_pnl, 2)} (${formatPercent(p.unrealized_pnl_pct)})</td>
        <td>${p.sell_signal ? (p.sell_reason || 'sell') : '--'}</td>
      </tr>
    `).join('');

    const tableHtml = openPositions.length ? `
      <table class="results-table" style="margin-top: 10px;">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th>板块</th>
            <th>角色</th>
            <th>买入日</th>
            <th>评分</th>
            <th>买入价</th>
            <th>现价</th>
            <th>浮盈</th>
            <th>离场</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    ` : '<div class="empty" style="margin-top: 10px;">当前无持仓</div>';

    content.innerHTML = `${summaryHtml}${tableHtml}`;
  }

  // ==================== 2.2 全历史回测报告 ====================
  function initLowfreqBacktest() {
    const container = $('lowfreq-backtest-panel');
    if (!container) return;

    container.innerHTML = `
      <div class="sectors-header">
        <h3>回测报告（PDF）</h3>
        <div class="header-actions">
          <label class="inline-field">
            <span class="inline-label">开始</span>
            <input id="lowfreq-backtest-start" class="form-input form-input--compact" type="date">
          </label>
          <label class="inline-field">
            <span class="inline-label">结束</span>
            <input id="lowfreq-backtest-end" class="form-input form-input--compact" type="date">
          </label>
          <button class="btn primary" onclick="runLowfreqBacktestAll()">运行并生成</button>
        </div>
      </div>
      <div id="lowfreq-backtest-content" class="sectors-content">
        <div class="empty">${lowfreqUiState.lastReportId ? `最近报告：${lowfreqUiState.lastReportId}` : '尚未生成报告。'}</div>
      </div>
    `;

    const startInput = $('lowfreq-backtest-start');
    const endInput = $('lowfreq-backtest-end');
    if (startInput) startInput.value = lowfreqUiState.backtestStart;
    if (endInput) endInput.value = lowfreqUiState.backtestEnd;
  }

  window.runLowfreqBacktestAll = async function() {
    const content = $('lowfreq-backtest-content');
    content.innerHTML = '<div class="loading">运行中（全历史可能较慢）...</div>';
    try {
      const startInput = $('lowfreq-backtest-start');
      const endInput = $('lowfreq-backtest-end');
      const startDate = startInput && startInput.value ? String(startInput.value) : '';
      const endDate = endInput && endInput.value ? String(endInput.value) : '';
      lowfreqUiState.backtestStart = startDate;
      lowfreqUiState.backtestEnd = endDate;
      storage.set('lowfreq.backtest.start', startDate);
      storage.set('lowfreq.backtest.end', endDate);

      const payload = { requested_by: 'dashboard' };
      if (startDate) payload.start_date = startDate;
      if (endDate) payload.end_date = endDate;
      const result = await apiPost('/api/v1/lowfreq/backtest/run', payload);
      const pdfUrl = result.pdf_url ? `${apiBaseUrl}${result.pdf_url}` : '';
      if (result.report_id) {
        lowfreqUiState.lastReportId = String(result.report_id);
        storage.set('lowfreq.backtest.last_report_id', lowfreqUiState.lastReportId);
      }
      content.innerHTML = `
        <div class="action-meta">回测区间：${result.start_date} → ${result.end_date}</div>
        <div class="action-meta">交易次数：${result.summary?.total_trades ?? '--'}，总收益率：${result.summary?.total_return_pct ?? '--'}%</div>
        <div class="action-meta">报告ID：${result.report_id}</div>
        <div style="margin-top: 10px; display:flex; gap:10px; flex-wrap:wrap;">
          ${pdfUrl ? `<a class="btn primary" href="${pdfUrl}" target="_blank" rel="noopener">下载 PDF</a>` : ''}
        </div>
      `;
      if (pdfUrl) {
        window.open(pdfUrl, '_blank', 'noopener');
      }
      showNotification('回测报告已生成', 'success');
    } catch (e) {
      content.innerHTML = `<div class="error">生成失败: ${e.message}</div>`;
      showNotification('回测报告生成失败: ' + e.message, 'error');
    }
  };

  // ==================== 2.3 候选池 ====================
  function initLowfreqCandidates() {
    const container = $('lowfreq-candidates-panel');
    if (!container) return;

    container.innerHTML = `
      <div class="sectors-header">
        <h3>候选池（买入信号）</h3>
        <div class="header-actions">
          <select id="lowfreq-candidates-mode" class="form-input form-input--compact" aria-label="候选池模式">
            <option value="buy_only">仅买入信号</option>
            <option value="topn">TopN（含未达阈值）</option>
          </select>
          <button class="btn secondary" onclick="loadLowfreqCandidates()">刷新</button>
        </div>
      </div>
      <div id="lowfreq-candidates-content" class="sectors-content">
        <div class="loading">加载中...</div>
      </div>
    `;

    const mode = $('lowfreq-candidates-mode');
    if (mode) {
      mode.value = lowfreqUiState.candidatesMode === 'topn' ? 'topn' : 'buy_only';
      mode.addEventListener('change', () => {
        lowfreqUiState.candidatesMode = mode.value === 'topn' ? 'topn' : 'buy_only';
        storage.set('lowfreq.candidates.mode', lowfreqUiState.candidatesMode);
        if (lowfreqSnapshotCache) {
          renderLowfreqCandidatesFromSnapshot(lowfreqSnapshotCache);
        }
      });
    }

    loadLowfreqCandidates();
  }

  window.loadLowfreqCandidates = async function() {
    const content = $('lowfreq-candidates-content');
    if (!content) return;
    content.innerHTML = '<div class="loading">加载中...</div>';

    try {
      const data = await fetchLowfreqSnapshot();
      renderLowfreqCandidatesFromSnapshot(data);
    } catch (e) {
      content.innerHTML = `<div class="error">加载失败: ${e.message}</div>`;
    }
  };

  function renderLowfreqCandidatesFromSnapshot(data) {
    const content = $('lowfreq-candidates-content');
    if (!content) return;

    const sectors = Array.isArray(data && data.sectors) ? data.sectors : [];
    const items = [];
    for (const sector of sectors) {
      const sectorName = sector && (sector.name || sector.code) ? String(sector.name || sector.code) : '';
      for (const group of ['leaders', 'middle', 'followers']) {
        const groupItems = Array.isArray(sector && sector[group]) ? sector[group] : [];
        for (const s of groupItems) {
          if (!s) continue;
          items.push({
            code: s.code,
            name: s.name,
            sector: sectorName,
            role: s.role || '',
            buy_score: s.buy_score ?? s.certainty ?? 0,
            return_5d: s.return_5d ?? 0,
            buy_signal: !!s.buy_signal,
            cup_handle_ok: !!s.cup_handle_ok,
            reasons: Array.isArray(s.reasons) ? s.reasons : [],
          });
        }
      }
    }

    items.sort((a, b) => Number(b.buy_score || 0) - Number(a.buy_score || 0));
    const mode = lowfreqUiState.candidatesMode === 'topn' ? 'topn' : 'buy_only';
    const filtered = mode === 'buy_only' ? items.filter(x => x.buy_signal) : items;
    const top = filtered.slice(0, mode === 'buy_only' ? 20 : 50);
    if (!top.length) {
      content.innerHTML = mode === 'buy_only'
        ? '<div class="empty">今日暂无买入信号候选</div>'
        : '<div class="empty">暂无候选（可能数据不足）</div>';
      return;
    }

    const rows = top.map((p) => `
      <tr class="${p.buy_signal ? 'row-buy-signal' : ''}">
        <td>${p.code}</td>
        <td>${p.name}</td>
        <td>${p.sector || '--'}</td>
        <td>${p.role || '--'}</td>
        <td>${formatNumber(p.buy_score, 0)}</td>
        <td>${formatPercent(p.return_5d)}</td>
        <td>${p.cup_handle_ok ? '是' : '否'}</td>
        <td>${p.reasons.slice(0, 4).map(r => `<span class="reason-pill" title="${escapeHtml(String(r))}">${escapeHtml(String(r))}</span>`).join('')}</td>
      </tr>
    `).join('');

    content.innerHTML = `
      <div class="action-meta">候选数：${top.length}${mode === 'buy_only' ? '（仅 buy_signal）' : '（TopN 含未达阈值）'}</div>
      <table class="results-table" style="margin-top: 10px;">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th>板块</th>
            <th>角色</th>
            <th>评分</th>
            <th>5日</th>
            <th>杯柄</th>
            <th>理由（Top4）</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  // ==================== 3. 筛选器管理 ====================
  function initScreenerPanel() {
    const container = $('screener-management-panel');
    if (!container) return;

    container.innerHTML = `
      <div class="screener-header">
        <h3>筛选器管理</h3>
        <button class="btn secondary" onclick="loadScreenerResults()">刷新结果</button>
      </div>
      <div id="screener-list" class="screener-list">
        <div class="loading">加载中...</div>
      </div>
    `;

    loadScreenerResults();
  }

  window.loadScreenerResults = async function() {
    const list = $('screener-list');
    list.innerHTML = '<div class="loading">加载中...</div>';
    
    try {
      const data = await apiGet('/api/v1/screeners');
      renderScreenerList(data.screeners || []);
    } catch (e) {
      list.innerHTML = `<div class="error">加载失败: ${e.message}</div>`;
    }
  };

  function renderScreenerList(screeners) {
    const list = $('screener-list');
    if (!screeners.length) {
      list.innerHTML = '<div class="empty">暂无筛选器</div>';
      return;
    }

    list.innerHTML = screeners.map((screener, idx) => `
      <div class="screener-item" data-id="${screener.id}">
        <div class="screener-summary" onclick="toggleScreener('${screener.id}')">
          <span class="screener-toggle">▶</span>
          <span class="screener-name">${screener.name}</span>
          <span class="screener-count">${screener.result_count || 0} 只</span>
          <span class="screener-status ${screener.enabled ? 'enabled' : 'disabled'}">${screener.enabled ? '启用' : '禁用'}</span>
          <button class="btn small" onclick="event.stopPropagation(); openScreenerConfig('${screener.id}')">参数</button>
          <button class="btn small" onclick="event.stopPropagation(); downloadScreenerCSV('${screener.id}')">下载CSV</button>
        </div>
        <div class="screener-detail" id="screener-detail-${screener.id}" style="display:none;">
          <div class="screener-description">${screener.description || '无描述'}</div>
          <div class="screener-results" id="screener-results-${screener.id}">
            ${renderScreenerResultsPreview(screener.results)}
          </div>
        </div>
      </div>
    `).join('');
  }

  function renderScreenerResultsPreview(results) {
    if (!results || !results.length) return '<div class="empty">无结果</div>';
    
    const preview = results.slice(0, 5);
    return `
      <table class="results-table">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th>板块</th>
            <th>得分</th>
          </tr>
        </thead>
        <tbody>
          ${preview.map(r => `
            <tr>
              <td>${r.code}</td>
              <td>${r.name}</td>
              <td>${r.sector || '--'}</td>
              <td>${formatNumber(r.score)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${results.length > 5 ? `<div class="more-results">还有 ${results.length - 5} 条结果...</div>` : ''}
    `;
  }

  window.toggleScreener = function(id) {
    const detail = $(`screener-detail-${id}`);
    const toggle = detail.previousElementSibling.querySelector('.screener-toggle');
    if (detail.style.display === 'none') {
      detail.style.display = 'block';
      toggle.textContent = '▼';
    } else {
      detail.style.display = 'none';
      toggle.textContent = '▶';
    }
  };

  window.openScreenerConfig = async function(id) {
    try {
      const data = await apiGet(`/api/v1/screeners/${id}/config`);
      showScreenerConfigModal(id, data);
    } catch (e) {
      showNotification('加载配置失败: ' + e.message, 'error');
    }
  };

  function showScreenerConfigModal(id, config) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h3>筛选器参数配置</h3>
          <button class="btn" onclick="this.closest('.modal-overlay').remove()">关闭</button>
        </div>
        <div class="modal-body">
          <div id="config-form">
            ${renderConfigForm(config)}
          </div>
          <div class="modal-actions">
            <button class="btn primary" onclick="saveScreenerConfig('${id}')">保存</button>
            <button class="btn" onclick="resetScreenerConfig('${id}')">重置默认</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  function renderConfigForm(config) {
    return Object.entries(config).map(([key, value]) => {
      const type = typeof value;
      if (type === 'boolean') {
        return `
          <label class="config-item">
            <span>${key}</span>
            <input type="checkbox" name="${key}" ${value ? 'checked' : ''}>
          </label>
        `;
      } else if (type === 'number') {
        return `
          <label class="config-item">
            <span>${key}</span>
            <input type="number" name="${key}" value="${value}" step="any">
          </label>
        `;
      } else {
        return `
          <label class="config-item">
            <span>${key}</span>
            <input type="text" name="${key}" value="${value}">
          </label>
        `;
      }
    }).join('');
  }

  window.saveScreenerConfig = async function(id) {
    const modal = document.querySelector('.modal-overlay');
    const inputs = modal.querySelectorAll('input');
    const config = {};
    inputs.forEach(input => {
      if (input.type === 'checkbox') {
        config[input.name] = input.checked;
      } else if (input.type === 'number') {
        config[input.name] = parseFloat(input.value);
      } else {
        config[input.name] = input.value;
      }
    });

    try {
      await apiPost(`/api/v1/screeners/${id}/config`, config);
      showNotification('配置已保存', 'success');
      modal.remove();
    } catch (e) {
      showNotification('保存失败: ' + e.message, 'error');
    }
  };

  window.downloadScreenerCSV = async function(id) {
    try {
      const data = await apiGet(`/api/v1/screeners/${id}/results`);
      const csv = convertToCSV(data.results || []);
      downloadFile(csv, `screener_${id}_${new Date().toISOString().slice(0,10)}.csv`, 'text/csv');
    } catch (e) {
      showNotification('下载失败: ' + e.message, 'error');
    }
  };

  function convertToCSV(data) {
    if (!data.length) return '';
    const headers = Object.keys(data[0]);
    const rows = data.map(row => headers.map(h => {
      const val = row[h];
      if (val === null || val === undefined) return '';
      if (typeof val === 'string' && val.includes(',')) return `"${val}"`;
      return val;
    }).join(','));
    return [headers.join(','), ...rows].join('\n');
  }

  function downloadFile(content, filename, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ==================== 4. 股票CHECK功能 ====================
  function initStockCheck() {
    const container = $('stock-check-panel');
    if (!container) return;

    container.innerHTML = `
      <div class="stock-check-header">
        <h3>股票 CHECK</h3>
        <div class="stock-check-input">
          <input type="text" id="stock-check-code" placeholder="输入6位股票代码，如: 600000" maxlength="6">
          <button class="btn primary" onclick="checkStock()">检查</button>
        </div>
      </div>
      <div id="stock-check-result" class="stock-check-result">
        <div class="empty">请输入股票代码进行检查</div>
      </div>
    `;
  }

  window.checkStock = async function() {
    const codeInput = $('stock-check-code');
    const resultDiv = $('stock-check-result');
    const code = codeInput.value.trim();
    
    if (!code || code.length !== 6 || !/^\d{6}$/.test(code)) {
      resultDiv.innerHTML = '<div class="error">请输入有效的6位股票代码</div>';
      return;
    }

    resultDiv.innerHTML = '<div class="loading">检查中...</div>';
    
    try {
      const data = await apiGet(`/api/v1/stock/${code}/check`);
      renderStockCheckResult(code, data);
    } catch (e) {
      resultDiv.innerHTML = `<div class="error">检查失败: ${e.message}</div>`;
    }
  };

  function renderStockCheckResult(code, data) {
    const resultDiv = $('stock-check-result');
    const passed = data.passed_screeners || [];
    const failed = data.failed_screeners || [];
    
    resultDiv.innerHTML = `
      <div class="stock-check-summary">
        <h4>${code} ${data.name || ''}</h4>
        <div class="check-stats">
          <span class="stat passed">通过: ${passed.length}</span>
          <span class="stat failed">未通过: ${failed.length}</span>
        </div>
      </div>
      
      ${passed.length > 0 ? `
        <div class="check-section passed-section">
          <h5>通过的筛选器</h5>
          <ul class="screener-list">
            ${passed.map(s => `
              <li class="screener-item passed">
                <span class="screener-name">${s.name}</span>
                <span class="screener-score">得分: ${formatNumber(s.score)}</span>
              </li>
            `).join('')}
          </ul>
        </div>
      ` : ''}
      
      ${failed.length > 0 ? `
        <div class="check-section failed-section">
          <h5>未通过的筛选器</h5>
          <ul class="screener-list">
            ${failed.map(s => `
              <li class="screener-item failed">
                <span class="screener-name">${s.name}</span>
                <span class="fail-reason">原因: ${s.reason}</span>
              </li>
            `).join('')}
          </ul>
        </div>
      ` : ''}
      
      <div class="stock-extra-info">
        <h5>个股信息</h5>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">所属板块:</span>
            <span class="value">${data.sector || '--'}</span>
          </div>
          <div class="info-item">
            <span class="label">个股分层:</span>
            <span class="value">${data.tier || '--'}</span>
          </div>
          <div class="info-item">
            <span class="label">RPS评分:</span>
            <span class="value">${formatNumber(data.rps, 1)}</span>
          </div>
          <div class="info-item">
            <span class="label">确定性评分:</span>
            <span class="value">${formatNumber(data.certainty, 1)}</span>
          </div>
        </div>
      </div>
    `;
  }

  // ==================== 通知系统 ====================
  function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
      notification.classList.add('show');
    }, 10);
    
    setTimeout(() => {
      notification.classList.remove('show');
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }

  // ==================== 初始化 ====================
  function init() {
    initQuickActions();
    initHotSectors();
    initLowfreqPortfolio();
    initLowfreqCandidates();
    initLowfreqBacktest();
    initScreenerPanel();
    initStockCheck();
  }

  // DOM 加载完成后初始化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
