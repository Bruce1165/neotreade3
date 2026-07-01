import { useCallback, useEffect, useState } from 'react';
import { Flame, Target, Calendar, AlertCircle, Loader2, Wallet, ListFilter, FileText } from 'lucide-react';
import { useApp } from '../context/AppContext';
import DateSelector from '../components/DateSelector';
import SemanticBadge from '../components/SemanticBadge';
import StockCodeLink from '../components/StockCodeLink';
import { fetchApi } from '../services/api';
import { createBlockState, rejectBlock, resolveBlock, startBlock } from '../services/asyncBlocks';

function BlockMessage({ tone = 'gray', message, onRetry }) {
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
          重试
        </button>
      ) : null}
    </div>
  );
}

function safeNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function formatAmountWan(value) {
  const numeric = safeNumber(value);
  return numeric == null ? '--' : `¥${(numeric / 10000).toFixed(2)}万`;
}

function formatCurrency(value) {
  const numeric = safeNumber(value);
  return numeric == null ? '--' : `¥${numeric.toFixed(2)}`;
}

function formatPercent(value, { signed = false } = {}) {
  const numeric = safeNumber(value);
  if (numeric == null) {
    return '--';
  }
  const prefix = signed && numeric >= 0 ? '+' : '';
  return `${prefix}${numeric.toFixed(2)}%`;
}

function signedNumberClass(value) {
  const numeric = safeNumber(value);
  if (numeric == null) {
    return 'text-gray-500';
  }
  return numeric >= 0 ? 'text-red-600' : 'text-green-600';
}

function displayText(value) {
  const text = String(value ?? '').trim();
  return text || '--';
}

function manualIntentTypeBadge(intentType) {
  const value = String(intentType || '').trim();
  if (value === 'buy_intent') return { key: 'entry_ready', label: '买入' };
  if (value === 'sell_intent') return { key: 'exit_signal', label: '卖出' };
  return null;
}

function manualIntentStatusBadge(status, intentType, cancelReason) {
  const value = String(status || '').trim();
  if (value === 'pending') return { key: 'queue_pending', label: '待处理' };
  if (value === 'executed') return { key: 'queue_executed', label: '已处理' };
  if (value === 'cancelled' && String(cancelReason || '').trim() === 'abandoned') {
    return { key: 'queue_abandoned', label: '已放弃' };
  }
  if (value === 'cancelled') return { key: 'queue_cancelled', label: '已取消' };
  if (String(intentType || '').trim() === 'sell_intent') {
    return { key: 'exit_signal', label: value || '卖出' };
  }
  return null;
}

