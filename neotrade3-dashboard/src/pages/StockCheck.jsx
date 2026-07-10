import { useState } from 'react';
import { Search, TrendingUp, Layers, Target } from 'lucide-react';
import { useApp } from '../context/AppContext';
import BlockMessage from '../components/BlockMessage';
import DateSelector from '../components/DateSelector';
import PageHeader from '../components/PageHeader';
import SemanticBadge from '../components/SemanticBadge';
import { STATUS_COPY } from '../components/statusCopy';
import StockCodeLink from '../components/StockCodeLink';
import { fetchApi } from '../services/api';

export default function StockCheck() {
  const { selectedDate } = useApp();
  const [stockCode, setStockCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleCheck = async () => {
    if (!stockCode.trim()) {
      setError('请输入股票代码');
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await fetchApi(
        `/api/check-stock?code=${encodeURIComponent(stockCode.trim())}&date=${encodeURIComponent(selectedDate)}`,
        {},
        { timeoutMs: 45000 }
      );
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleCheck();
    }
  };

  return (
    <div className="space-y-6">
      {/* Date Selector */}
      <DateSelector />

      <PageHeader title="单股核验" subtitle="输入股票代码，核验筛选器 / 热门板块 / 老鸭头 / 确定性" />

      {/* Search Input */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              股票代码
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={stockCode}
                onChange={(e) => setStockCode(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="例如：600000"
                className="flex-1 border border-gray-300 rounded-lg px-4 py-3 text-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleCheck}
                disabled={loading}
                className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                <Search size={20} />
                {loading ? '核验中...' : '开始核验'}
              </button>
            </div>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mt-4">
            <BlockMessage tone="red" message={error} />
          </div>
        )}
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Basic Info */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">基本信息</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-gray-500">股票代码</div>
                <div className="text-lg font-semibold text-gray-900">
                  <StockCodeLink
                    code={result.stock_code || stockCode.trim()}
                    className="hover:text-blue-600 hover:underline"
                  >
                    {result.stock_code || stockCode.trim()}
                  </StockCodeLink>
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">核验日期</div>
                <div className="text-lg font-semibold text-gray-900">{result.target_date || selectedDate}</div>
              </div>
              <div>
                <div className="text-sm text-gray-500">确定性</div>
                <div className="text-lg font-semibold text-gray-900">
                  {typeof result?.checks?.certainty?.value === 'number'
                    ? result.checks.certainty.value.toFixed(2)
                    : '--'}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">确定性来源</div>
                <div className="text-lg font-semibold text-gray-900">
                  {result?.checks?.certainty?.message || '--'}
                </div>
              </div>
            </div>
          </div>

          {/* Hot Sector Presence */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Layers size={20} />
              热门板块（Top5）命中
            </h3>
            <div className="text-sm text-gray-700 mb-3">
              {result?.checks?.hot_sectors?.message || '—'}
            </div>
            {Array.isArray(result?.checks?.hot_sectors?.matches) && result.checks.hot_sectors.matches.length > 0 ? (
              <div className="space-y-2">
                {result.checks.hot_sectors.matches.map((m, idx) => (
                  <div key={idx} className="p-3 bg-gray-50 rounded border border-gray-100 text-sm">
                    <div className="flex items-center justify-between">
                      <div className="font-medium text-gray-900">{m.sector}</div>
                      <div className="flex items-center gap-2">
                        <SemanticBadge
                          semanticKey={
                            m.buy_signal === true
                              ? 'entry_ready'
                              : (m.role === 'leaders' || m.role === 'leader')
                                ? 'watch_general'
                                : 'watch_follower'
                          }
                          label={
                            m.buy_signal === true
                              ? STATUS_COPY.actionable
                              : (m.role === 'leaders' || m.role === 'leader')
                                ? STATUS_COPY.observing
                                : STATUS_COPY.followerObserving
                          }
                        />
                        <div className="text-gray-500">{m.role}</div>
                      </div>
                    </div>
                    <div className="text-gray-600 mt-1">
                      入场信号：{m.buy_signal === true ? '是' : m.buy_signal === false ? '否' : '—'}
                      {m.suggested_entry ? ` · 建议：${m.suggested_entry}` : ''}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-500">未命中热门板块 Top5</div>
            )}
          </div>

          {/* Weekly Duck Head */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Target size={20} />
              老鸭头（周线）
            </h3>
            <div className="text-sm text-gray-700">
              {result?.checks?.weekly_duck_head?.explain_cn || '—'}
            </div>
          </div>

          {/* Screeners */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <TrendingUp size={20} />
              筛选器核验
            </h3>
            {Array.isArray(result?.checks?.screeners?.items) ? (
              <div className="space-y-4">
                <div>
                  <div className="text-sm font-medium text-gray-700 mb-2">通过</div>
                  <div className="space-y-2">
                    {result.checks.screeners.items
                      .filter((x) => x && x.result === true)
                      .map((x) => (
                        <div key={x.screener_id} className="p-3 bg-green-50 border border-green-200 rounded text-sm">
                          <div className="flex items-center justify-between">
                            <div className="font-medium text-gray-900">{x.name}</div>
                            <div className="flex items-center gap-2">
                              <SemanticBadge semanticKey="check_pass" label="通过" />
                              <div className="text-green-700">{x.screener_id}</div>
                            </div>
                          </div>
                          <div className="text-green-800 mt-1">{x.explain_cn || '通过'}</div>
                        </div>
                      ))}
                    {result.checks.screeners.items.filter((x) => x && x.result === true).length === 0 ? (
                      <div className="text-sm text-gray-500">无</div>
                    ) : null}
                  </div>
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-700 mb-2">未通过</div>
                  <div className="space-y-2">
                    {result.checks.screeners.items
                      .filter((x) => x && x.result === false)
                      .map((x) => (
                        <div key={x.screener_id} className="p-3 bg-red-50 border border-red-200 rounded text-sm">
                          <div className="flex items-center justify-between">
                            <div className="font-medium text-gray-900">{x.name}</div>
                            <div className="flex items-center gap-2">
                              <SemanticBadge semanticKey="check_fail" label="未通过" />
                              <div className="text-red-700">{x.screener_id}</div>
                            </div>
                          </div>
                          <div className="text-red-800 mt-1">{x.explain_cn || '未通过'}</div>
                        </div>
                      ))}
                    {result.checks.screeners.items.filter((x) => x && x.result === false).length === 0 ? (
                      <div className="text-sm text-gray-500">无</div>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-gray-500">无可用筛选器核验结果</div>
            )}
          </div>

          <details className="bg-white rounded-lg border border-gray-200 p-6">
            <summary className="text-sm text-gray-600 cursor-pointer">原始返回数据</summary>
            <pre className="mt-3 text-sm text-gray-600 overflow-auto bg-gray-50 p-4 rounded">
              {JSON.stringify(result, null, 2)}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}
