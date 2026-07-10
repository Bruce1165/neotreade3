import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, BarChart3, FileText, Flame, ListChecks, Wallet } from 'lucide-react';
import { useApp } from '../context/AppContext';
import BlockMessage from '../components/BlockMessage';
import DateSelector from '../components/DateSelector';
import MetricCard from '../components/MetricCard';
import PageHeader from '../components/PageHeader';
import StatusPill from '../components/StatusPill';
import StockCodeLink from '../components/StockCodeLink';
import { fetchApi } from '../services/api';
import { createBlockState, rejectBlock, resolveBlock, startBlock } from '../services/asyncBlocks';

function displayText(value) {
  const text = String(value ?? '').trim();
  return text || '--';
}

function formatScore(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '--';
  }
  return value.toFixed(1);
}

function formatPrice(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '--';
  }
  return `¥${value.toFixed(2)}`;
}

function formatPercent(value, { signed = false } = {}) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '--';
  }
  const prefix = signed && value >= 0 ? '+' : '';
  return `${prefix}${value.toFixed(2)}%`;
}

function signedClass(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'text-gray-500';
  }
  return value >= 0 ? 'text-red-600' : 'text-green-600';
}

function ActionCard({ title, description, to, cta }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 flex flex-col gap-3">
      <div>
        <div className="text-sm font-medium text-gray-500">{title}</div>
        <div className="text-sm text-gray-900 leading-6 mt-2">{description}</div>
      </div>
      <div>
        <Link
          to={to}
          className="inline-flex items-center rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          {cta}
        </Link>
      </div>
    </div>
  );
}

function isEnvironmentUnavailableMessage(message) {
  const text = String(message || '').trim();
  return text.includes('后端不可达') || text.includes('请求超时');
}

