import { useEffect, useState } from 'react';
import { TrendingUp, Flame, Target, Calendar, Download, AlertCircle, Loader2, Wallet, ListFilter, FileText } from 'lucide-react';
import { useApp } from '../context/AppContext';
import DateSelector from '../components/DateSelector';

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
    const v = String(riskLevel || '').trim();
    if (!v) return null;
    if (v === 'ok') return { text: '正常', cls: 'bg-green-50 text-green-700 border-green-100' };
    if (v === 'warn') return { text: '注意', cls: 'bg-orange-50 text-orange-700 border-orange-100' };
    if (v === 'exit') return { text: '回避', cls: 'bg-red-50 text-red-700 border-red-100' };
    return { text: v, cls: 'bg-gray-50 text-gray-700 border-gray-100' };
  };

  const stockStatus = (stock, roleLabel) => {
    const manual = stock?.manual || {};
    if (manual?.abandoned === true) {
      return { text: '已放弃', cls: 'bg-gray-100 text-gray-700 border-gray-200' };
    }
    if (manual?.buy_intent_pending === true) {
      return { text: '已排队', cls: 'bg-blue-50 text-blue-700 border-blue-100' };
    }
    if (stock?.buy_signal === true) {
      return { text: '可出手', cls: 'bg-green-50 text-green-700 border-green-100' };
    }
    if (roleLabel === '跟随') {
      return { text: '跟随观察', cls: 'bg-gray-50 text-gray-700 border-gray-100' };
    }
    const gate = stock?.upwave_gate || {};
    if (gate?.market_ok === false) {
      return { text: '大盘不配合', cls: 'bg-gray-50 text-gray-700 border-gray-100' };
    }
    if (gate?.concept_ok === false) {
      return { text: '题材不配合', cls: 'bg-gray-50 text-gray-700 border-gray-100' };
    }
    if (gate?.stock_ok === false) {
      return { text: '动能不足', cls: 'bg-gray-50 text-gray-700 border-gray-100' };
    }
    if (stock?.risk_level === 'exit') {
      return { text: '回避', cls: 'bg-red-50 text-red-700 border-red-100' };
    }
    return { text: '观察', cls: 'bg-gray-50 text-gray-700 border-gray-100' };
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
            <div className="text-sm text-gray-500">{stock.code}</div>
          </div>
          <div className="flex items-center gap-2 flex-wrap justify-end">
            <span className="px-2 py-1 rounded bg-gray-50 text-gray-700 text-xs border border-gray-100">
              {roleLabel}
            </span>
            <span className={`px-2 py-1 rounded text-xs border ${status.cls}`}>
              {status.text}{pending && executeDate ? `(${executeDate})` : ''}
            </span>
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
              <div className="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 border border-green-100 rounded text-sm">
                <Target size={14} />
                满足出手条件
              </div>
            ) : (
              <div className="text-sm text-gray-500">
                {roleLabel === '跟随' ? '跟随仅观察' : '未满足出手条件'}
              </div>
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
              <span className={`px-2 py-1 rounded border ${rp.cls}`}>{rp.text}</span>
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
        <h3 className="text-lg font-medium text-gray-900 mb-2">暂无持仓数据</h3>
        <p className="text-gray-500">无法获取投资组合信息</p>
      </div>
    );
  }
  
  const hasPositions = portfolio.open_positions && portfolio.open_positions.length > 0;
  const hasClosedTrades = Array.isArray(portfolio.closed_trades) && portfolio.closed_trades.length > 0;
  const hasManualIntents = Array.isArray(portfolio.manual_intents) && portfolio.manual_intents.length > 0;
  
  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">总资产</div>
          <div className="text-2xl font-bold text-gray-900">¥{(portfolio.total_value / 10000).toFixed(2)}万</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">现金</div>
          <div className="text-2xl font-bold text-blue-600">¥{(portfolio.cash / 10000).toFixed(2)}万</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-sm text-gray-500 mb-1">总收益</div>
          <div className={`text-2xl font-bold ${portfolio.total_return_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
            {portfolio.total_return_pct >= 0 ? '+' : ''}{portfolio.total_return_pct.toFixed(2)}%
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
          <span className="text-gray-500">策略: <span className="text-gray-900 font-medium">{portfolio.strategy || '--'}</span></span>
          <span className="text-gray-500">数据日期: <span className="text-gray-900">{portfolio.as_of || '--'}</span></span>
          <span className="text-gray-500">初始资金: <span className="text-gray-900">¥{(portfolio.initial_capital / 10000).toFixed(2)}万</span></span>
        </div>
      </div>

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
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">买入价</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">现价</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">市值</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">盈亏</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.open_positions.map((pos, index) => (
                  <tr key={index} className="border-b border-gray-100">
                    <td className="py-3 px-4 text-gray-900">{pos.code}</td>
                    <td className="py-3 px-4 text-gray-900">{pos.name}</td>
                    <td className="py-3 px-4 text-gray-500">{pos.sector}</td>
                    <td className="py-3 px-4 text-gray-900">¥{pos.buy_price?.toFixed(2)}</td>
                    <td className="py-3 px-4 text-gray-900">¥{pos.current_price?.toFixed(2)}</td>
                    <td className="py-3 px-4 text-gray-900">¥{(pos.market_value / 10000).toFixed(2)}万</td>
                    <td className="py-3 px-4">
                      <span className={`${pos.unrealized_pnl >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {pos.unrealized_pnl >= 0 ? '+' : ''}{pos.unrealized_pnl_pct?.toFixed(2)}%
                      </span>
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
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">数量</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">买入价</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">卖出价</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">收益</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">原因</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.closed_trades.map((t, index) => (
                  <tr key={index} className="border-b border-gray-100">
                    <td className="py-3 px-4 text-gray-900">{t.sell_date || '--'}</td>
                    <td className="py-3 px-4 text-gray-900">{t.code}</td>
                    <td className="py-3 px-4 text-gray-900">{t.name}</td>
                    <td className="py-3 px-4 text-gray-500">{t.buy_date || '--'}</td>
                    <td className="py-3 px-4 text-gray-900">{t.shares}</td>
                    <td className="py-3 px-4 text-gray-900">¥{Number(t.buy_price || 0).toFixed(2)}</td>
                    <td className="py-3 px-4 text-gray-900">¥{Number(t.sell_price || 0).toFixed(2)}</td>
                    <td className="py-3 px-4">
                      <span className={`${Number(t.realized_pnl || 0) >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {Number(t.realized_pnl || 0) >= 0 ? '+' : ''}¥{Number(t.realized_pnl || 0).toFixed(2)} ({Number(t.return_pct || 0).toFixed(2)}%)
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-500">{t.sell_reason || '--'}</td>
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
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">股票</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">请求日</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">状态</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.manual_intents.slice(-30).reverse().map((it, idx) => (
                  <tr key={idx} className="border-b border-gray-100">
                    <td className="py-3 px-4 text-gray-900">{it.created_at || it.executed_at || it.cancelled_at || '--'}</td>
                    <td className="py-3 px-4 text-gray-900">{it.intent_type || '--'}</td>
                    <td className="py-3 px-4 text-gray-900">{it.code || '--'}</td>
                    <td className="py-3 px-4 text-gray-500">{it.requested_date || '--'}</td>
                    <td className="py-3 px-4 text-gray-500">{it.status || '--'}</td>
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
                <td className="py-3 px-4 text-gray-900">{candidate.code}</td>
                <td className="py-3 px-4 text-gray-900">{candidate.name}</td>
                <td className="py-3 px-4 text-gray-500">{candidate.sector}</td>
                <td className="py-3 px-4 text-gray-500">{candidate.role || '--'}</td>
                <td className="py-3 px-4">
                  {candidate.manual?.abandoned ? (
                    <span className="px-2 py-1 rounded text-xs border bg-gray-100 text-gray-700 border-gray-200">已放弃</span>
                  ) : candidate.manual?.buy_intent_pending ? (
                    <span className="px-2 py-1 rounded text-xs border bg-blue-50 text-blue-700 border-blue-100">已排队</span>
                  ) : candidate.buy_signal ? (
                    <span className="px-2 py-1 rounded text-xs border bg-green-50 text-green-700 border-green-100">可出手</span>
                  ) : (
                    <span className="px-2 py-1 rounded text-xs border bg-gray-50 text-gray-700 border-gray-100">观察</span>
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
          <div className="text-sm text-gray-500 mb-1">总收益</div>
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
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">总收益</th>
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
  const [loading, setLoading] = useState(false);
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

  const buildCandidatesFromHotSectors = (payload) => {
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
  };

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // 根据当前 tab 获取不同数据
      const requests = [];
      
      if (activeTab === 'today') {
        requests.push(
          fetch(`/api/market-phase?date=${selectedDate}`),
          fetch(`/api/sectors/hot?date=${selectedDate}&mode=${hotMode}&include_portfolio=0&include_sell_signal=0`)
        );
      } else if (activeTab === 'portfolio') {
        requests.push(
          fetch(`/api/lowfreq/portfolio?date=${selectedDate}`)
        );
      } else if (activeTab === 'candidates') {
        requests.push(
          fetch(`/api/sectors/hot?date=${selectedDate}&mode=${hotMode}&include_portfolio=0&include_sell_signal=0`)
        );
      } else if (activeTab === 'backtest') {
        setData(prev => ({ ...prev, backtest: null }));
      }

      const responses = await Promise.all(requests);
      const results = await Promise.all(
        responses.map(r => r.ok ? r.json() : null)
      );

      if (activeTab === 'today') {
        setData(prev => ({
          ...prev,
          marketPhase: results[0],
          hotSectors: results[1],
        }));
      } else if (activeTab === 'portfolio') {
        // portfolio 数据在 /api/sectors/hot 的返回中
        setData(prev => ({ ...prev, portfolio: results[0] }));
      } else if (activeTab === 'candidates') {
        setData(prev => ({ ...prev, candidates: buildCandidatesFromHotSectors(results[0]) }));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchBacktestReports = async () => {
    try {
      const res = await fetch('/api/lowfreq/backtest/reports?limit=10');
      if (!res.ok) {
        return;
      }
      const payload = await res.json();
      if (Array.isArray(payload?.reports)) {
        setBacktestReports(payload.reports);
      }
    } catch (e) {
      return;
    }
  };

  useEffect(() => {
    fetchData();
    if (activeTab === 'backtest') {
      fetchBacktestReports();
    }
  }, [selectedDate, activeTab, hotMode]);

  useEffect(() => {
    if (!backtestEndDate) {
      setBacktestEndDate(selectedDate);
    }
  }, [selectedDate, backtestEndDate]);

  const postJson = async (url, payload) => {
    const headers = { 'Content-Type': 'application/json' };
    const res = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    const json = await res.json().catch(() => null);
    if (!res.ok) {
      const msg = json?.error?.message || json?.message || json?._meta?.message || '请求失败';
      throw new Error(msg);
    }
    return json;
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
    const reportId = backtestResult?.report_id || localStorage.getItem('neotrade3_last_backtest_report_id');
    if (!reportId) {
      return;
    }
    let cancelled = false;
    let timer = null;

    const tick = async () => {
      try {
        const res = await fetch(`/api/lowfreq/backtest/status?report_id=${encodeURIComponent(reportId)}`);
        if (!res.ok) {
          return;
        }
        const payload = await res.json();
        if (cancelled) {
          return;
        }
        const job = payload?.job;
        const jobStatus = job?.status;
        const merged = {
          ...(backtestResult || {}),
          report_id: reportId,
          job,
          pdf_url: payload?.pdf_url || backtestResult?.pdf_url,
          json_url: payload?.json_url || backtestResult?.json_url,
        };
        if (jobStatus === 'done') {
          merged._meta = { ...(merged._meta || {}), status: 'ok' };
        } else if (jobStatus === 'failed') {
          merged._meta = { ...(merged._meta || {}), status: 'error' };
        } else {
          merged._meta = { ...(merged._meta || {}), status: 'accepted' };
        }
        setBacktestResult(merged);
        if (jobStatus === 'done' || jobStatus === 'failed') {
          fetchBacktestReports();
        }
      } catch (e) {
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
  }, [activeTab, backtestResult?.report_id]);

  const tabs = [
    { id: 'today', label: '今日快照', icon: Calendar },
    { id: 'portfolio', label: '持仓监控', icon: Wallet },
    { id: 'candidates', label: '候选池', icon: ListFilter },
    { id: 'backtest', label: '回测报告', icon: FileText },
  ];

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
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={32} className="animate-spin text-blue-600" />
        </div>
      )}

      {/* Tab Content */}
      {!loading && activeTab === 'today' && (
        <div className="space-y-6">
          {/* Market Phase */}
          {data.marketPhase?.market_phase && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">市场阶段</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm text-gray-500">当前阶段</div>
                  <div className="text-xl font-bold text-gray-900 capitalize">{data.marketPhase.market_phase.phase}</div>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm text-gray-500">市场宽度</div>
                  <div className="text-xl font-bold text-gray-900">{(data.marketPhase.market_phase.market_breadth * 100)?.toFixed(0)}%</div>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm text-gray-500">20日收益</div>
                  <div className={`text-xl font-bold ${data.marketPhase.market_phase.market_return_20d > 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {(data.marketPhase.market_phase.market_return_20d * 100)?.toFixed(2)}%
                  </div>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm text-gray-500">成交量趋势</div>
                  <div className="text-xl font-bold text-gray-900 capitalize">{data.marketPhase.market_phase.amount_trend}</div>
                </div>
              </div>
            </div>
          )}

          {/* Portfolio Summary */}
          {data.hotSectors?.portfolio && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">投资组合</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm text-gray-500">总价值</div>
                  <div className="text-xl font-bold text-gray-900">¥{(data.hotSectors.portfolio.total_value / 10000)?.toFixed(2)}万</div>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm text-gray-500">现金</div>
                  <div className="text-xl font-bold text-gray-900">¥{(data.hotSectors.portfolio.cash / 10000)?.toFixed(2)}万</div>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm text-gray-500">总收益</div>
                  <div className={`text-xl font-bold ${data.hotSectors.portfolio.total_return_pct > 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {data.hotSectors.portfolio.total_return_pct?.toFixed(2)}%
                  </div>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="text-sm text-gray-500">持仓数</div>
                  <div className="text-xl font-bold text-gray-900">{data.hotSectors.portfolio.open_positions?.length || 0}</div>
                </div>
              </div>
            </div>
          )}

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
            {data.hotSectors?._meta?.status === 'error' ? (
              <div className="bg-white rounded-lg border border-gray-200 p-6 text-sm text-gray-700">
                {data.hotSectors?._meta?.message || '热门板块数据不可用'}
              </div>
            ) : null}
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
            {!data.hotSectors?.sectors?.length && !loading && (
              <div className="text-center py-12 text-gray-500">
                暂无热门板块数据
              </div>
            )}
          </div>
        </div>
      )}

      {!loading && activeTab === 'portfolio' && (
        <PortfolioPanel data={data.portfolio} />
      )}

      {!loading && activeTab === 'candidates' && (
        <CandidatesPanel
          data={{ candidates: data.candidates || [] }}
          onBuyIntent={handleBuyIntent}
          onAbandon={handleAbandon}
          posting={posting}
        />
      )}

      {!loading && activeTab === 'backtest' && (
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
      )}
    </div>
  );
}
