import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, Flame, Target, Wallet, FileText, RefreshCw } from 'lucide-react';
import { useApp } from '../context/AppContext';
import SemanticBadge from '../components/SemanticBadge';
import DateSelector from '../components/DateSelector';
import StockCodeLink from '../components/StockCodeLink';
import { fetchApi } from '../services/api';
import { createBlockState, rejectBlock, resolveBlock, startBlock } from '../services/asyncBlocks';

function SimpleCard({ title, value, subtitle }) {
  const displayValue = value == null || value === '' ? '--' : value;
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="text-sm font-medium text-gray-500 mb-2">{title}</div>
      <div className="text-2xl font-bold text-gray-900 mb-1">{displayValue}</div>
      {subtitle ? <div className="text-sm text-gray-500">{subtitle}</div> : null}
    </div>
  );
}

function BlockMessage({ tone = 'gray', message, onRetry, retryLabel = '重试' }) {
  const toneClass =
    tone === 'red'
      ? 'bg-red-50 border-red-200 text-red-700'
      : 'bg-gray-50 border-gray-200 text-gray-600';
  return (
    <div className={`rounded-lg border p-4 text-sm flex items-center justify-between gap-3 ${toneClass}`}>
      <span>{message}</span>
      {typeof onRetry === 'function' ? (
        <button
          type="button"
          onClick={onRetry}
          className="px-3 py-1 rounded bg-white text-gray-700 border border-gray-200 hover:bg-gray-50"
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}

function toLocalDateString(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${dd}`;
}

function minusDays(isoDate, days) {
  const [y, m, d] = String(isoDate || '').split('-').map((x) => Number(x));
  if (!y || !m || !d) return null;
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() - Number(days || 0));
  return toLocalDateString(dt);
}

function conceptRiskBadge(v) {
  const lv = String(v || '').trim().toLowerCase();
  if (lv === 'exit') return { key: 'not_qualified_avoid', label: '回避' };
  if (lv === 'warn') return { key: 'risk_warn', label: '危险状态' };
  if (lv === 'ok') return { key: 'risk_ok', label: '稳定状态' };
  return null;
}

function queueStatusBadge(rawStatus, cancelReason) {
  if (rawStatus === 'executed') return { key: 'queue_executed', label: '已处理' };
  if (rawStatus === 'cancelled' && cancelReason === 'abandoned') {
    return { key: 'queue_abandoned', label: '已放弃' };
  }
  if (rawStatus === 'cancelled') {
    return {
      key: 'queue_cancelled',
      label: cancelReason ? `已取消（${cancelReason}）` : '已取消',
    };
  }
  return { key: 'queue_pending', label: '待处理' };
}

function queueRiskBadge(risk, isSell) {
  const lv = String(risk || '').trim().toLowerCase();
  if (lv === 'exit') {
    return { key: isSell ? 'exit_signal' : 'not_qualified_avoid', label: isSell ? '离场信号' : '回避' };
  }
  if (lv === 'warn') return { key: 'risk_warn', label: '危险状态' };
  if (lv === 'ok') return { key: 'risk_ok', label: '稳定状态' };
  return null;
}

function findLatestTushareFailure(resources) {
  if (!resources || typeof resources !== 'object') return null;
  let latest = null;
  for (const [resource, payload] of Object.entries(resources)) {
    if (!payload || typeof payload !== 'object') continue;
    const lastFailureAt = String(payload.last_failure_at || '').trim();
    const lastOkAt = String(payload.last_ok_at || '').trim();
    if (!lastFailureAt) continue;
    if (lastOkAt && lastOkAt >= lastFailureAt) continue;
    if (!latest || lastFailureAt > latest.lastFailureAt) {
      latest = {
        resource,
        lastFailureAt,
        reason: String(payload.last_failure_reason || '').trim(),
      };
    }
  }
  return latest;
}

export default function Overview() {
  const { selectedDate } = useApp();
  const [error, setError] = useState(null);
  const [mutating, setMutating] = useState(false);
  const [actionState, setActionState] = useState({ kind: null, intentId: null });
  const [blocks, setBlocks] = useState({
    core: createBlockState(),
    sectors: createBlockState(),
    queue: createBlockState(),
    backtest: createBlockState(),
  });

  const backtestEndDate = useMemo(() => minusDays(selectedDate, 1) || selectedDate, [selectedDate]);

  const loadCoreBlock = useCallback(async () => {
    setBlocks((prev) => ({ ...prev, core: startBlock(prev.core, true) }));
    try {
      const [dataStatus, conceptsMainline] = await Promise.all([
        fetchApi('/api/data/status', {}, { timeoutMs: 45000 }),
        fetchApi(
          `/api/concepts/mainline?date=${encodeURIComponent(selectedDate)}&limit=10`,
          {},
          { timeoutMs: 45000 }
        ),
      ]);
      setBlocks((prev) => ({ ...prev, core: resolveBlock({ dataStatus, conceptsMainline }) }));
    } catch (e) {
      setBlocks((prev) => ({ ...prev, core: rejectBlock(prev.core, e, true) }));
    }
  }, [selectedDate]);

  const loadSectorsBlock = useCallback(async () => {
    setBlocks((prev) => ({ ...prev, sectors: startBlock(prev.sectors, true) }));
    try {
      const hotSectors = await fetchApi(
        `/api/sectors/hot?date=${encodeURIComponent(selectedDate)}&include_sell_signal=true`,
        {},
        { timeoutMs: 45000 }
      );
      setBlocks((prev) => ({ ...prev, sectors: resolveBlock({ hotSectors }) }));
    } catch (e) {
      setBlocks((prev) => ({ ...prev, sectors: rejectBlock(prev.sectors, e, true) }));
    }
  }, [selectedDate]);

  const loadQueueBlock = useCallback(async () => {
    setBlocks((prev) => ({ ...prev, queue: startBlock(prev.queue, true) }));
    try {
      const executionQueue = await fetchApi(
        `/api/lowfreq/execution/queue?date=${encodeURIComponent(selectedDate)}&ensure_generated=true`,
        {},
        { timeoutMs: 45000 }
      );
      setBlocks((prev) => ({ ...prev, queue: resolveBlock({ executionQueue }) }));
    } catch (e) {
      setBlocks((prev) => ({ ...prev, queue: rejectBlock(prev.queue, e, true) }));
    }
  }, [selectedDate]);

  const loadBacktestBlock = useCallback(async () => {
    setBlocks((prev) => ({ ...prev, backtest: startBlock(prev.backtest, true) }));
    try {
      const backtestWindow = await fetchApi(
        `/api/lowfreq/backtest/window-summary?end_date=${encodeURIComponent(
          backtestEndDate
        )}&window_trading_days=60`,
        {},
        { timeoutMs: 60000 }
      );
      setBlocks((prev) => ({ ...prev, backtest: resolveBlock({ backtestWindow }) }));
    } catch (e) {
      setBlocks((prev) => ({ ...prev, backtest: rejectBlock(prev.backtest, e, true) }));
    }
  }, [backtestEndDate]);

  const fetchData = useCallback(async () => {
    setError(null);
    await loadCoreBlock();
    void loadSectorsBlock();
    void loadQueueBlock();
    void loadBacktestBlock();
  }, [loadBacktestBlock, loadCoreBlock, loadQueueBlock, loadSectorsBlock]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const corePayload = blocks.core.data || {};
  const sectorsPayload = blocks.sectors.data || {};
  const queuePayload = blocks.queue.data || {};
  const backtestPayload = blocks.backtest.data || {};
  const loading = Object.values(blocks).some((block) => block.loading);
  const latestAvailableDate =
    corePayload.dataStatus?.latest_available_date ||
    corePayload.dataStatus?.latest_trade_date ||
    '--';
  const latestTushareFailure = findLatestTushareFailure(corePayload.dataStatus?.tushare?.resources);

  const sectors = Array.isArray(sectorsPayload.hotSectors?.sectors)
    ? sectorsPayload.hotSectors.sectors
    : [];
  const topSectors = sectors.slice(0, 5);
  const portfolio = sectorsPayload.hotSectors?.portfolio || null;
  const mainlineConcepts = Array.isArray(corePayload.conceptsMainline?.concepts)
    ? corePayload.conceptsMainline.concepts
    : [];
  const mainlineRiskCounts = (() => {
    const counts = { ok: 0, warn: 0, exit: 0 };
    for (const c of mainlineConcepts) {
      const lv = String(c?.risk_level || '').trim();
      if (lv === 'ok' || lv === 'warn' || lv === 'exit') counts[lv] += 1;
    }
    return counts;
  })();
  const queueItems = Array.isArray(queuePayload.executionQueue?.queue) ? queuePayload.executionQueue.queue : [];
  const autopilotEnabled = Boolean(queuePayload.executionQueue?.autopilot_enabled);
  const pageError = error || (!blocks.core.loaded && blocks.core.error ? blocks.core.error : null);

  const postJson = async (url, payload) => {
    return fetchApi(
      url,
      { method: 'POST', body: JSON.stringify(payload) },
      { timeoutMs: 30000 }
    );
  };

  const toggleAutopilot = async (nextEnabled) => {
    setMutating(true);
    setError(null);
    setActionState({ kind: 'autopilot', intentId: null });
    try {
      await postJson('/api/lowfreq/settings/autopilot', {
        enabled: Boolean(nextEnabled),
        requested_by: 'dashboard.react',
      });
      await fetchData();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setActionState({ kind: null, intentId: null });
      setMutating(false);
    }
  };

  const executeIntent = async (intentId) => {
    setMutating(true);
    setError(null);
    setActionState({ kind: 'execute', intentId: String(intentId || '').trim() });
    try {
      await postJson('/api/lowfreq/execution/processed', {
        intent_id: String(intentId || '').trim(),
        requested_by: 'dashboard.react',
      });
      await fetchData();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setActionState({ kind: null, intentId: null });
      setMutating(false);
    }
  };

  const markAbandoned = async (intentId) => {
    setMutating(true);
    setError(null);
    setActionState({ kind: 'abandon', intentId: String(intentId || '').trim() });
    try {
      await postJson('/api/lowfreq/execution/abandon', {
        intent_id: String(intentId || '').trim(),
        reason: 'abandoned',
        requested_by: 'dashboard.react',
      });
      await fetchData();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setActionState({ kind: null, intentId: null });
      setMutating(false);
    }
  };

  const buySignals = (() => {
    let cnt = 0;
    for (const sec of sectors) {
      const items = []
        .concat(sec?.leaders || [])
        .concat(sec?.middle || [])
        .concat(sec?.followers || []);
      for (const s of items) {
        if (s?.buy_signal) cnt += 1;
      }
    }
    return cnt;
  })();

  return (
    <div className="space-y-6">
      <DateSelector onRefresh={fetchData} loading={loading} />

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">今日总览</h2>
          <div className="text-gray-500 mt-1">聚焦：数据更新、昨日回测、热门板块、入场信号、虚拟持仓</div>
        </div>
        <button
          onClick={fetchData}
          disabled={loading || mutating}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          刷新
        </button>
      </div>

      {pageError ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3 text-red-700">
          <AlertCircle size={20} />
          <span>{pageError}</span>
        </div>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <SimpleCard title="数据更新到" value={latestAvailableDate} subtitle="本地可用最新日期" />
        <SimpleCard title="热门板块 Top5" value={String(topSectors.length)} subtitle="板块轮动快照" />
        <SimpleCard title="买入信号" value={String(buySignals)} subtitle="热门板块内买入信号数量" />
        <SimpleCard
          title="虚拟持仓收益"
          value={
            portfolio && typeof portfolio.total_return_pct === 'number'
              ? `${portfolio.total_return_pct >= 0 ? '+' : ''}${portfolio.total_return_pct.toFixed(2)}%`
              : '--'
          }
          subtitle={portfolio?.as_of ? `当前虚拟组合累计收益｜数据日期：${portfolio.as_of}` : '当前虚拟组合累计收益'}
        />
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4 text-sm text-gray-600">
        <span className="font-medium text-gray-900">当前 authoritative 口径</span>
        <span className="ml-3">日线主源：Tushare</span>
        <span className="ml-3">safety-net：Tencent</span>
        {latestTushareFailure ? (
          <span className="ml-3 text-red-700">
            最近异常：{latestTushareFailure.resource} @ {latestTushareFailure.lastFailureAt}
            {latestTushareFailure.reason ? ` (${latestTushareFailure.reason})` : ''}
          </span>
        ) : null}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Flame size={20} className="text-orange-500" />
          主线概念（Top10）
        </h3>
        <div className="text-sm text-gray-600 mb-3">
          风险灯：<span className="text-gray-700 font-semibold">回避 {mainlineRiskCounts.exit}</span>{' '}
          <span className="text-orange-600 font-semibold">危险状态 {mainlineRiskCounts.warn}</span>{' '}
          <span className="text-green-700 font-semibold">稳定状态 {mainlineRiskCounts.ok}</span>
        </div>
        {blocks.core.loading && !blocks.core.loaded ? (
          <BlockMessage message="主线概念加载中..." />
        ) : blocks.core.error && !blocks.core.loaded ? (
          <BlockMessage tone="red" message={blocks.core.error} onRetry={loadCoreBlock} />
        ) : mainlineConcepts.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2 pr-4">排名</th>
                  <th className="py-2 pr-4">概念</th>
                  <th className="py-2 pr-4">主线分</th>
                  <th className="py-2 pr-4">持久</th>
                  <th className="py-2 pr-4">风险</th>
                </tr>
              </thead>
              <tbody>
                {mainlineConcepts.map((c) => (
                  <tr key={c.concept_code} className="border-b last:border-b-0">
                    <td className="py-2 pr-4 text-gray-700">{c.mainline_rank}</td>
                    <td className="py-2 pr-4">
                      <div className="text-gray-900 font-medium">{c.concept_name}</div>
                      <div className="text-gray-500">{c.concept_code}</div>
                    </td>
                    <td className="py-2 pr-4 text-gray-900">
                      {typeof c.mainline_score === 'number' ? c.mainline_score.toFixed(1) : '--'}
                    </td>
                    <td className="py-2 pr-4 text-gray-700">
                      {typeof c.mainline_streak === 'number' ? `${c.mainline_streak}d` : '--'}
                    </td>
                    <td className="py-2 pr-4">
                      {conceptRiskBadge(c.risk_level) ? (
                        <SemanticBadge
                          semanticKey={conceptRiskBadge(c.risk_level).key}
                          label={conceptRiskBadge(c.risk_level).label}
                        />
                      ) : (
                        <span className="text-gray-500">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-gray-600">暂无主线概念数据</div>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Target size={20} />
          买入 / 卖出 / 调整仓位（执行队列）
        </h3>
        <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
          <div className="flex items-center gap-3">
            <label className="inline-flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={autopilotEnabled}
                onChange={(e) => toggleAutopilot(e.target.checked)}
                disabled={loading || mutating}
              />
              自动操盘（自动保存）
            </label>
            <span className="text-sm text-gray-500">
              当前模式：{autopilotEnabled ? '自动执行（方案1）' : '人工执行队列（方案2）'}
            </span>
          </div>
          <div className="text-sm text-gray-500">本机访问默认放行，无需 API Key</div>
        </div>

        {blocks.queue.loading && !blocks.queue.loaded ? (
          <BlockMessage message="执行队列加载中..." />
        ) : blocks.queue.error && !blocks.queue.loaded ? (
          <BlockMessage tone="red" message={blocks.queue.error} onRetry={loadQueueBlock} />
        ) : queueItems.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2 pr-4">类型</th>
                  <th className="py-2 pr-4">股票</th>
                  <th className="py-2 pr-4">执行日</th>
                  <th className="py-2 pr-4">状态</th>
                  <th className="py-2 pr-4">说明</th>
                  <th className="py-2 pr-4">操作</th>
                </tr>
              </thead>
              <tbody>
                {queueItems.map((it) => {
                  const rawStatus = String(it?.status || 'pending');
                  const cancelReason = String(it?.cancel_reason || '').trim();
                  const isPending = rawStatus === 'pending';
                  const isBuy = it?.intent_type === 'buy_intent';
                  const isSell = it?.intent_type === 'sell_intent';
                  const isBusy = Boolean(actionState?.intentId) && actionState.intentId === String(it.intent_id);
                  const typeLabel = isBuy ? '买入' : it?.intent_type === 'sell_intent' ? '卖出' : String(it?.intent_type || '--');
                  const canExecute =
                    (it?.can_execute === undefined || Boolean(it?.can_execute)) &&
                    (!it?.execute_date || String(it.execute_date) <= String(selectedDate));
                  const blockedReason =
                    !canExecute && String(it?.blocked_reason || '').trim() === 'execute_date_not_reached'
                      ? '未到执行日'
                      : !canExecute
                      ? '暂不可执行'
                      : null;
                  const prob =
                    typeof it?.certainty_prob === 'number'
                      ? it.certainty_prob
                      : typeof it?.confidence_prob === 'number'
                      ? it.confidence_prob
                      : null;
                  const samples =
                    typeof it?.certainty_samples === 'number'
                      ? it.certainty_samples
                      : typeof it?.confidence_samples === 'number'
                      ? it.confidence_samples
                      : null;
                  const certaintyText =
                    prob !== null ? `确定性=${Math.round(prob * 100)}%${samples !== null ? `（n=${samples}）` : ''}` : '确定性=--';
                  const noteBase = isBuy ? certaintyText : String(it?.sell_reason || it?.sell_signal || '--');
                  const note = blockedReason ? `${noteBase}｜${blockedReason}` : noteBase;
                  const risk = String(it?.risk_level || '').trim();
                  const statusBadge = queueStatusBadge(rawStatus, cancelReason);
                  const riskBadge = queueRiskBadge(risk, isSell);
                  return (
                    <tr key={it.intent_id} className="border-b last:border-b-0">
                      <td className="py-2 pr-4 text-gray-700">{typeLabel}</td>
                      <td className="py-2 pr-4">
                        <div className="text-gray-900 font-medium">
                          {it?.name || '--'}{' '}
                          <StockCodeLink code={it?.code} className="text-gray-500 hover:text-blue-600 hover:underline">
                            {it?.code || '--'}
                          </StockCodeLink>
                        </div>
                        <div className="text-gray-500">{it?.sector || '--'}</div>
                      </td>
                      <td className="py-2 pr-4 text-gray-700">{it?.execute_date || '--'}</td>
                      <td className="py-2 pr-4">
                        <div className="flex items-center gap-2 flex-wrap">
                          <SemanticBadge semanticKey={statusBadge.key} label={statusBadge.label} />
                          {riskBadge ? (
                            <SemanticBadge semanticKey={riskBadge.key} label={riskBadge.label} />
                          ) : null}
                        </div>
                      </td>
                      <td className="py-2 pr-4 text-gray-700">{note}</td>
                      <td className="py-2 pr-4">
                        <div className="flex items-center gap-2">
                          <button
                            className="px-3 py-1 rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                            disabled={!isPending || !isBuy || !canExecute || loading || mutating}
                            onClick={() => executeIntent(it.intent_id)}
                          >
                            {isBusy && actionState.kind === 'execute' ? '处理中…' : '买入'}
                          </button>
                          <button
                            className="px-3 py-1 rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                            disabled={!isPending || !isSell || !canExecute || loading || mutating}
                            onClick={() => executeIntent(it.intent_id)}
                          >
                            {isBusy && actionState.kind === 'execute' ? '处理中…' : '卖出'}
                          </button>
                          <button
                            className="px-3 py-1 rounded bg-gray-200 text-gray-800 hover:bg-gray-300 disabled:opacity-50"
                            disabled={!isPending || loading || mutating}
                            onClick={() => markAbandoned(it.intent_id)}
                          >
                            {isBusy && actionState.kind === 'abandon' ? '处理中…' : '放弃'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-gray-600">暂无执行队列数据</div>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <FileText size={20} />
          昨日回测（窗口 60 交易日）
        </h3>
        {blocks.backtest.loading && !blocks.backtest.loaded ? (
          <BlockMessage message="昨日回测加载中..." />
        ) : blocks.backtest.error && !blocks.backtest.loaded ? (
          <BlockMessage tone="red" message={blocks.backtest.error} onRetry={loadBacktestBlock} />
        ) : backtestPayload.backtestWindow?._meta?.status === 'ok' ? (
          <div className="flex items-center justify-between gap-3 flex-wrap text-sm">
            <div className="text-gray-700">
              窗口：{backtestPayload.backtestWindow.start_date} → {backtestPayload.backtestWindow.end_date}
            </div>
            <div className="text-gray-700">
              窗口回测总收益：
              {typeof backtestPayload.backtestWindow?.report?.summary?.total_return_pct === 'number' ? (
                <span className={backtestPayload.backtestWindow.report.summary.total_return_pct >= 0 ? 'text-red-600 font-semibold' : 'text-green-600 font-semibold'}>
                  {backtestPayload.backtestWindow.report.summary.total_return_pct >= 0 ? '+' : ''}
                  {backtestPayload.backtestWindow.report.summary.total_return_pct.toFixed(2)}%
                </span>
              ) : (
                <span className="text-gray-500">--</span>
              )}
            </div>
            <div className="flex items-center gap-3">
              {backtestPayload.backtestWindow?.report?.pdf_url ? (
                <a className="text-blue-600 hover:underline" href={backtestPayload.backtestWindow.report.pdf_url} target="_blank" rel="noreferrer">
                  下载 PDF
                </a>
              ) : null}
              {backtestPayload.backtestWindow?.report?.json_url ? (
                <a className="text-blue-600 hover:underline" href={backtestPayload.backtestWindow.report.json_url} target="_blank" rel="noreferrer">
                  下载 JSON
                </a>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="text-sm text-gray-600">
            {backtestPayload.backtestWindow?.message || '未生成该窗口回测报告'}
          </div>
        )}
      </div>

      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Flame size={20} className="text-orange-500" />
          最新热门板块（Top5）
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {blocks.sectors.loading && !blocks.sectors.loaded ? (
            <BlockMessage message="热门板块加载中..." />
          ) : blocks.sectors.error && !blocks.sectors.loaded ? (
            <BlockMessage tone="red" message={blocks.sectors.error} onRetry={loadSectorsBlock} />
          ) : topSectors.map((sec, idx) => (
            <div key={idx} className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="text-lg font-semibold text-gray-900">{sec.name}</div>
                  <div className="text-sm text-gray-500">{sec.code}</div>
                </div>
                <div className="flex items-center gap-1 text-orange-500">
                  <Flame size={18} />
                  <span className="font-bold">{sec.heat_score?.toFixed(1) || '--'}</span>
                </div>
              </div>

              <div className="space-y-3 text-sm">
                <div>
                  <div className="text-gray-700 font-medium mb-1">龙头（2）</div>
                  <div className="space-y-1">
                    {(sec.leaders || []).slice(0, 2).map((s) => (
                      <div key={s.code} className="flex items-center justify-between bg-gray-50 border border-gray-100 rounded px-3 py-2">
                        <div className="text-gray-900">
                          {s.name}{' '}
                          <StockCodeLink code={s.code} className="text-gray-500 hover:text-blue-600 hover:underline">
                            {s.code || '--'}
                          </StockCodeLink>
                        </div>
                        <div className="inline-flex items-center gap-3">
                          {typeof (s.certainty_prob ?? s.confidence_prob) === 'number' ? (
                            <span className="text-gray-700">
                              确定性 {Math.round((s.certainty_prob ?? s.confidence_prob) * 100)}%
                              {typeof (s.certainty_samples ?? s.confidence_samples) === 'number' ? (
                                <span className="text-gray-500">（n={s.certainty_samples ?? s.confidence_samples}）</span>
                              ) : null}
                            </span>
                          ) : (
                            <span className="text-gray-500">确定性 —</span>
                          )}
                          {conceptRiskBadge(s.risk_level) ? (
                            <SemanticBadge
                              semanticKey={conceptRiskBadge(s.risk_level).key}
                              label={conceptRiskBadge(s.risk_level).label}
                            />
                          ) : (
                            <span className="text-gray-500">—</span>
                          )}
                          {s.buy_signal ? (
                            <div className="inline-flex items-center gap-1">
                              <Target size={14} className="text-green-700" />
                              <SemanticBadge semanticKey="entry_ready" label="入场" />
                            </div>
                          ) : null}
                        </div>
                      </div>
          ))}
                  </div>
                </div>

                <div>
                  <div className="text-gray-700 font-medium mb-1">中军（2）</div>
                  <div className="space-y-1">
                    {(sec.middle || []).slice(0, 2).map((s) => (
                      <div key={s.code} className="flex items-center justify-between bg-gray-50 border border-gray-100 rounded px-3 py-2">
                        <div className="text-gray-900">
                          {s.name}{' '}
                          <StockCodeLink code={s.code} className="text-gray-500 hover:text-blue-600 hover:underline">
                            {s.code || '--'}
                          </StockCodeLink>
                        </div>
                        <div className="inline-flex items-center gap-3">
                          {typeof (s.certainty_prob ?? s.confidence_prob) === 'number' ? (
                            <span className="text-gray-700">
                              确定性 {Math.round((s.certainty_prob ?? s.confidence_prob) * 100)}%
                              {typeof (s.certainty_samples ?? s.confidence_samples) === 'number' ? (
                                <span className="text-gray-500">（n={s.certainty_samples ?? s.confidence_samples}）</span>
                              ) : null}
                            </span>
                          ) : (
                            <span className="text-gray-500">确定性 —</span>
                          )}
                          {conceptRiskBadge(s.risk_level) ? (
                            <SemanticBadge
                              semanticKey={conceptRiskBadge(s.risk_level).key}
                              label={conceptRiskBadge(s.risk_level).label}
                            />
                          ) : (
                            <span className="text-gray-500">—</span>
                          )}
                          {s.buy_signal ? (
                            <div className="inline-flex items-center gap-1">
                              <Target size={14} className="text-green-700" />
                              <SemanticBadge semanticKey="entry_ready" label="入场" />
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="text-gray-700 font-medium mb-1">跟随（2）</div>
                  <div className="space-y-1">
                    {(sec.followers || []).slice(0, 2).map((s) => (
                      <div key={s.code} className="flex items-center justify-between bg-gray-50 border border-gray-100 rounded px-3 py-2">
                        <div className="text-gray-900">
                          {s.name}{' '}
                          <StockCodeLink code={s.code} className="text-gray-500 hover:text-blue-600 hover:underline">
                            {s.code || '--'}
                          </StockCodeLink>
                        </div>
                        <div className="inline-flex items-center gap-3">
                          {typeof (s.certainty_prob ?? s.confidence_prob) === 'number' ? (
                            <span className="text-gray-700">
                              确定性 {Math.round((s.certainty_prob ?? s.confidence_prob) * 100)}%
                              {typeof (s.certainty_samples ?? s.confidence_samples) === 'number' ? (
                                <span className="text-gray-500">（n={s.certainty_samples ?? s.confidence_samples}）</span>
                              ) : null}
                            </span>
                          ) : (
                            <span className="text-gray-500">确定性 —</span>
                          )}
                          {conceptRiskBadge(s.risk_level) ? (
                            <SemanticBadge
                              semanticKey={conceptRiskBadge(s.risk_level).key}
                              label={conceptRiskBadge(s.risk_level).label}
                            />
                          ) : (
                            <span className="text-gray-500">—</span>
                          )}
                          {s.buy_signal ? (
                            <div className="inline-flex items-center gap-1">
                              <Target size={14} className="text-green-700" />
                              <SemanticBadge semanticKey="entry_ready" label="入场" />
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
        {!sectors.length ? (
          <div className="text-center py-12 text-gray-500">暂无热门板块数据</div>
        ) : null}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Wallet size={20} />
          虚拟持仓
        </h3>
        {portfolio?.open_positions?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">代码</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">名称</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">板块</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">买入日</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">盈亏</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.open_positions.map((pos) => (
                  <tr key={pos.code} className="border-b border-gray-100">
                    <td className="py-3 px-4 text-gray-900">
                      <StockCodeLink code={pos.code} className="hover:text-blue-600 hover:underline">
                        {pos.code || '--'}
                      </StockCodeLink>
                    </td>
                    <td className="py-3 px-4 text-gray-900">{pos.name}</td>
                    <td className="py-3 px-4 text-gray-500">{pos.sector}</td>
                    <td className="py-3 px-4 text-gray-500">{pos.buy_date || '--'}</td>
                    <td className="py-3 px-4">
                      <span className={pos.unrealized_pnl_pct >= 0 ? 'text-red-600' : 'text-green-600'}>
                        {pos.unrealized_pnl_pct >= 0 ? '+' : ''}
                        {pos.unrealized_pnl_pct?.toFixed(2)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-gray-500">当前无持仓</div>
        )}
      </div>
    </div>
  );
}