export default function Overview() {
  const { selectedDate } = useApp();
  const [block, setBlock] = useState(createBlockState());

  const fetchData = useCallback(async () => {
    setBlock((prev) => startBlock(prev, true));
    try {
      const payload = await fetchApi(
        `/api/lowfreq/workbench?date=${encodeURIComponent(selectedDate)}&ensure_generated=false`,
        {},
        { timeoutMs: 60000 }
      );
      setBlock(resolveBlock(payload));
    } catch (error) {
      setBlock((prev) => rejectBlock(prev, error, true));
    }
  }, [selectedDate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const payload = block.data || {};
  const meta = payload.meta || {};
  const marketSummary = payload.market_summary || {};
  const dailyOps = payload.daily_ops || {};
  const hotSectors = Array.isArray(payload.hot_sectors) ? payload.hot_sectors : [];
  const trackingList = Array.isArray(payload.tracking_list) ? payload.tracking_list : [];
  const positions = Array.isArray(payload.positions) ? payload.positions : [];
  const tradeLedger = Array.isArray(payload.trade_ledger) ? payload.trade_ledger : [];
  const loading = block.loading;
  const pageError = !block.loaded && block.error ? block.error : null;
  const environmentUnavailable = isEnvironmentUnavailableMessage(pageError);
  const summaryText = displayText(meta.summary_text || marketSummary.summary_text);
  const topSector = hotSectors[0] || null;
  const topTracking = trackingList[0] || null;
  const suggestedAction = !dailyOps.available
    ? '先确认每日运行状态，排除阻塞后再继续审阅。'
    : topSector
    ? `优先复盘 ${displayText(topSector.sector_name)}，再进入选股工作台确认候选动作。`
    : trackingList.length
    ? '优先检查跟踪池和持仓池，确认是否需要人工处理。'
    : '进入选股工作台补充候选与复盘信息。';
  const riskSummary = dailyOps.available
    ? `运行状态 ${displayText(dailyOps.status_text)}，顺延待处理 ${displayText(dailyOps.overdue_shifted_count)}，日后待执行 ${displayText(dailyOps.pending_intents_after)}。`
    : '每日运行状态尚未确认，建议先检查链路健康与数据更新。';

  return (
    <div className="space-y-6">
      <DateSelector onRefresh={fetchData} loading={loading} />

      <PageHeader title="今日总览" subtitle={summaryText} onRefresh={fetchData} loading={loading} />

      {pageError && !environmentUnavailable ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3 text-red-700">
          <AlertCircle size={20} />
          <span>{pageError}</span>
        </div>
      ) : null}

      {environmentUnavailable ? (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-5">
          <div className="font-medium text-amber-900">本地服务暂未连接</div>
          <div className="text-sm text-amber-800 mt-2">
            当前先展示总览骨架。启动后端服务后刷新页面，即可恢复实时数据。
          </div>
        </div>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="当前交易日" value={displayText(meta.as_of_date)} subtitle="工作台快照日期" />
        <MetricCard title="运行状态" value={displayText(dailyOps.status_text)} subtitle="每日任务与数据更新" />
        <MetricCard title="市场倾向" value={displayText(marketSummary.bias_label)} subtitle={displayText(marketSummary.phase_label)} />
        <MetricCard title="当前持仓" value={String(positions.length)} subtitle="已建仓股票数" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <ActionCard
          title="今日结论"
          description={summaryText}
          to="/market-intelligence"
          cta="查看主线审阅"
        />
        <ActionCard
          title="风险与阻塞"
          description={riskSummary}
          to="/ops"
          cta="查看运维中心"
        />
        <ActionCard
          title="建议动作"
          description={suggestedAction}
          to="/lowfreq"
          cta="进入选股工作台"
        />
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">重点摘要</h3>
            <div className="text-sm text-gray-500 mt-1">先看结论，再决定进入哪个明细区域。</div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <a href="#hot-sectors-section" className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50">人气板块</a>
            <a href="#tracking-section" className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50">跟踪池</a>
            <a href="#positions-section" className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50">持仓池</a>
            <a href="#ledger-section" className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50">交易台账</a>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mt-4">
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
            <div className="text-sm text-gray-500 mb-1">当前人气板块</div>
            <div className="text-xl font-semibold text-gray-900">{topSector ? displayText(topSector.sector_name) : '--'}</div>
            <div className="text-sm text-gray-500 mt-1">{topSector ? displayText(topSector.summary_text) : '暂无板块摘要'}</div>
          </div>
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
            <div className="text-sm text-gray-500 mb-1">重点跟踪股票</div>
            <div className="text-xl font-semibold text-gray-900">{topTracking ? displayText(topTracking.name) : '--'}</div>
            <div className="text-sm text-gray-500 mt-1">{topTracking ? displayText(topTracking.summary_text) : '暂无跟踪摘要'}</div>
          </div>
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
            <div className="text-sm text-gray-500 mb-1">跟踪股票数</div>
            <div className="text-xl font-semibold text-gray-900">{String(trackingList.length)}</div>
            <div className="text-sm text-gray-500 mt-1">候选与建仓准备池</div>
          </div>
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
            <div className="text-sm text-gray-500 mb-1">最近交易动作</div>
            <div className="text-xl font-semibold text-gray-900">{tradeLedger.length ? displayText(tradeLedger[0].action_text) : '--'}</div>
            <div className="text-sm text-gray-500 mt-1">{tradeLedger.length ? `${displayText(tradeLedger[0].name)} · ${displayText(tradeLedger[0].trade_date)}` : '暂无交易记录'}</div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">每日运行与数据更新</h3>
            <div className="text-sm text-gray-500 mt-1">{displayText(dailyOps.summary_text)}</div>
          </div>
          {dailyOps.available ? (
            <StatusPill kind={dailyOps.status_kind} label={displayText(dailyOps.status_text)} />
          ) : (
            <StatusPill kind="blocked" label="未确认" />
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mt-4">
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
            <div className="text-sm text-gray-500 mb-1">最近日任务</div>
            <div className="text-xl font-semibold text-gray-900">{displayText(dailyOps.run_date)}</div>
            <div className="text-sm text-gray-500 mt-1">最近一轮 daily pipeline 账本日期</div>
          </div>
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
            <div className="text-sm text-gray-500 mb-1">数据追平状态</div>
            <div className="text-xl font-semibold text-gray-900">{displayText(dailyOps.latest_data_synced_text)}</div>
            <div className="text-sm text-gray-500 mt-1">最新数据日 {displayText(meta.latest_data_date)}</div>
          </div>
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
            <div className="text-sm text-gray-500 mb-1">顺延待处理</div>
            <div className="text-xl font-semibold text-gray-900">{displayText(dailyOps.overdue_shifted_count)}</div>
            <div className="text-sm text-gray-500 mt-1">昨日收口中被顺延到下一交易日的意图数</div>
          </div>
          <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
            <div className="text-sm text-gray-500 mb-1">日后待执行</div>
            <div className="text-xl font-semibold text-gray-900">{displayText(dailyOps.pending_intents_after)}</div>
            <div className="text-sm text-gray-500 mt-1">低频日运行后仍处于待执行的意图数</div>
          </div>
        </div>

        {Array.isArray(dailyOps.steps) && dailyOps.steps.length ? (
          <div className="mt-4 flex items-center gap-2 flex-wrap">
            {dailyOps.steps.map((step) => (
              <span key={step.step_id} className="inline-flex items-center gap-2 rounded border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs text-gray-700">
                <span>{displayText(step.step_label)}</span>
                <StatusPill kind={step.status_kind} label={displayText(step.status_text)} />
              </span>
            ))}
          </div>
        ) : null}

        <div className="mt-4 text-sm text-gray-500 flex items-center gap-4 flex-wrap">
          <span>
            行情来源：
            <span className="ml-1 text-gray-900 font-medium">{displayText(dailyOps.provider)}</span>
          </span>
          <span>
            收口异常：
            <span className="ml-1 text-gray-900 font-medium">{displayText(dailyOps.inconsistency_count)}</span>
          </span>
          <span>
            完成时间：
            <span className="ml-1 text-gray-900 font-medium">{displayText(dailyOps.finished_at)}</span>
          </span>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4 text-sm text-gray-600 flex items-center gap-4 flex-wrap">
        <span>
          最新数据：
          <span className="ml-1 text-gray-900 font-medium">{displayText(meta.latest_data_date)}</span>
        </span>
        <span>
          执行模式：
          <span className="ml-1 text-gray-900 font-medium">{displayText(meta.execution_mode)}</span>
        </span>
        <span>
          自动执行：
          <span className="ml-1 text-gray-900 font-medium">{meta.autopilot_enabled ? '开启' : '关闭'}</span>
        </span>
        <span>
          市场倾向：
          <span className="ml-1 text-gray-900 font-medium">{displayText(marketSummary.bias_label)}</span>
        </span>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <BarChart3 size={20} className="text-blue-600" />
          大盘阶段判断
        </h3>
        {loading && !block.loaded ? (
          <BlockMessage message="工作台加载中..." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
              <div className="text-sm text-gray-500 mb-1">当前阶段</div>
              <div className="text-xl font-semibold text-gray-900">{displayText(marketSummary.phase_label)}</div>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
              <div className="text-sm text-gray-500 mb-1">操作倾向</div>
              <div className="text-xl font-semibold text-gray-900">{displayText(marketSummary.bias_label)}</div>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
              <div className="text-sm text-gray-500 mb-1">风险等级</div>
              <div className="text-xl font-semibold text-gray-900">{displayText(marketSummary.risk_label)}</div>
            </div>
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
              <div className="text-sm text-gray-500 mb-1">一句解读</div>
              <div className="text-sm text-gray-900 leading-6">{displayText(marketSummary.summary_text)}</div>
            </div>
          </div>
        )}
        {Array.isArray(marketSummary.evidence) && marketSummary.evidence.length ? (
          <div className="mt-4 flex items-center gap-2 flex-wrap">
            {marketSummary.evidence.map((item) => (
              <span
                key={item}
                className="inline-flex items-center rounded border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-600"
              >
                {item}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      <div id="hot-sectors-section" className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Flame size={20} className="text-orange-500" />
          当前人气板块
        </h3>
        {hotSectors.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2 pr-4">板块</th>
                  <th className="py-2 pr-4">热度</th>
                  <th className="py-2 pr-4">状态</th>
                  <th className="py-2 pr-4">龙头/中军/跟随</th>
                  <th className="py-2 pr-4">可建仓</th>
                  <th className="py-2 pr-4">说明</th>
                </tr>
              </thead>
              <tbody>
                {hotSectors.map((sector) => (
                  <tr key={sector.sector_code} className="border-b last:border-b-0">
                    <td className="py-3 pr-4">
                      <div className="font-medium text-gray-900">{displayText(sector.sector_name)}</div>
                      <div className="text-xs text-gray-500">{displayText(sector.sector_code)}</div>
                    </td>
                    <td className="py-3 pr-4 text-gray-900">{formatScore(sector.heat_score)}</td>
                    <td className="py-3 pr-4">
                      <StatusPill kind={sector.status} label={displayText(sector.status_text)} />
                    </td>
                    <td className="py-3 pr-4 text-gray-700">{`${sector.leader_count}/${sector.middle_count}/${sector.follower_count}`}</td>
                    <td className="py-3 pr-4 text-gray-900">{displayText(sector.actionable_count)}</td>
                    <td className="py-3 pr-4 text-gray-600">
                      <div>{displayText(sector.summary_text)}</div>
                      {Array.isArray(sector.representatives) && sector.representatives.length ? (
                        <div className="mt-1 text-xs text-gray-500">
                          代表股：
                          {sector.representatives
                            .map((stock) => `${displayText(stock.name)}(${displayText(stock.role_text)})`)
                            .join('，')}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-gray-600">暂无人气板块</div>
        )}
      </div>

      <div id="tracking-section" className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <ListChecks size={20} className="text-blue-600" />
          当前跟踪股票池
        </h3>
        {trackingList.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2 pr-4">股票</th>
                  <th className="py-2 pr-4">板块</th>
                  <th className="py-2 pr-4">角色</th>
                  <th className="py-2 pr-4">确定性</th>
                  <th className="py-2 pr-4">层级</th>
                  <th className="py-2 pr-4">状态</th>
                  <th className="py-2 pr-4">说明</th>
                  <th className="py-2 pr-4">首次进入</th>
                  <th className="py-2 pr-4">最近变化</th>
                </tr>
              </thead>
              <tbody>
                {trackingList.map((item) => (
                  <tr key={item.code} className="border-b last:border-b-0">
                    <td className="py-3 pr-4">
                      <div className="font-medium text-gray-900">
                        {displayText(item.name)}{' '}
                        <StockCodeLink code={item.code} className="text-gray-500 hover:text-blue-600 hover:underline">
                          {item.code || '--'}
                        </StockCodeLink>
                      </div>
                      {item.is_new_today ? <div className="text-xs text-blue-600">今日新增</div> : null}
                    </td>
                    <td className="py-3 pr-4 text-gray-700">{displayText(item.sector)}</td>
                    <td className="py-3 pr-4 text-gray-700">{displayText(item.role_text)}</td>
                    <td className="py-3 pr-4 text-gray-900">{formatScore(item.certainty_score)}</td>
                    <td className="py-3 pr-4 text-gray-700">{displayText(item.tracking_stage_text)}</td>
                    <td className="py-3 pr-4">
                      <StatusPill kind={item.tracking_status} label={displayText(item.tracking_status_text)} />
                    </td>
                    <td className="py-3 pr-4 text-gray-600">{displayText(item.summary_text)}</td>
                    <td className="py-3 pr-4 text-gray-500">{displayText(item.first_seen_at)}</td>
                    <td className="py-3 pr-4 text-gray-500">{displayText(item.last_changed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-gray-600">暂无跟踪股票</div>
        )}
      </div>

      <div id="positions-section" className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Wallet size={20} />
          当前建仓股票池
        </h3>
        {positions.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500">
                  <th className="py-2 pr-4">股票</th>
                  <th className="py-2 pr-4">板块</th>
                  <th className="py-2 pr-4">角色</th>
                  <th className="py-2 pr-4">状态</th>
                  <th className="py-2 pr-4">买入价</th>
                  <th className="py-2 pr-4">现价</th>
                  <th className="py-2 pr-4">浮盈亏</th>
                  <th className="py-2 pr-4">接近高位</th>
                  <th className="py-2 pr-4">持有天数</th>
                  <th className="py-2 pr-4">离场风险</th>
                  <th className="py-2 pr-4">说明</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((item) => (
                  <tr key={item.code} className="border-b border-gray-100 last:border-b-0">
                    <td className="py-3 pr-4">
                      <div className="font-medium text-gray-900">
                        {displayText(item.name)}{' '}
                        <StockCodeLink code={item.code} className="text-gray-500 hover:text-blue-600 hover:underline">
                          {item.code || '--'}
                        </StockCodeLink>
                      </div>
                      <div className="text-xs text-gray-500">建仓日：{displayText(item.buy_date)}</div>
                    </td>
                    <td className="py-3 pr-4 text-gray-700">{displayText(item.sector)}</td>
                    <td className="py-3 pr-4 text-gray-700">{displayText(item.role_text)}</td>
                    <td className="py-3 pr-4">
                      <StatusPill kind={item.position_status} label={displayText(item.position_status_text)} />
                    </td>
                    <td className="py-3 pr-4 text-gray-900">{formatPrice(item.buy_price)}</td>
                    <td className="py-3 pr-4 text-gray-900">{formatPrice(item.current_price)}</td>
                    <td className={`py-3 pr-4 ${signedClass(item.pnl_pct)}`}>{formatPercent(item.pnl_pct, { signed: true })}</td>
                    <td className="py-3 pr-4 text-gray-700">{displayText(item.near_top_text)}</td>
                    <td className="py-3 pr-4 text-gray-700">{displayText(item.holding_days)}</td>
                    <td className="py-3 pr-4">
                      <StatusPill kind={item.exit_risk} label={displayText(item.exit_risk_text)} />
                    </td>
                    <td className="py-3 pr-4 text-gray-600">{displayText(item.summary_text)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-gray-500">当前无持仓</div>
        )}
      </div>

      <div id="ledger-section" className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <FileText size={20} />
          交易台账
        </h3>
        {tradeLedger.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500">
                  <th className="py-2 pr-4">交易日</th>
                  <th className="py-2 pr-4">动作</th>
                  <th className="py-2 pr-4">股票</th>
                  <th className="py-2 pr-4">板块</th>
                  <th className="py-2 pr-4">成交价</th>
                  <th className="py-2 pr-4">数量</th>
                  <th className="py-2 pr-4">原因</th>
                  <th className="py-2 pr-4">来源</th>
                  <th className="py-2 pr-4">对应信号日</th>
                </tr>
              </thead>
              <tbody>
                {tradeLedger.map((item) => (
                  <tr key={`${item.action}-${item.code}-${item.trade_date}`} className="border-b border-gray-100 last:border-b-0">
                    <td className="py-3 pr-4 text-gray-900">{displayText(item.trade_date)}</td>
                    <td className="py-3 pr-4">
                      <StatusPill kind={item.action} label={displayText(item.action_text)} />
                    </td>
                    <td className="py-3 pr-4">
                      <div className="font-medium text-gray-900">
                        {displayText(item.name)}{' '}
                        <StockCodeLink code={item.code} className="text-gray-500 hover:text-blue-600 hover:underline">
                          {item.code || '--'}
                        </StockCodeLink>
                      </div>
                    </td>
                    <td className="py-3 pr-4 text-gray-700">{displayText(item.sector)}</td>
                    <td className="py-3 pr-4 text-gray-900">{formatPrice(item.price)}</td>
                    <td className="py-3 pr-4 text-gray-700">{displayText(item.size_or_weight)}</td>
                    <td className="py-3 pr-4 text-gray-600">
                      <div>{displayText(item.reason_text)}</div>
                      <div className="text-xs text-gray-400">tag: {displayText(item.reason_tag)}</div>
                    </td>
                    <td className="py-3 pr-4">
                      <StatusPill kind={item.source} label={displayText(item.source_text)} />
                    </td>
                    <td className="py-3 pr-4 text-gray-500">{displayText(item.signal_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-gray-500">暂无交易记录</div>
        )}
      </div>
    </div>
  );
}
