import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ChevronLeft, FileText } from 'lucide-react';

import { fetchApi } from '../services/api';

function safeNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function formatPercent(value, { signed = false } = {}) {
  const numeric = safeNumber(value);
  if (numeric == null) {
    return '--';
  }
  const prefix = signed && numeric >= 0 ? '+' : '';
  return `${prefix}${numeric.toFixed(2)}%`;
}

function formatCurrency(value) {
  const numeric = safeNumber(value);
  return numeric == null ? '--' : `¥${numeric.toFixed(2)}`;
}

function displayText(value) {
  const text = String(value ?? '').trim();
  return text || '--';
}

function signedNumberClass(value) {
  const numeric = safeNumber(value);
  if (numeric == null) {
    return 'text-gray-500';
  }
  return numeric >= 0 ? 'text-red-600' : 'text-green-600';
}

export default function LowfreqBacktestReport() {
  const { reportId = '' } = useParams();
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const detail = await fetchApi(
          `/api/lowfreq/backtest/report-detail?report_id=${encodeURIComponent(reportId)}`,
          {},
          { timeoutMs: 45000 },
        );
        if (!alive) return;
        setPayload(detail);
      } catch (err) {
        if (!alive) return;
        setPayload(null);
        setError(String(err?.message || '无法读取回测报告详情'));
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    }

    if (reportId) {
      load();
    } else {
      setPayload(null);
      setError('报告编号缺失');
      setLoading(false);
    }

    return () => {
      alive = false;
    };
  }, [reportId]);

  const summary = payload?.summary && typeof payload.summary === 'object' ? payload.summary : {};
  const actionEntries = useMemo(() => {
    const source = payload?.execution_action_summary;
    return source && typeof source === 'object'
      ? Object.entries(source).filter(([, value]) => safeNumber(value) != null)
      : [];
  }, [payload]);
  const tradeBlockEntries = useMemo(() => {
    const source = payload?.trade_blocks;
    return source && typeof source === 'object'
      ? Object.entries(source).filter(([, value]) => safeNumber(value) != null)
      : [];
  }, [payload]);
  const coverageEntries = useMemo(() => {
    const source = payload?.coverage_gaps;
    return source && typeof source === 'object'
      ? Object.entries(source)
      : [];
  }, [payload]);
  const configEntries = useMemo(() => {
    const source = payload?.config_snapshot;
    return source && typeof source === 'object'
      ? Object.entries(source)
      : [];
  }, [payload]);
  const nextSession = payload?.next_session && typeof payload.next_session === 'object' ? payload.next_session : {};
  const nextSignalEntries = useMemo(() => {
    const source = nextSession?.signal_summary;
    return source && typeof source === 'object' ? Object.entries(source) : [];
  }, [nextSession]);
  const nextCandidates = Array.isArray(nextSession?.candidates) ? nextSession.candidates.slice(0, 5) : [];
  const exitQuality = payload?.exit_quality && typeof payload.exit_quality === 'object' ? payload.exit_quality : {};
  const exitRunup = exitQuality?.post_exit_runup_pct && typeof exitQuality.post_exit_runup_pct === 'object'
    ? exitQuality.post_exit_runup_pct
    : {};
  const buyDates = Array.isArray(payload?.buy_dates) ? payload.buy_dates : [];
  const recentTrades = Array.isArray(payload?.recent_trades) ? payload.recent_trades : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <Link to="/lowfreq" className="inline-flex items-center gap-2 text-sm text-blue-600 hover:underline">
            <ChevronLeft size={16} />
            返回选股工作台
          </Link>
          <h1 className="mt-3 text-2xl font-semibold text-gray-900">回测报告详情</h1>
          <p className="mt-1 text-sm text-gray-500">报告编号：{displayText(reportId)}</p>
        </div>
        {payload ? (
          <div className="flex items-center gap-3 text-sm flex-wrap">
            {payload?.pdf_url ? (
              <a className="text-blue-600 hover:underline" href={payload.pdf_url} target="_blank" rel="noreferrer">
                下载 PDF
              </a>
            ) : null}
            {payload?.json_url ? (
              <a className="text-gray-500 hover:text-gray-700 hover:underline" href={payload.json_url} target="_blank" rel="noreferrer">
                下载 JSON
              </a>
            ) : null}
          </div>
        ) : null}
      </div>

      {loading ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <FileText size={48} className="mx-auto text-gray-300 mb-4" />
          <h2 className="text-lg font-medium text-gray-900 mb-2">读取报告中</h2>
          <p className="text-gray-500">正在加载结构化结果</p>
        </div>
      ) : null}

      {!loading && error ? (
        <div className="bg-white rounded-lg border border-red-200 bg-red-50 p-12 text-center">
          <FileText size={48} className="mx-auto text-red-200 mb-4" />
          <h2 className="text-lg font-medium text-red-900 mb-2">报告读取失败</h2>
          <p className="text-red-700">{error}</p>
        </div>
      ) : null}

      {!loading && !error && payload ? (
        <>
          <div className="grid grid-cols-2 xl:grid-cols-5 gap-4">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="text-sm text-gray-500 mb-1">回测总收益</div>
              <div className={`text-2xl font-bold ${signedNumberClass(summary.total_return_pct)}`}>
                {formatPercent(summary.total_return_pct, { signed: true })}
              </div>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="text-sm text-gray-500 mb-1">年化收益</div>
              <div className={`text-2xl font-bold ${signedNumberClass(summary.annual_return_pct)}`}>
                {formatPercent(summary.annual_return_pct, { signed: true })}
              </div>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="text-sm text-gray-500 mb-1">最大回撤</div>
              <div className="text-2xl font-bold text-green-600">
                {formatPercent(summary.max_drawdown_pct)}
              </div>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="text-sm text-gray-500 mb-1">总交易数</div>
              <div className="text-2xl font-bold text-gray-900">{displayText(summary.total_trades)}</div>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="text-sm text-gray-500 mb-1">运行方式</div>
              <div className="text-lg font-semibold text-gray-900 break-all">{displayText(payload.execution_mode)}</div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">执行摘要</h2>
              {actionEntries.length > 0 ? (
                <div className="space-y-3">
                  {actionEntries.map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between text-sm">
                      <span className="text-gray-500">{displayText(key)}</span>
                      <span className="text-gray-900 font-medium">{displayText(value)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-gray-500">暂无执行动作摘要</div>
              )}
            </div>

            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">退出质量评估</h2>
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">观察窗口</span>
                  <span className="text-gray-900 font-medium">{displayText(exitQuality.lookahead_trading_days)} 个交易日</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">样本数</span>
                  <span className="text-gray-900 font-medium">{displayText(exitQuality.count)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">卖出后涨幅 P90</span>
                  <span className={`font-medium ${signedNumberClass(exitRunup.p90)}`}>{formatPercent(exitRunup.p90, { signed: true })}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">窗口内最大继续上涨</span>
                  <span className={`font-medium ${signedNumberClass(exitRunup.max)}`}>{formatPercent(exitRunup.max, { signed: true })}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">继续上涨超 10% 占比</span>
                  <span className={`font-medium ${signedNumberClass(exitRunup.gt_10pct_rate)}`}>{formatPercent(exitRunup.gt_10pct_rate, { signed: true })}</span>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">下一交易日信号</h2>
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">下一交易日</span>
                  <span className="text-gray-900 font-medium">{displayText(nextSession.next_trading_day)}</span>
                </div>
                {nextSignalEntries.map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-gray-500">{displayText(key)}</span>
                    <span className="text-gray-900 font-medium">{displayText(value)}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4">
                <div className="text-sm font-medium text-gray-900 mb-2">前 5 候选</div>
                {nextCandidates.length > 0 ? (
                  <div className="space-y-2">
                    {nextCandidates.map((candidate) => (
                      <div key={candidate.code} className="rounded border border-gray-100 px-3 py-2">
                        <div className="text-sm font-medium text-gray-900">
                          {displayText(candidate.name)} · {displayText(candidate.code)}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {displayText(candidate.sector_name || candidate.sector)} · {displayText(candidate.role)} · 买入分 {safeNumber(candidate.buy_score) == null ? '--' : candidate.buy_score.toFixed(0)}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-gray-500">暂无候选信号</div>
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">执行拦截统计</h2>
              {tradeBlockEntries.length > 0 ? (
                <div className="space-y-3">
                  {tradeBlockEntries.map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between text-sm">
                      <span className="text-gray-500 break-all pr-3">{displayText(key)}</span>
                      <span className="text-gray-900 font-medium">{displayText(value)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-gray-500">暂无执行拦截统计</div>
              )}
            </div>

            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">参数与覆盖情况</h2>
              <div className="space-y-3 text-sm">
                {configEntries.map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between gap-4">
                    <span className="text-gray-500">{displayText(key)}</span>
                    <span className="text-gray-900 font-medium break-all text-right">{displayText(value)}</span>
                  </div>
                ))}
                {coverageEntries.map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between gap-4">
                    <span className="text-gray-500">{displayText(key)}</span>
                    <span className="text-gray-900 font-medium break-all text-right">{displayText(value)}</span>
                  </div>
                ))}
                {configEntries.length === 0 && coverageEntries.length === 0 ? (
                  <div className="text-sm text-gray-500">暂无额外参数与覆盖信息</div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">买点分布</h2>
              {buyDates.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">买入日期</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">次数</th>
                      </tr>
                    </thead>
                    <tbody>
                      {buyDates.map((row, index) => (
                        <tr key={`${row.buy_date || 'buy-date'}-${index}`} className="border-b border-gray-100">
                          <td className="py-3 px-4 text-gray-900">{displayText(row.buy_date)}</td>
                          <td className="py-3 px-4 text-gray-500">{displayText(row.count)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-sm text-gray-500">暂无买点分布</div>
              )}
            </div>

            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">最近交易样本</h2>
              {recentTrades.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">股票</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">买入</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">卖出</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">收益</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentTrades.map((trade, index) => (
                        <tr key={`${trade.code || 'trade'}-${trade.sell_date || trade.buy_date || index}`} className="border-b border-gray-100 align-top">
                          <td className="py-3 px-4 text-gray-900">
                            <div>{displayText(trade.name)}</div>
                            <div className="text-xs text-gray-500 mt-1">
                              {displayText(trade.code)} · {displayText(trade.role)}
                            </div>
                          </td>
                          <td className="py-3 px-4 text-gray-500">
                            <div>{displayText(trade.buy_date)}</div>
                            <div className="text-xs mt-1">{formatCurrency(trade.buy_price)}</div>
                          </td>
                          <td className="py-3 px-4 text-gray-500">
                            <div>{displayText(trade.sell_date)}</div>
                            <div className="text-xs mt-1">{formatCurrency(trade.sell_price)}</div>
                          </td>
                          <td className="py-3 px-4">
                            <div className={signedNumberClass(trade.return_pct)}>
                              {formatPercent(trade.return_pct, { signed: true })}
                            </div>
                            <div className="text-xs text-gray-500 mt-1">
                              持有 {displayText(trade.hold_days)} 天
                            </div>
                            <div className="text-xs text-gray-500 mt-1 max-w-xs">
                              {displayText(trade.sell_reason)}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-sm text-gray-500">暂无交易样本</div>
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
