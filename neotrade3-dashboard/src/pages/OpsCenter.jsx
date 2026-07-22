import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, AlertTriangle, ListChecks, ShieldAlert } from 'lucide-react';

import DateSelector from '../components/DateSelector';
import MetricCard from '../components/MetricCard';
import PageHeader from '../components/PageHeader';
import StatusPill from '../components/StatusPill';
import { useApp } from '../context/AppContext';
import { createBlockState, rejectBlock, resolveBlock, startBlock } from '../services/asyncBlocks';
import { getOpsCenterSummary } from '../services/api';

function displayText(value) {
  const text = String(value ?? '').trim();
  return text || '--';
}

export default function OpsCenter() {
  const { selectedDate } = useApp();
  const [block, setBlock] = useState(createBlockState());

  const fetchData = useCallback(async () => {
    setBlock((prev) => startBlock(prev, true));
    try {
      const payload = await getOpsCenterSummary(selectedDate);
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
  const inspection = payload.inspection || {};
  const checklist = Array.isArray(payload.checklist) ? payload.checklist : [];
  const pipelineSteps = Array.isArray(payload.pipeline_steps) ? payload.pipeline_steps : [];
  const exceptions = Array.isArray(payload.exceptions) ? payload.exceptions : [];
  const evidence = payload.evidence || {};
  const loading = block.loading;
  const pageError = !block.loaded && block.error ? block.error : null;
  const runningEvidenceItems = [
    {
      label: '快照生成',
      value: meta.snapshot_generated_at,
    },
    {
      label: '最近任务',
      value: evidence.latest_run_date,
    },
    {
      label: '目标交易日',
      value: evidence.expected_trade_date,
    },
    {
      label: '顺延待处理',
      value: evidence.overdue_shifted_count,
    },
    {
      label: '收口异常',
      value: evidence.inconsistency_count,
    },
    {
      label: '日后待执行',
      value: evidence.pending_intents_after,
    },
  ];

  return (
    <div className="space-y-6">
      <DateSelector onRefresh={fetchData} loading={loading} />

      <PageHeader title="运维中心" subtitle={displayText(inspection.summary_text)} onRefresh={fetchData} loading={loading} />

      {pageError ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3 text-red-700">
          <AlertCircle size={20} />
          <span>{pageError}</span>
        </div>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard
          title="巡检日期"
          value={displayText(meta.as_of_date)}
          subtitle="当前运维快照查询日期"
        />
        <MetricCard
          title="总状态"
          value={displayText(inspection.overall_status_text)}
          subtitle={displayText(inspection.summary_text)}
          badge={<StatusPill kind={inspection.overall_status_kind} label={displayText(inspection.overall_status_text)} />}
        />
        <MetricCard
          title="风险等级"
          value={displayText(inspection.risk_level_text)}
          subtitle="由后端统一判定"
          badge={<StatusPill kind={inspection.risk_level_kind} label={displayText(inspection.risk_level_text)} />}
        />
        <MetricCard
          title="最新数据日"
          value={displayText(meta.latest_data_date)}
          subtitle={`最新交易日 ${displayText(meta.latest_trade_date)}`}
        />
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <ListChecks size={20} className="text-blue-600" />
          每日巡检
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-4">
          {checklist.map((item) => (
            <div key={item.item_id} className="rounded-lg border border-gray-100 bg-gray-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium text-gray-900">{displayText(item.item_label)}</div>
                <StatusPill kind={item.status_kind} label={displayText(item.status_text)} />
              </div>
              <div className="text-sm text-gray-600 mt-3 leading-6">{displayText(item.summary)}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900">关键链路状态</h3>
        {pipelineSteps.length ? (
          <div className="overflow-x-auto mt-4">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2 pr-4">步骤</th>
                  <th className="py-2 pr-4">状态</th>
                  <th className="py-2 pr-4">完成时间</th>
                </tr>
              </thead>
              <tbody>
                {pipelineSteps.map((step) => (
                  <tr key={step.step_id} className="border-b last:border-b-0">
                    <td className="py-3 pr-4 text-gray-900">{displayText(step.step_label)}</td>
                    <td className="py-3 pr-4">
                      <StatusPill kind={step.status_kind} label={displayText(step.status_text)} />
                    </td>
                    <td className="py-3 pr-4 text-gray-600">{displayText(step.finished_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-gray-500 mt-4">暂无关键链路状态</div>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <ShieldAlert size={20} className="text-red-600" />
          异常处置摘要
        </h3>
        {exceptions.length ? (
          <div className="space-y-4 mt-4">
            {exceptions.map((item) => (
              <div key={item.exception_id} className="rounded-lg border border-red-100 bg-red-50 p-4">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={18} className="text-red-600" />
                    <div className="font-medium text-gray-900">{displayText(item.title)}</div>
                  </div>
                  <StatusPill kind={item.severity_kind} label={displayText(item.severity_text)} />
                </div>
                <div className="text-sm text-gray-600 mt-3">
                  影响范围：<span className="text-gray-900">{displayText(item.impact_scope)}</span>
                </div>
                <div className="text-sm text-gray-700 mt-2 leading-6">{displayText(item.summary)}</div>
                <div className="text-sm text-gray-600 mt-2">
                  下一步：<span className="text-gray-900">{displayText(item.next_action)}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-gray-500 mt-4">当前无异常摘要</div>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900">运行证据</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-4">
          {runningEvidenceItems.map((item) => (
            <div key={item.label} className="rounded-lg border border-gray-100 bg-gray-50 p-4">
              <div className="text-sm text-gray-500">{item.label}</div>
              <div className="mt-2 text-sm font-medium text-gray-900">{displayText(item.value)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