function SectorCard({ sector, snapshotMeta, onBuyIntent, onAbandon, posting, canPost }) {
  const market = snapshotMeta?.market_phase || null;
  const mode = snapshotMeta?.mode || null;

  const formatPercentile = (value01) => {
    if (typeof value01 !== 'number') return null;
    const p = Math.round(Math.max(0, Math.min(1, value01)) * 100);
    return `P${p}`;
  };

  const trendLabel = (trendState) => {
    const v = String(trendState || '').trim();
    if (!v) return null;
    if (v === 'rising') return '走强';
    if (v === 'falling') return '走弱';
    if (v === 'consolidating') return '整理';
    if (v === 'diverging') return '分化';
    return '未知';
  };

  const riskLabel = (riskLevel) => {
    const v = String(riskLevel || '').trim().toLowerCase();
    if (!v) return null;
    if (v === 'ok') return { key: 'risk_ok', label: '正常' };
    if (v === 'warn') return { key: 'risk_warn', label: '注意' };
    if (v === 'exit') return { key: 'not_qualified_avoid', label: '回避' };
    return null;
  };

  const stockStatus = (stock, roleLabel) => {
    const manual = stock?.manual || {};
    if (manual?.abandoned === true) {
      return { key: 'abandoned', label: '已放弃' };
    }
    if (manual?.buy_intent_pending === true) {
      return { key: 'entry_queued', label: '已排队' };
    }
    if (stock?.buy_signal === true) {
      return { key: 'entry_ready', label: '可出手' };
    }
    if (roleLabel === '跟随') {
      return { key: 'watch_follower', label: '跟随观察' };
    }
    const gate = stock?.upwave_gate || {};
    if (gate?.market_ok === false) {
      return { key: 'not_qualified_market', label: '大盘不配合' };
    }
    if (gate?.concept_ok === false) {
      return { key: 'not_qualified_concept', label: '题材不配合' };
    }
    if (gate?.stock_ok === false) {
      return { key: 'not_qualified_momentum', label: '动能不足' };
    }
    if (stock?.risk_level === 'exit') {
      return { key: 'not_qualified_avoid', label: '回避' };
    }
    return { key: 'watch_general', label: '观察' };
  };

  const upwavePill = (sec) => {
    const status = sec?.upwave?.status;
    if (status === 'upwave') return { text: '升浪支持', cls: 'bg-green-50 text-green-700 border-green-100' };
    if (status === 'not_upwave') return { text: '升浪不支持', cls: 'bg-gray-50 text-gray-700 border-gray-100' };
    return null;
  };

  const renderStock = (stock, roleLabel) => {
    const manual = stock?.manual || {};
    const abandoned = manual?.abandoned === true;
    const pending = manual?.buy_intent_pending === true;
    const executeDate = manual?.buy_execute_date || null;
    const status = stockStatus(stock, roleLabel);
    const scores = stock?.role_scores || {};
    const moneyRatio =
      typeof scores?.money_ratio === 'number' ? scores.money_ratio : null;
    const moneyRank = formatPercentile(scores?.money_rank);
    const capRank = formatPercentile(scores?.cap_rank);
    const ret5Rank = formatPercentile(scores?.return_5d_rank);
    const ret20Rank = formatPercentile(scores?.return_20d_rank);
    const buyDisabledReason =
      abandoned
        ? '已放弃'
        : pending
          ? '已排队'
          : roleLabel === '跟随'
            ? '跟随仅观察'
            : stock?.buy_signal !== true
              ? '未满足出手条件'
              : null;

    return (
      <div className="p-3 bg-white rounded-lg border border-gray-100">
        <div className="flex items-start justify-between gap-3 mb-1">
          <div>
            <div className="font-medium text-gray-900">{stock.name}</div>
            <div className="text-sm text-gray-500">
              <StockCodeLink code={stock.code} className="hover:text-blue-600 hover:underline">
                {stock.code || '--'}
              </StockCodeLink>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap justify-end">
            <span className="px-2 py-1 rounded bg-gray-50 text-gray-700 text-xs border border-gray-100">
              {roleLabel}
            </span>
            <SemanticBadge
              semanticKey={status.key}
              label={`${status.label}${pending && executeDate ? `(${executeDate})` : ''}`}
            />
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm flex-wrap">
          <span className="text-gray-600">
            5日:{' '}
            <span className={stock.return_5d > 0 ? 'text-red-600' : 'text-green-600'}>
              {stock.return_5d?.toFixed(2)}%
            </span>
          </span>
          {moneyRatio != null ? (
            <span className="text-gray-600">
              放量:{' '}
              <span className={moneyRatio >= 1.1 ? 'text-red-600' : 'text-gray-700'}>
                ×{moneyRatio.toFixed(2)}
              </span>
              {moneyRank ? <span className="text-gray-500">（{moneyRank}）</span> : null}
            </span>
          ) : null}
          {ret5Rank ? (
            <span className="text-gray-600">
              领涨:{' '}
              <span className="text-gray-700">{ret5Rank}</span>
            </span>
          ) : null}
          {capRank ? (
            <span className="text-gray-600">
              规模:{' '}
              <span className="text-gray-700">{capRank}</span>
            </span>
          ) : null}
          {ret20Rank ? (
            <span className="text-gray-600">
              趋势:{' '}
              <span className="text-gray-700">{ret20Rank}</span>
            </span>
          ) : null}
        </div>
        <div className="mt-2 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            {stock.buy_signal ? (
                <div className="inline-flex items-center gap-1">
                  <Target size={14} className="text-green-700" />
                  <SemanticBadge semanticKey="entry_ready" label="满足出手条件" />
                </div>
            ) : (
                <SemanticBadge
                  semanticKey={roleLabel === '跟随' ? 'watch_follower' : 'not_qualified_avoid'}
                  label={roleLabel === '跟随' ? '跟随仅观察' : '未满足出手条件'}
                />
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              disabled={!canPost || posting || !!buyDisabledReason}
              onClick={() =>
                onBuyIntent({
                  code: stock.code,
                  name: stock.name,
                  sector: stock.sector,
                  role: stock.role,
                  buy_score: stock.buy_score,
                })
              }
              title={buyDisabledReason || ''}
              className="px-3 py-1 rounded bg-green-600 text-white text-sm disabled:opacity-50"
            >
              买进(T+1)
            </button>
            <button
              disabled={!canPost || posting}
              onClick={() => onAbandon({ code: stock.code })}
              className="px-3 py-1 rounded bg-gray-100 text-gray-700 text-sm hover:bg-gray-200 disabled:opacity-50"
            >
              放弃
            </button>
          </div>
        </div>
      </div>
    );
  };

  const rp = riskLabel(sector?.meta?.risk_level);
  const tp = trendLabel(sector?.meta?.trend_state);
  const up = upwavePill(sector);
  const mainlineRank =
    typeof sector?.meta?.mainline_rank === 'number'
      ? `主线#${sector.meta.mainline_rank}`
      : null;
  const mainlineStreak =
    typeof sector?.meta?.mainline_streak === 'number'
      ? `持续${sector.meta.mainline_streak}`
      : null;
  const risingRatio =
    typeof sector?.upwave?.diffusion === 'number'
      ? Math.round(Math.max(0, Math.min(1, sector.upwave.diffusion)) * 100)
      : null;
  const leadAvg =
    typeof sector?.upwave?.avg_top3_return_5d === 'number'
      ? sector.upwave.avg_top3_return_5d
      : null;
  const moneyAvg =
    typeof sector?.upwave?.avg_top3_money_ratio === 'number'
      ? sector.upwave.avg_top3_money_ratio
      : null;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{sector.name}</h3>
          <p className="text-sm text-gray-500">{sector.code}</p>
          <div className="mt-2 flex items-center gap-2 flex-wrap text-xs">
            {mode === 'ths_concept' && mainlineRank ? (
              <span className="px-2 py-1 rounded border bg-gray-50 text-gray-700 border-gray-100">{mainlineRank}</span>
            ) : null}
            {mode === 'ths_concept' && mainlineStreak ? (
              <span className="px-2 py-1 rounded border bg-gray-50 text-gray-700 border-gray-100">{mainlineStreak}</span>
            ) : null}
            {tp ? (
              <span className="px-2 py-1 rounded border bg-gray-50 text-gray-700 border-gray-100">状态：{tp}</span>
            ) : null}
            {rp ? (
              <SemanticBadge semanticKey={rp.key} label={rp.label} />
            ) : null}
            {up ? (
              <span className={`px-2 py-1 rounded border ${up.cls}`}>{up.text}</span>
            ) : null}
          </div>
          {risingRatio != null || leadAvg != null || moneyAvg != null ? (
            <div className="mt-2 text-xs text-gray-500 flex items-center gap-3 flex-wrap">
              {risingRatio != null ? <span>上涨占比 {risingRatio}%</span> : null}
              {leadAvg != null ? <span>领涨均值 {leadAvg >= 0 ? '+' : ''}{leadAvg.toFixed(2)}%</span> : null}
              {moneyAvg != null ? <span>放量均值 ×{moneyAvg.toFixed(2)}</span> : null}
            </div>
          ) : null}
          {market?.phase ? (
            <div className="mt-2 text-xs text-gray-500">
              大盘环境：{String(market.phase || '').trim()}（置信 {typeof market.confidence === 'number' ? market.confidence.toFixed(2) : '--'}）
            </div>
          ) : null}
        </div>
        <div className="flex items-center gap-1 text-orange-500">
          <Flame size={18} />
          <span className="font-bold">{sector.heat_score?.toFixed(1) || '--'}</span>
        </div>
      </div>

      {/* Leaders */}
      {sector.leaders?.length > 0 && (
        <div className="mb-3">
          <div className="text-sm font-medium text-gray-700 mb-2">龙头股</div>
          <div className="space-y-2">
            {sector.leaders.map((stock, idx) => (
              <div key={idx}>{renderStock(stock, '龙头')}</div>
            ))}
          </div>
        </div>
      )}

      {/* Middle */}
      {sector.middle?.length > 0 && (
        <div className="mb-3">
          <div className="text-sm font-medium text-gray-700 mb-2">中军股</div>
          <div className="space-y-2">
            {sector.middle.map((stock, idx) => (
              <div key={idx}>{renderStock(stock, '中军')}</div>
            ))}
          </div>
        </div>
      )}

      {/* Followers */}
      {sector.followers?.length > 0 && (
        <div>
          <div className="text-sm font-medium text-gray-700 mb-2">跟随股</div>
          <div className="space-y-2">
            {sector.followers.map((stock, idx) => (
              <div key={idx}>{renderStock(stock, '跟随')}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PortfolioPanel({ data }) {
  // 数据来自 /api/sectors/hot 的 portfolio 字段
  const portfolio = data?.portfolio;
  
  if (!portfolio) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
        <Wallet size={48} className="mx-auto text-gray-300 mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">暂无交易数据</h3>
        <p className="text-gray-500">无法获取组合与交易信息</p>
      </div>
    );
  }
  
  const hasPositions = Array.isArray(portfolio.open_positions) && portfolio.open_positions.length > 0;
  const hasClosedTrades = Array.isArray(portfolio.closed_trades) && portfolio.closed_trades.length > 0;
  const hasManualIntents = Array.isArray(portfolio.manual_intents) && portfolio.manual_intents.length > 0;
  const totalReturnPct = safeNumber(portfolio.total_return_pct);
  const processBadge = (stage) => {
    const value = String(stage || '').trim();
    if (value === 'exit_signal') {
      return { label: '退出确认', cls: 'bg-red-50 text-red-700 border-red-100' };
    }
    if (value === 'exit_watch') {
      return { label: '退出观察', cls: 'bg-amber-50 text-amber-700 border-amber-100' };
    }
    if (value === 'closed') {
      return { label: '已退出', cls: 'bg-gray-50 text-gray-700 border-gray-100' };
    }
    return { label: '持有中', cls: 'bg-emerald-50 text-emerald-700 border-emerald-100' };
  };
  const entryStageText = (item) => {
    const parts = [];
    if (String(item?.buy_progress_label || '').trim()) parts.push(String(item.buy_progress_label).trim());
    if (String(item?.wave_phase || '').trim()) parts.push(String(item.wave_phase).trim());
    return parts.length > 0 ? parts.join(' / ') : '--';
  };
  const warningSummary = (item) => {
    const parts = [];
    if (String(item?.market_exit_state || '').trim()) {
      parts.push(`大盘${String(item.market_exit_state).trim()}(${Number(item.market_exit_hits || 0)})`);
    }
    if (String(item?.sector_exit_state || '').trim()) {
      parts.push(`板块${String(item.sector_exit_state).trim()}(${Number(item.sector_exit_hits || 0)})`);
    }
    return parts.length > 0 ? parts.join(' | ') : '--';
  };
  const graceSummary = (item) => {
    if (!item?.system_exit_grace_used) return null;
    const scope = String(item.system_exit_grace_scope || '').trim();
    const date = String(item.system_exit_grace_date || '').trim();
    return `grace${scope ? `:${scope}` : ''}${date ? ` @ ${date}` : ''}`;
  };
  const timelineItems = [
    ...(Array.isArray(portfolio.open_positions)
      ? portfolio.open_positions.map((pos) => ({
          kind: 'open',
          eventDate: pos.buy_date || '',
          code: pos.code,
          name: pos.name,
          sector: pos.sector,
          buyDate: pos.buy_date,
          holdDays: pos.hold_days,
          entryStage: entryStageText(pos),
          processStage: processBadge(pos.process_stage),
          returnText: formatPercent(pos.unrealized_pnl_pct, { signed: true }),
          returnClass: signedNumberClass(pos.unrealized_pnl_pct),
          peakText: formatPercent(pos.peak_return_pct),
          holdText: warningSummary(pos),
          exitText: displayText(pos.sell_reason || pos.sector_exit_last_reason || pos.market_exit_last_reason),
          graceText: graceSummary(pos),
        }))
      : []),
    ...(Array.isArray(portfolio.closed_trades)
      ? portfolio.closed_trades.slice(0, 20).map((trade) => ({
          kind: 'closed',
          eventDate: trade.sell_date || trade.buy_date || '',
          code: trade.code,
          name: trade.name,
          sector: trade.sector,
          buyDate: trade.buy_date,
          holdDays: trade.hold_days,
          entryStage: entryStageText(trade),
          processStage: processBadge(trade.process_stage),
          returnText: formatPercent(trade.return_pct, { signed: true }),
          returnClass: signedNumberClass(trade.return_pct),
          peakText: formatPercent(trade.peak_return_pct),
          holdText: `${displayText(trade.sell_date)} 卖出`,
          exitText: displayText(trade.sell_reason),
          graceText: graceSummary(trade),
        }))
      : []),
  ].sort((a, b) => String(b.eventDate || '').localeCompare(String(a.eventDate || '')));
  
  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">总资产</div>
          <div className="text-2xl font-bold text-gray-900">{formatAmountWan(portfolio.total_value)}</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">现金</div>
          <div className="text-2xl font-bold text-blue-600">{formatAmountWan(portfolio.cash)}</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">当前组合累计收益</div>
          <div className={`text-2xl font-bold ${signedNumberClass(totalReturnPct)}`}>
            {formatPercent(totalReturnPct, { signed: true })}
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">持仓数</div>
          <div className="text-2xl font-bold text-gray-900">{portfolio.open_positions?.length || 0}</div>
        </div>
      </div>

      {/* Strategy Info */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">策略: <span className="text-gray-900 font-medium">{displayText(portfolio.strategy)}</span></span>
          <span className="text-gray-500">数据日期: <span className="text-gray-900">{displayText(portfolio.as_of)}</span></span>
          <span className="text-gray-500">初始资金: <span className="text-gray-900">{formatAmountWan(portfolio.initial_capital)}</span></span>
        </div>
      </div>

      {timelineItems.length > 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Calendar size={20} />
            捕捉 / 持有 / 退出全过程
          </h3>
          <div className="space-y-3">
            {timelineItems.slice(0, 24).map((item) => (
              <div key={`${item.kind}-${item.code}-${item.eventDate}`} className="rounded-lg border border-gray-100 p-4">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <div className="font-medium text-gray-900">{displayText(item.name)}</div>
                      <StockCodeLink code={item.code} className="text-sm text-gray-500 hover:text-blue-600 hover:underline">
                        {item.code || '--'}
                      </StockCodeLink>
                      <span className="text-xs text-gray-400">{displayText(item.sector)}</span>
                    </div>
                    <div className="mt-2 text-sm text-gray-600 flex items-center gap-3 flex-wrap">
                      <span>捕捉: {displayText(item.buyDate)}</span>
                      <span>阶段: {item.entryStage}</span>
                      <span>持有: {displayText(item.holdDays)}天</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`px-2 py-1 rounded border text-xs ${item.processStage.cls}`}>{item.processStage.label}</span>
                    {item.graceText ? (
                      <span className="px-2 py-1 rounded border text-xs bg-blue-50 text-blue-700 border-blue-100">
                        {item.graceText}
                      </span>
                    ) : null}
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                  <div className="rounded bg-gray-50 px-3 py-2">
                    <div className="text-xs text-gray-500 mb-1">持有表现</div>
                    <div className={item.returnClass}>{item.returnText}</div>
                    <div className="text-gray-500">峰值: {item.peakText}</div>
                  </div>
                  <div className="rounded bg-gray-50 px-3 py-2">
                    <div className="text-xs text-gray-500 mb-1">预警进度</div>
                    <div className="text-gray-700">{item.holdText}</div>
                  </div>
                  <div className="rounded bg-gray-50 px-3 py-2">
                    <div className="text-xs text-gray-500 mb-1">退出结果</div>
                    <div className="text-gray-700">{item.exitText}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Positions Table */}
      {hasPositions ? (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Wallet size={20} />
            持仓明细
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">代码</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">名称</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">板块</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">状态</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">进场阶段</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">买入价</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">现价</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">峰值收益</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">市值</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">盈亏</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">过程</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.open_positions.map((pos, index) => (
                  <tr key={index} className="border-b border-gray-100">
                    <td className="py-3 px-4 text-gray-900">
                      <StockCodeLink code={pos.code} className="hover:text-blue-600 hover:underline">
                        {pos.code || '--'}
                      </StockCodeLink>
                    </td>
                    <td className="py-3 px-4 text-gray-900">{displayText(pos.name)}</td>
                    <td className="py-3 px-4 text-gray-500">{displayText(pos.sector)}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded border text-xs ${processBadge(pos.process_stage).cls}`}>
                        {processBadge(pos.process_stage).label}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-700">{entryStageText(pos)}</td>
                    <td className="py-3 px-4 text-gray-900">{formatCurrency(pos.buy_price)}</td>
                    <td className="py-3 px-4 text-gray-900">{formatCurrency(pos.current_price)}</td>
                    <td className="py-3 px-4 text-gray-900">{formatPercent(pos.peak_return_pct)}</td>
                    <td className="py-3 px-4 text-gray-900">{formatAmountWan(pos.market_value)}</td>
                    <td className="py-3 px-4">
                      <span className={`${signedNumberClass(safeNumber(pos.unrealized_pnl ?? pos.unrealized_pnl_pct))}`}>
                        {formatPercent(pos.unrealized_pnl_pct, { signed: true })}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-500">
                      <div>{warningSummary(pos)}</div>
                      {graceSummary(pos) ? <div className="text-blue-600">{graceSummary(pos)}</div> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <Wallet size={48} className="mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">当前无持仓</h3>
          <p className="text-gray-500">投资组合中暂无持仓股票</p>
        </div>
      )}

      {hasClosedTrades ? (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <FileText size={20} />
            交易记录
            <span className={`ml-2 text-sm ${Number(portfolio.realized_pnl_total || 0) >= 0 ? 'text-red-600' : 'text-green-600'}`}>
              累计已实现{Number(portfolio.realized_pnl_total || 0) >= 0 ? '+' : ''}¥{Number(portfolio.realized_pnl_total || 0).toFixed(2)}
            </span>
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">卖出日</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">代码</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">名称</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">买入日</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">进场阶段</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">数量</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">买入价</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">卖出价</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">峰值收益</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">收益</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">退出过程</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.closed_trades.map((t, index) => (
                  <tr key={index} className="border-b border-gray-100">
                    <td className="py-3 px-4 text-gray-900">{t.sell_date || '--'}</td>
                    <td className="py-3 px-4 text-gray-900">
                      <StockCodeLink code={t.code} className="hover:text-blue-600 hover:underline">
                        {t.code || '--'}
                      </StockCodeLink>
                    </td>
                    <td className="py-3 px-4 text-gray-900">{displayText(t.name)}</td>
                    <td className="py-3 px-4 text-gray-500">{displayText(t.buy_date)}</td>
                    <td className="py-3 px-4 text-gray-700">{entryStageText(t)}</td>
                    <td className="py-3 px-4 text-gray-900">{displayText(t.shares)}</td>
                    <td className="py-3 px-4 text-gray-900">{formatCurrency(t.buy_price)}</td>
                    <td className="py-3 px-4 text-gray-900">{formatCurrency(t.sell_price)}</td>
                    <td className="py-3 px-4 text-gray-900">{formatPercent(t.peak_return_pct)}</td>
                    <td className="py-3 px-4">
                      <span className={`${signedNumberClass(t.realized_pnl)}`}>
                        {`${formatCurrency(t.realized_pnl)} (${formatPercent(t.return_pct)})`}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-500">
                      <div>{displayText(t.sell_reason)}</div>
                      {graceSummary(t) ? <div className="text-blue-600">{graceSummary(t)}</div> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {hasManualIntents ? (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <ListFilter size={20} />
            人工干预记录
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">时间</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">类型</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">代码</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">名称</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">请求日</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">状态</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.manual_intents.slice(-30).reverse().map((it, idx) => (
                  <tr key={idx} className="border-b border-gray-100">
                    <td className="py-3 px-4 text-gray-900">{displayText(it.created_at || it.executed_at || it.cancelled_at)}</td>
                    <td className="py-3 px-4 text-gray-900">
                      {manualIntentTypeBadge(it.intent_type) ? (
                        <SemanticBadge
                          semanticKey={manualIntentTypeBadge(it.intent_type).key}
                          label={manualIntentTypeBadge(it.intent_type).label}
                        />
                      ) : (
                        it.intent_type || '--'
                      )}
                    </td>
                    <td className="py-3 px-4 text-gray-900">
                      <StockCodeLink code={it.code} className="hover:text-blue-600 hover:underline">
                        {it.code || '--'}
                      </StockCodeLink>
                    </td>
                    <td className="py-3 px-4 text-gray-900">{displayText(it.name)}</td>
                    <td className="py-3 px-4 text-gray-500">{displayText(it.requested_date)}</td>
                    <td className="py-3 px-4 text-gray-500">
                      {manualIntentStatusBadge(it.status, it.intent_type, it.cancel_reason) ? (
                        <SemanticBadge
                          semanticKey={manualIntentStatusBadge(it.status, it.intent_type, it.cancel_reason).key}
                          label={manualIntentStatusBadge(it.status, it.intent_type, it.cancel_reason).label}
                        />
                      ) : (
                        it.status || '--'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function CandidatesPanel({ data, onBuyIntent, onAbandon, posting }) {
  if (!data?.candidates || data.candidates.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
        <ListFilter size={48} className="mx-auto text-gray-300 mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">暂无候选股</h3>
        <p className="text-gray-500">当前没有符合条件的候选股票</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <ListFilter size={20} />
        候选池 ({data.candidates.length})
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">代码</th>
              <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">名称</th>
              <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">板块</th>
              <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">角色</th>
              <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">状态</th>
              <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">买入分</th>
              <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">5日涨幅</th>
              <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">操作</th>
            </tr>
          </thead>
          <tbody>
            {data.candidates.map((candidate, index) => (
              <tr key={index} className="border-b border-gray-100">
                <td className="py-3 px-4 text-gray-900">
                  <StockCodeLink code={candidate.code} className="hover:text-blue-600 hover:underline">
                    {candidate.code || '--'}
                  </StockCodeLink>
                </td>
                <td className="py-3 px-4 text-gray-900">{candidate.name}</td>
                <td className="py-3 px-4 text-gray-500">{candidate.sector}</td>
                <td className="py-3 px-4 text-gray-500">{candidate.role || '--'}</td>
                <td className="py-3 px-4">
                  {candidate.manual?.abandoned ? (
                    <SemanticBadge semanticKey="abandoned" label="已放弃" />
                  ) : candidate.manual?.buy_intent_pending ? (
                    <SemanticBadge semanticKey="entry_queued" label="已排队" />
                  ) : candidate.buy_signal ? (
                    <SemanticBadge semanticKey="entry_ready" label="可出手" />
                  ) : (
                    <SemanticBadge semanticKey="watch_general" label="观察" />
                  )}
                </td>
                <td className="py-3 px-4 text-gray-900">{candidate.buy_score?.toFixed(0)}</td>
                <td className="py-3 px-4">
                  <span className={candidate.return_5d >= 0 ? 'text-red-600' : 'text-green-600'}>
                    {candidate.return_5d >= 0 ? '+' : ''}{candidate.return_5d?.toFixed(2)}%
                  </span>
                </td>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    {candidate.manual?.abandoned ? (
                      <span className="text-sm text-gray-500">已放弃</span>
                    ) : candidate.manual?.buy_intent_pending ? (
                      <span className="text-sm text-blue-600">已排队({candidate.manual?.buy_execute_date || 'T+1'})</span>
                    ) : (
                      <>
                        <button
                          onClick={() => onBuyIntent(candidate)}
                          disabled={posting || candidate.buy_signal !== true || candidate.role === '跟随'}
                          title={
                            candidate.role === '跟随'
                              ? '跟随仅观察'
                              : candidate.buy_signal !== true
                                ? '未满足出手条件'
                                : ''
                          }
                          className="px-3 py-1 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
                        >
                          买进(T+1)
                        </button>
                        <button
                          onClick={() => onAbandon(candidate)}
                          disabled={posting}
                          className="px-3 py-1 rounded bg-gray-100 text-gray-700 text-sm hover:bg-gray-200 disabled:opacity-50"
                        >
                          放弃
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BacktestPanel({ result, startDate, endDate, setStartDate, setEndDate, onRun, running, reports }) {
  const summary = result?.summary;
  const metaStatus = result?._meta?.status;
  const pendingMessage =
    metaStatus === 'accepted'
      ? String(result?.message || '已提交后台运行，报告生成中').trim()
      : '';
  const jobStatus = result?.job?.status;

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <FileText size={20} />
            回测报告
          </h3>
          <div className="flex items-center gap-3 flex-wrap">
            <input
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              placeholder="start_date (YYYY-MM-DD，可选)"
              className="px-3 py-2 border border-gray-200 rounded text-sm w-56"
            />
            <input
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              placeholder="end_date (YYYY-MM-DD，可选)"
              className="px-3 py-2 border border-gray-200 rounded text-sm w-56"
            />
            <button
              onClick={onRun}
              disabled={running || metaStatus === 'accepted' || jobStatus === 'running'}
              className="px-4 py-2 bg-blue-600 text-white rounded text-sm disabled:opacity-50"
            >
              {running || metaStatus === 'accepted' || jobStatus === 'running' ? '运行中...' : '运行回测'}
            </button>
          </div>
        </div>
        {pendingMessage ? (
          <div className="mt-4 text-sm text-blue-700 bg-blue-50 border border-blue-100 rounded px-3 py-2">
            {pendingMessage}（建议稍后再点击下载链接）
          </div>
        ) : null}
        {result?.pdf_url && (
          <div className="mt-4 flex items-center gap-3 text-sm">
            <a className="text-blue-600 hover:underline" href={result.pdf_url} target="_blank" rel="noreferrer">
              下载 PDF
            </a>
            <a className="text-blue-600 hover:underline" href={result.json_url} target="_blank" rel="noreferrer">
              下载 JSON
            </a>
            <span className="text-gray-500">report_id: {result.report_id}</span>
          </div>
        )}
      </div>

      {(metaStatus === 'accepted' || jobStatus === 'running') && (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <FileText size={48} className="mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">回测运行中</h3>
          <p className="text-gray-500">可切换板块，后台会继续生成报告</p>
          {result?.report_id ? (
            <div className="mt-3 text-sm text-gray-500">report_id: {result.report_id}</div>
          ) : null}
        </div>
      )}

      {!summary && metaStatus !== 'accepted' && jobStatus !== 'running' && (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <FileText size={48} className="mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">暂无回测结果</h3>
          <p className="text-gray-500">点击“运行回测”生成报告</p>
        </div>
      )}

      {/* Summary */}
      {summary && (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">回测总收益</div>
          <div className={`text-2xl font-bold ${summary.total_return_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
            {summary.total_return_pct >= 0 ? '+' : ''}{summary.total_return_pct?.toFixed(2)}%
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">年化收益</div>
          <div className={`text-2xl font-bold ${summary.annualized_return_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
            {summary.annualized_return_pct >= 0 ? '+' : ''}{summary.annualized_return_pct?.toFixed(2)}%
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">最大回撤</div>
          <div className="text-2xl font-bold text-green-600">
            {summary.max_drawdown_pct?.toFixed(2)}%
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">夏普比率</div>
          <div className="text-2xl font-bold text-gray-900">{summary.sharpe_ratio?.toFixed(2)}</div>
        </div>
      </div>
      )}

      {/* Trades */}
      {result?.buy_dates?.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">买点分布</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">买入日期</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">次数</th>
                </tr>
              </thead>
              <tbody>
                {result.buy_dates.map((row, index) => (
                  <tr key={index} className="border-b border-gray-100">
                    <td className="py-3 px-4 text-gray-900">{row.buy_date}</td>
                    <td className="py-3 px-4 text-gray-500">{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">最近 10 次回测报告</h3>
        {Array.isArray(reports) && reports.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">起始</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">结束</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">回测总收益</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">下载</th>
                </tr>
              </thead>
              <tbody>
                {reports.slice(0, 10).map((r) => (
                  <tr key={r.report_id} className="border-b border-gray-100">
                    <td className="py-3 px-4 text-gray-900">{r.start_date || '--'}</td>
                    <td className="py-3 px-4 text-gray-900">{r.end_date || '--'}</td>
                    <td className="py-3 px-4">
                      {typeof r?.summary?.total_return_pct === 'number' ? (
                        <span className={r.summary.total_return_pct >= 0 ? 'text-red-600' : 'text-green-600'}>
                          {r.summary.total_return_pct >= 0 ? '+' : ''}
                          {r.summary.total_return_pct.toFixed(2)}%
                        </span>
                      ) : (
                        <span className="text-gray-500">--</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <a className="text-blue-600 hover:underline" href={r.pdf_url} target="_blank" rel="noreferrer">
                        PDF
                      </a>
                      <span className="text-gray-300 mx-2">|</span>
                      <a className="text-blue-600 hover:underline" href={r.json_url} target="_blank" rel="noreferrer">
                        JSON
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-gray-500">暂无可下载报告</div>
        )}
      </div>
    </div>
  );
}

export default function Lowfreq() {
  const { selectedDate } = useApp();
  const [activeTab, setActiveTab] = useState('today');
  const [hotMode, setHotMode] = useState('ths_concept');
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState(null);
  const [backtestReports, setBacktestReports] = useState([]);
  const [backtestStartDate, setBacktestStartDate] = useState('');
  const [backtestEndDate, setBacktestEndDate] = useState('');
  const [backtestResult, setBacktestResult] = useState(null);
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [data, setData] = useState({
    marketPhase: null,
    hotSectors: null,
    portfolio: null,
    candidates: null,
    backtest: null,
  });
  const [blocks, setBlocks] = useState({
    marketPhase: createBlockState(),
    hotSectors: createBlockState(),
    portfolio: createBlockState(),
    candidates: createBlockState(),
    reports: createBlockState([]),
  });

  const formatPercentOrFallback = (value, digits = 2) => {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      return '--';
    }
    return `${(value * 100).toFixed(digits)}%`;
  };

  const buildCandidatesFromHotSectors = useCallback((payload) => {
    const sectors = payload?.sectors || [];
    const map = new Map();
    for (const sec of sectors) {
      const all = []
        .concat(sec.leaders || [])
        .concat(sec.middle || [])
        .concat(sec.followers || []);
      for (const s of all) {
        if (!s?.code) continue;
        if (!map.has(s.code)) {
          map.set(s.code, {
            code: s.code,
            name: s.name,
            sector: s.sector,
            buy_score: s.buy_score,
            certainty: s.certainty,
            return_5d: s.return_5d,
            role: s.role,
            buy_signal: !!s.buy_signal,
            upwave_gate: s.upwave_gate,
            role_scores: s.role_scores,
            risk_level: s.risk_level,
            reasons: s.reasons,
            manual: s.manual,
          });
        }
      }
    }
    const list = Array.from(map.values());
    list.sort((a, b) => (b.buy_score || 0) - (a.buy_score || 0));
    return list;
  }, []);

  const loadMarketPhaseBlock = useCallback(async () => {
    setBlocks((prev) => ({ ...prev, marketPhase: startBlock(prev.marketPhase, true) }));
    try {
      const payload = await fetchApi(`/api/market-phase?date=${encodeURIComponent(selectedDate)}`, {}, { timeoutMs: 45000 });
      setData((prev) => ({ ...prev, marketPhase: payload }));
      setBlocks((prev) => ({ ...prev, marketPhase: resolveBlock(payload) }));
    } catch (err) {
      setBlocks((prev) => ({ ...prev, marketPhase: rejectBlock(prev.marketPhase, err, true) }));
    }
  }, [selectedDate]);

  const loadHotSectorsBlock = useCallback(async () => {
    setBlocks((prev) => ({ ...prev, hotSectors: startBlock(prev.hotSectors, true) }));
    try {
      const payload = await fetchApi(
        `/api/sectors/hot?date=${encodeURIComponent(
          selectedDate
        )}&mode=${encodeURIComponent(hotMode)}&include_portfolio=0&include_sell_signal=0`,
        {},
        { timeoutMs: 45000 }
      );
      setData((prev) => ({ ...prev, hotSectors: payload }));
      setBlocks((prev) => ({ ...prev, hotSectors: resolveBlock(payload) }));
    } catch (err) {
      setBlocks((prev) => ({ ...prev, hotSectors: rejectBlock(prev.hotSectors, err, true) }));
    }
  }, [hotMode, selectedDate]);

  const loadPortfolioBlock = useCallback(async () => {
    setBlocks((prev) => ({ ...prev, portfolio: startBlock(prev.portfolio, true) }));
    try {
      const payload = await fetchApi(`/api/lowfreq/portfolio?date=${encodeURIComponent(selectedDate)}`, {}, { timeoutMs: 45000 });
      setData((prev) => ({ ...prev, portfolio: payload }));
      setBlocks((prev) => ({ ...prev, portfolio: resolveBlock(payload) }));
    } catch (err) {
      setBlocks((prev) => ({ ...prev, portfolio: rejectBlock(prev.portfolio, err, true) }));
    }
  }, [selectedDate]);

  const loadCandidatesBlock = useCallback(async () => {
    setBlocks((prev) => ({ ...prev, candidates: startBlock(prev.candidates, true) }));
    try {
      const payload = await fetchApi(
        `/api/sectors/hot?date=${encodeURIComponent(
          selectedDate
        )}&mode=${encodeURIComponent(hotMode)}&include_portfolio=0&include_sell_signal=0`,
        {},
        { timeoutMs: 45000 }
      );
      const candidates = buildCandidatesFromHotSectors(payload);
      setData((prev) => ({ ...prev, candidates }));
      setBlocks((prev) => ({ ...prev, candidates: resolveBlock(candidates) }));
    } catch (err) {
      setBlocks((prev) => ({ ...prev, candidates: rejectBlock(prev.candidates, err, true) }));
    }
  }, [buildCandidatesFromHotSectors, hotMode, selectedDate]);

  const fetchData = useCallback(async () => {
    setError(null);
    if (activeTab === 'today') {
      void loadMarketPhaseBlock();
      void loadHotSectorsBlock();
    } else if (activeTab === 'portfolio') {
      void loadPortfolioBlock();
    } else if (activeTab === 'candidates') {
      void loadCandidatesBlock();
    } else if (activeTab === 'backtest') {
      setData((prev) => ({ ...prev, backtest: null }));
    }
  }, [activeTab, loadCandidatesBlock, loadHotSectorsBlock, loadMarketPhaseBlock, loadPortfolioBlock]);

  const fetchBacktestReports = useCallback(async () => {
    setBlocks((prev) => ({ ...prev, reports: startBlock(prev.reports, true) }));
    try {
      const payload = await fetchApi('/api/lowfreq/backtest/reports?limit=10', {}, { timeoutMs: 60000 });
      if (Array.isArray(payload?.reports)) {
        setBacktestReports(payload.reports);
        setBlocks((prev) => ({ ...prev, reports: resolveBlock(payload.reports) }));
      } else {
        setBacktestReports([]);
        setBlocks((prev) => ({ ...prev, reports: resolveBlock([]) }));
      }
    } catch (err) {
      setBlocks((prev) => ({ ...prev, reports: rejectBlock(prev.reports, err, true) }));
    }
  }, []);

  useEffect(() => {
    fetchData();
    if (activeTab === 'backtest') {
      fetchBacktestReports();
    }
  }, [activeTab, fetchBacktestReports, fetchData]);

  useEffect(() => {
    if (!backtestEndDate) {
      setBacktestEndDate(selectedDate);
    }
  }, [selectedDate, backtestEndDate]);

  const postJson = async (url, payload) => {
    return fetchApi(url, { method: 'POST', body: JSON.stringify(payload) }, { timeoutMs: 30000 });
  };

  const handleBuyIntent = async (candidate) => {
    setPosting(true);
    setError(null);
    try {
      await postJson('/api/lowfreq/manual/buy-intent', {
        code: candidate.code,
        name: candidate.name,
        sector: candidate.sector,
        role: candidate.role,
        buy_score: candidate.buy_score,
        requested_date: selectedDate,
        requested_by: 'dashboard.react',
      });
      await fetchData();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setPosting(false);
    }
  };

  const handleAbandon = async (candidate) => {
    setPosting(true);
    setError(null);
    try {
      await postJson('/api/lowfreq/manual/abandon', {
        code: candidate.code,
        requested_date: selectedDate,
        requested_by: 'dashboard.react',
      });
      await fetchData();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setPosting(false);
    }
  };

  const runBacktest = async () => {
    setBacktestRunning(true);
    setError(null);
    try {
      const res = await postJson('/api/lowfreq/backtest/run', {
        start_date: backtestStartDate.trim() || null,
        end_date: backtestEndDate.trim() || null,
        requested_by: 'dashboard.react',
      });
      setBacktestResult(res);
      if (res?.report_id) {
        localStorage.setItem('neotrade3_last_backtest_report_id', String(res.report_id));
      }
      fetchBacktestReports();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setBacktestRunning(false);
    }
  };

  useEffect(() => {
    if (activeTab !== 'backtest') {
      return;
    }
    const reportId =
      backtestResult?.report_id ||
      localStorage.getItem('neotrade3_last_backtest_report_id');
    if (!reportId) {
      return;
    }
    let cancelled = false;
    let timer = null;

    const tick = async () => {
      try {
        const payload = await fetchApi(
          `/api/lowfreq/backtest/status?report_id=${encodeURIComponent(reportId)}`,
          {},
          { timeoutMs: 8000 }
        );
        if (cancelled) {
          return;
        }
        const job = payload?.job;
        const jobStatus = job?.status;
        setBacktestResult((prev) => {
          const merged = {
            ...(prev || {}),
            report_id: reportId,
            job,
            pdf_url: payload?.pdf_url || prev?.pdf_url,
            json_url: payload?.json_url || prev?.json_url,
          };
          if (jobStatus === 'done') {
            merged._meta = { ...(merged._meta || {}), status: 'ok' };
          } else if (jobStatus === 'failed') {
            merged._meta = { ...(merged._meta || {}), status: 'error' };
          } else {
            merged._meta = { ...(merged._meta || {}), status: 'accepted' };
          }
          return merged;
        });
        if (jobStatus === 'done' || jobStatus === 'failed') {
          fetchBacktestReports();
        }
      } catch {
        return;
      }
    };

    tick();
    timer = window.setInterval(tick, 2000);
    return () => {
      cancelled = true;
      if (timer) {
        window.clearInterval(timer);
      }
    };
  }, [activeTab, backtestResult?.report_id, fetchBacktestReports]);

  const tabs = [
    { id: 'today', label: '今日快照', icon: Calendar },
    { id: 'portfolio', label: '交易记录', icon: Wallet },
    { id: 'candidates', label: '候选池', icon: ListFilter },
    { id: 'backtest', label: '回测报告', icon: FileText },
  ];
  const loading =
    activeTab === 'today'
      ? blocks.marketPhase.loading || blocks.hotSectors.loading
      : activeTab === 'portfolio'
      ? blocks.portfolio.loading
      : activeTab === 'candidates'
      ? blocks.candidates.loading
      : activeTab === 'backtest'
      ? blocks.reports.loading
      : false;

  return (
    <div className="space-y-6">
      {/* Date Selector */}
      <DateSelector onRefresh={fetchData} loading={loading} />

      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">低频交易</h2>
        <p className="text-gray-500 mt-1">预判未来20-60个交易日有80%+机会涨幅达到30%以上的股票</p>
      </div>

      {(activeTab === 'today' || activeTab === 'candidates' || activeTab === 'backtest') && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-sm text-gray-500">操作提示：买入/放弃/回测无需再输入 API Key（本机访问默认放行）</div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-6">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                <Icon size={18} />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3 text-red-700">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {/* Loading */}
      {loading && activeTab !== 'today' && (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={32} className="animate-spin text-blue-600" />
        </div>
      )}

      {/* Tab Content */}
      {activeTab === 'today' && (
        <div className="space-y-6">
          {/* Market Phase */}
          {blocks.marketPhase.loading && !blocks.marketPhase.loaded ? (
            <BlockMessage message="市场阶段加载中..." />
          ) : blocks.marketPhase.error && !blocks.marketPhase.loaded ? (
            <BlockMessage tone="red" message={blocks.marketPhase.error} onRetry={loadMarketPhaseBlock} />
          ) : data.marketPhase?.market_phase ? (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">市场阶段</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm text-gray-500">当前阶段</div>
                  <div className="text-xl font-bold text-gray-900 capitalize">{data.marketPhase.market_phase.phase}</div>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm text-gray-500">市场宽度</div>
                  <div className="text-xl font-bold text-gray-900">
                    {formatPercentOrFallback(data.marketPhase.market_phase.market_breadth, 0)}
                  </div>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm text-gray-500">市场近20日涨跌</div>
                  <div className={`text-xl font-bold ${data.marketPhase.market_phase.market_return_20d > 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {formatPercentOrFallback(data.marketPhase.market_phase.market_return_20d, 2)}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">市场环境指标，非策略收益</div>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm text-gray-500">成交量趋势</div>
                  <div className="text-xl font-bold text-gray-900 capitalize">{data.marketPhase.market_phase.amount_trend}</div>
                </div>
              </div>
            </div>
          ) : null}

          {/* Hot Sectors */}
          <div>
            <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
              <h3 className="text-lg font-semibold text-gray-900">热门板块</h3>
              <div className="flex items-center gap-2 text-sm">
                <button
                  onClick={() => setHotMode('ths_concept')}
                  className={`px-3 py-1 rounded border ${
                    hotMode === 'ths_concept'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-200'
                  }`}
                >
                  同花顺概念
                </button>
                <button
                  onClick={() => setHotMode('team_theme')}
                  className={`px-3 py-1 rounded border ${
                    hotMode === 'team_theme'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-200'
                  }`}
                >
                  团队主题
                </button>
                <button
                  onClick={() => setHotMode('industry')}
                  className={`px-3 py-1 rounded border ${
                    hotMode === 'industry'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-200'
                  }`}
                >
                  行业
                </button>
              </div>
            </div>
            {blocks.hotSectors.loading && !blocks.hotSectors.loaded ? (
              <BlockMessage message="热门板块加载中..." />
            ) : blocks.hotSectors.error && !blocks.hotSectors.loaded ? (
              <BlockMessage tone="red" message={blocks.hotSectors.error} onRetry={loadHotSectorsBlock} />
            ) : data.hotSectors?._meta?.status === 'error' ? (
              <div className="bg-white rounded-lg border border-gray-200 p-6 text-sm text-gray-700">
                {data.hotSectors?._meta?.message || '热门板块数据不可用'}
              </div>
            ) : null}
            {!blocks.hotSectors.loading && !blocks.hotSectors.error ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {data.hotSectors?.sectors?.map((sector, index) => (
                  <SectorCard
                    key={index}
                    sector={sector}
                    snapshotMeta={data.hotSectors?._meta}
                    onBuyIntent={handleBuyIntent}
                    onAbandon={handleAbandon}
                    posting={posting}
                    canPost={true}
                  />
                ))}
              </div>
            ) : null}
            {!data.hotSectors?.sectors?.length && !blocks.hotSectors.loading && !blocks.hotSectors.error && (
              <div className="text-center py-12 text-gray-500">
                暂无热门板块数据
              </div>
            )}
          </div>
        </div>
      )}

      {!loading && activeTab === 'portfolio' && (
        <>
          {blocks.portfolio.error && !blocks.portfolio.loaded ? (
            <BlockMessage tone="red" message={blocks.portfolio.error} onRetry={loadPortfolioBlock} />
          ) : (
            <PortfolioPanel data={data.portfolio} />
          )}
        </>
      )}

      {!loading && activeTab === 'candidates' && (
        <>
          {blocks.candidates.error && !blocks.candidates.loaded ? (
            <BlockMessage tone="red" message={blocks.candidates.error} onRetry={loadCandidatesBlock} />
          ) : (
            <CandidatesPanel
              data={{ candidates: data.candidates || [] }}
              onBuyIntent={handleBuyIntent}
              onAbandon={handleAbandon}
              posting={posting}
            />
          )}
        </>
      )}

      {!loading && activeTab === 'backtest' && (
        <div className="space-y-4">
          {blocks.reports.error && !blocks.reports.loaded ? (
            <BlockMessage tone="red" message={blocks.reports.error} onRetry={fetchBacktestReports} />
          ) : null}
          <BacktestPanel
            result={backtestResult}
            startDate={backtestStartDate}
            endDate={backtestEndDate}
            setStartDate={setBacktestStartDate}
            setEndDate={setBacktestEndDate}
            onRun={runBacktest}
            running={backtestRunning}
            reports={backtestReports}
          />
        </div>
      )}
    </div>
  );
}
