import { useCallback, useEffect, useState } from 'react';
import { Play, Filter, AlertCircle, CheckCircle, Clock, Download, Loader2, Settings, Save } from 'lucide-react';
import { useApp } from '../context/AppContext';
import DateSelector from '../components/DateSelector';
import { fetchApi } from '../services/api';
import { createBlockState, rejectBlock, resolveBlock, startBlock } from '../services/asyncBlocks';

// 状态中文映射
const STATUS_CN = {
  success: '成功',
  completed: '已完成',
  failed: '失败',
  running: '运行中',
  planned: '计划中',
};

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

function flattenSchemaFields(schema, prefix) {
  const root = schema && typeof schema === 'object' ? schema : {};
  const basePrefix = prefix ? String(prefix) : '';
  const fields = [];
  const props =
    root.properties && typeof root.properties === 'object' ? root.properties : {};

  for (const [key, child] of Object.entries(props)) {
    const path = basePrefix ? `${basePrefix}.${key}` : String(key);
    const childSchema = child && typeof child === 'object' ? child : {};
    const type = childSchema.type;
    if (type === 'object') {
      fields.push(...flattenSchemaFields(childSchema, path));
      continue;
    }
    const childProps =
      childSchema.properties && typeof childSchema.properties === 'object'
        ? childSchema.properties
        : null;
    if (childProps) {
      fields.push(...flattenSchemaFields(childSchema, path));
      continue;
    }
    const displayName = String(
      childSchema.x_display_name || childSchema.title || ''
    ).trim();
    fields.push({
      path,
      schema: childSchema,
      display_name: displayName,
      description: String(childSchema.description || '').trim(),
      unit: String(childSchema.x_unit || '').trim(),
      group: String(childSchema.x_group || '').trim(),
      min: childSchema.x_min,
      max: childSchema.x_max,
      step: childSchema.x_step,
    });
  }

  fields.sort((a, b) => String(a.path).localeCompare(String(b.path)));
  return fields;
}

function getByPath(obj, path) {
  if (!obj || typeof obj !== 'object') return undefined;
  const parts = String(path || '')
    .split('.')
    .filter((v) => v);
  let cur = obj;
  for (const part of parts) {
    if (!cur || typeof cur !== 'object') return undefined;
    cur = cur[part];
  }
  return cur;
}

function setByPath(obj, path, value) {
  const parts = String(path || '')
    .split('.')
    .filter((v) => v);
  let cur = obj;
  for (let i = 0; i < parts.length; i += 1) {
    const part = parts[i];
    if (i === parts.length - 1) {
      cur[part] = value;
      return;
    }
    if (!cur[part] || typeof cur[part] !== 'object') {
      cur[part] = {};
    }
    cur = cur[part];
  }
}

function parseParamValue(raw, schema) {
  const trimmed = String(raw ?? '').trim();
  if (!trimmed) return { ok: true, value: undefined };
  if (trimmed.toLowerCase() === 'null') return { ok: true, value: null };
  const t = schema && schema.type ? schema.type : null;
  const types = Array.isArray(t) ? t : t ? [t] : [];
  if (types.includes('number') || types.includes('integer')) {
    const n = Number(trimmed);
    if (!Number.isFinite(n)) return { ok: false, value: null };
    if (types.includes('integer')) return { ok: true, value: Math.trunc(n) };
    return { ok: true, value: n };
  }
  if (types.includes('boolean')) {
    const norm = trimmed.toLowerCase();
    if (norm === 'true' || norm === '1' || norm === 'yes' || norm === 'y') {
      return { ok: true, value: true };
    }
    if (norm === 'false' || norm === '0' || norm === 'no' || norm === 'n') {
      return { ok: true, value: false };
    }
    return { ok: false, value: null };
  }
  return { ok: true, value: trimmed };
}

export default function Screeners() {
  const { selectedDate } = useApp();
  const [activeTab, setActiveTab] = useState('runs');
  const [error, setError] = useState(null);
  const [runLoading, setRunLoading] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [blocks, setBlocks] = useState({
    screeners: createBlockState(),
    runs: createBlockState(),
    bulkRuns: createBlockState(),
  });
  const [configLoading, setConfigLoading] = useState(false);
  const [configError, setConfigError] = useState(null);
  const [configStatus, setConfigStatus] = useState(null);
  const [selectedScreenerId, setSelectedScreenerId] = useState('');
  const [configPayload, setConfigPayload] = useState(null);
  const [configFilter, setConfigFilter] = useState('');
  const [paramInputs, setParamInputs] = useState({});
  const [saveLoading, setSaveLoading] = useState(false);

  const loadScreenersBlock = useCallback(async () => {
    setBlocks((prev) => ({ ...prev, screeners: startBlock(prev.screeners, true) }));
    try {
      const screeners = await fetchApi(`/api/screeners?date=${encodeURIComponent(selectedDate)}`, {}, { timeoutMs: 45000 });
      setBlocks((prev) => ({ ...prev, screeners: resolveBlock(screeners) }));
    } catch (err) {
      setBlocks((prev) => ({ ...prev, screeners: rejectBlock(prev.screeners, err, true) }));
    }
  }, [selectedDate]);

  const loadRunsBlock = useCallback(async () => {
    setBlocks((prev) => ({ ...prev, runs: startBlock(prev.runs, true) }));
    try {
      const runs = await fetchApi(`/api/screeners/runs?date=${encodeURIComponent(selectedDate)}`, {}, { timeoutMs: 45000 });
      setBlocks((prev) => ({ ...prev, runs: resolveBlock(runs) }));
    } catch (err) {
      setBlocks((prev) => ({ ...prev, runs: rejectBlock(prev.runs, err, true) }));
    }
  }, [selectedDate]);

  const loadBulkRunsBlock = useCallback(async () => {
    setBlocks((prev) => ({ ...prev, bulkRuns: startBlock(prev.bulkRuns, true) }));
    try {
      const bulkRuns = await fetchApi('/api/screeners/bulk-runs?limit=1', {}, { timeoutMs: 60000 });
      setBlocks((prev) => ({ ...prev, bulkRuns: resolveBlock(bulkRuns) }));
    } catch (err) {
      setBlocks((prev) => ({ ...prev, bulkRuns: rejectBlock(prev.bulkRuns, err, true) }));
    }
  }, []);

  const fetchData = useCallback(async () => {
    setError(null);
    void loadScreenersBlock();
    void loadRunsBlock();
    void loadBulkRunsBlock();
  }, [loadBulkRunsBlock, loadRunsBlock, loadScreenersBlock]);

  // 一键运行全部筛选器
  const handleRunAll = async () => {
    setRunLoading(true);
    setRunResult(null);
    setError(null);
    
    try {
      const result = await fetchApi(
        '/api/screeners/bulk-run',
        {
          method: 'POST',
          body: JSON.stringify({
            date: selectedDate,
            requested_by: 'dashboard.react',
          }),
        },
        { timeoutMs: 60000 }
      );
      setRunResult(result);
      
      // 刷新数据
      await fetchData();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunLoading(false);
    }
  };

  // 下载结果（按: date + screener_id）
  const handleDownload = async (targetDate, screenerId) => {
    try {
      const response = await fetch(
        `/api/screeners/runs/${encodeURIComponent(targetDate)}/${encodeURIComponent(
          screenerId
        )}/download.csv`
      );
      if (!response.ok) {
        throw new Error(`下载失败：HTTP ${response.status}`);
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `screener_${screenerId}_${targetDate}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err?.message || '下载失败');
    }
  };

  const loadScreenerConfig = async (screenerId) => {
    setConfigLoading(true);
    setConfigError(null);
    setConfigStatus(null);
    try {
      const payload = await fetchApi(
        `/api/screeners/config/${encodeURIComponent(screenerId)}`,
        {},
        { timeoutMs: 45000 }
      );
      setConfigPayload(payload);

      const cfg = payload?.screener_config || {};
      const schema = cfg?.schema || {};
      const fields = flattenSchemaFields(schema, '');
      const current = cfg?.current_parameters || {};
      const nextInputs = {};
      for (const field of fields) {
        const v = getByPath(current, field.path);
        nextInputs[field.path] = v === undefined ? '' : String(v);
      }
      setParamInputs(nextInputs);
      setConfigStatus(
        `已加载：${cfg?.screener_id || screenerId}${
          cfg?.updated_at ? ` · 更新于 ${cfg.updated_at}` : ''
        }`
      );
    } catch (err) {
      setConfigError(err.message);
      setConfigPayload(null);
      setParamInputs({});
    } finally {
      setConfigLoading(false);
    }
  };

  const handleSaveConfig = async () => {
    setSaveLoading(true);
    setConfigError(null);
    setConfigStatus(null);
    try {
      if (!configPayload?.screener_config) {
        throw new Error('配置尚未加载');
      }
      const cfg = configPayload.screener_config;
      const schema = cfg?.schema || {};
      const fields = flattenSchemaFields(schema, '');
      const currentParameters = {};
      for (const field of fields) {
        const raw = String(paramInputs[field.path] ?? '');
        const parsed = parseParamValue(raw, field.schema);
        if (!parsed.ok) {
          throw new Error(`参数格式不合法：${field.path}`);
        }
        if (parsed.value === undefined) continue;
        setByPath(currentParameters, field.path, parsed.value);
      }
      const payload = await fetchApi(
        `/api/screeners/config/${encodeURIComponent(cfg.screener_id)}`,
        {
          method: 'POST',
          body: JSON.stringify({
            current_parameters: currentParameters,
            requested_by: 'dashboard.react',
          }),
        }
      );
      setConfigPayload(payload);
      setConfigStatus('保存成功');
      await fetchData();
    } catch (err) {
      setConfigError(err.message);
    } finally {
      setSaveLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const loading = Object.values(blocks).some((block) => block.loading);
  const screenerList = blocks.screeners.data?.screeners_registry?.screeners || [];
  const screenerRuns = blocks.runs.data?.screener_runs || [];
  const latestBulk = Array.isArray(blocks.bulkRuns.data?.bulk_runs)
    ? blocks.bulkRuns.data.bulk_runs[0]
    : null;
  const latestBulkDate = latestBulk?.target_date || '--';
  const pageError = error || (!blocks.screeners.loaded && blocks.screeners.error ? blocks.screeners.error : null);
  const latestRunByScreenerId = (() => {
    const m = new Map();
    for (const run of screenerRuns) {
      if (!run || typeof run !== 'object') continue;
      const id = String(run.screener_id || '').trim();
      if (!id) continue;
      m.set(id, run);
    }
    return m;
  })();
  const resolveRunDownloadDate = (runLike) => {
    const targetDate = String(runLike?.target_date || '').trim();
    return targetDate || selectedDate;
  };
  const filteredScreeners = configFilter.trim()
    ? screenerList.filter((s) =>
        `${s.display_name || ''} ${s.screener_id || ''}`
          .toLowerCase()
          .includes(configFilter.trim().toLowerCase())
      )
    : screenerList;

  const cfg = configPayload?.screener_config || null;
  const cfgSchema = cfg?.schema || {};
  const cfgDefaultParams = cfg?.default_parameters || {};
  const cfgCurrentParams = cfg?.current_parameters || {};
  const cfgFields = cfg ? flattenSchemaFields(cfgSchema, '') : [];
  const cfgProps =
    cfgSchema && typeof cfgSchema === 'object' && cfgSchema.properties
      ? cfgSchema.properties
      : {};
  const groups = (() => {
    const grouped = new Map();
    for (const field of cfgFields) {
      const path = String(field.path || '');
      const parts = path.split('.').filter((v) => v);
      const explicitGroup = String(field.group || '').trim();
      const groupKey = explicitGroup ? explicitGroup : parts.length <= 1 ? '基本' : parts[0];
      if (!grouped.has(groupKey)) grouped.set(groupKey, []);
      grouped.get(groupKey).push(field);
    }
    const keys = Array.from(grouped.keys()).sort((a, b) => String(a).localeCompare(String(b)));
    if (keys.includes('基本')) {
      keys.splice(keys.indexOf('基本'), 1);
      keys.unshift('基本');
    }
    return { grouped, keys };
  })();

  return (
    <div className="space-y-6">
      {/* Date Selector */}
      <DateSelector onRefresh={fetchData} loading={loading} />

      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <h2 className="text-2xl font-bold text-gray-900">筛选器管理</h2>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="text-sm text-gray-500">本机访问默认放行，无需 API Key</div>
          <button
            onClick={handleRunAll}
            disabled={runLoading || loading}
            className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {runLoading ? <Loader2 size={20} className="animate-spin" /> : <Play size={20} />}
            {runLoading ? '运行中...' : '一键运行全部'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-6">
          <button
            onClick={() => setActiveTab('runs')}
            className={`flex items-center gap-2 py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'runs'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Clock size={18} />
            运行与结果
          </button>
          <button
            onClick={() => setActiveTab('config')}
            className={`flex items-center gap-2 py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'config'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Settings size={18} />
            参数配置
          </button>
        </nav>
      </div>

      {/* Error Display */}
      {pageError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3 text-red-700">
          <AlertCircle size={20} />
          <span>{pageError}</span>
        </div>
      )}

      {activeTab === 'runs' && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="text-sm text-gray-500 mb-1">总筛选器</div>
              <div className="text-2xl font-bold text-gray-900">{screenerList.length}</div>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="text-sm text-gray-500 mb-1">已启用</div>
              <div className="text-2xl font-bold text-green-600">{screenerList.filter(s => s.enabled).length}</div>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="text-sm text-gray-500 mb-1">当日运行记录</div>
              <div className="text-2xl font-bold text-blue-600">{screenerRuns.length}</div>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="text-sm text-gray-500 mb-1">最近批量运行日期</div>
              <div className="text-2xl font-bold text-purple-600">
                {latestBulkDate}
              </div>
              {blocks.bulkRuns.error && !blocks.bulkRuns.loaded ? (
                <div className="mt-2 text-sm text-red-700">
                  {blocks.bulkRuns.error}
                </div>
              ) : null}
            </div>
          </div>

          {/* Screeners Grid */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Filter size={20} />
              筛选器列表
            </h3>
            {blocks.screeners.loading && !blocks.screeners.loaded ? (
              <BlockMessage message="筛选器列表加载中..." />
            ) : blocks.screeners.error && !blocks.screeners.loaded ? (
              <BlockMessage tone="red" message={blocks.screeners.error} onRetry={loadScreenersBlock} />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {screenerList.map((screener) => (
                  <div key={screener.screener_id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-start justify-between mb-2 gap-2">
                      <h4 className="font-medium text-gray-900">{screener.display_name}</h4>
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        screener.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
                      }`}>
                        {screener.enabled ? '启用' : '禁用'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 mb-3 line-clamp-2">{screener.notes}</p>
                    <div className="flex flex-wrap gap-1 mb-3">
                      {screener.tags?.map((tag, idx) => (
                        <span key={idx} className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">
                          {tag}
                        </span>
                      ))}
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-xs text-gray-400 font-mono truncate">{screener.screener_id}</div>
                      <button
                        onClick={() =>
                          handleDownload(
                            resolveRunDownloadDate(
                              latestRunByScreenerId.get(String(screener.screener_id || '').trim()),
                            ),
                            screener.screener_id,
                          )
                        }
                        disabled={!latestRunByScreenerId.has(String(screener.screener_id || '').trim())}
                        className="flex items-center gap-1 px-3 py-1 text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded disabled:text-gray-400 disabled:hover:bg-transparent disabled:cursor-not-allowed text-sm transition-colors"
                      >
                        <Download size={14} />
                        下载 CSV
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Runs */}
          {(screenerRuns.length > 0 || blocks.runs.loading || (blocks.runs.error && !blocks.runs.loaded)) && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Clock size={20} />
                最近运行记录
              </h3>
              {blocks.runs.loading && !blocks.runs.loaded ? (
                <BlockMessage message="最近运行记录加载中..." />
              ) : blocks.runs.error && !blocks.runs.loaded ? (
                <BlockMessage tone="red" message={blocks.runs.error} onRetry={loadRunsBlock} />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">筛选器</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">运行时间</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">状态</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">命中数</th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {screenerRuns.slice(0, 10).map((run, index) => (
                        <tr key={index} className="border-b border-gray-100">
                          <td className="py-3 px-4 text-gray-900">{run.screener_id}</td>
                          <td className="py-3 px-4 text-gray-500">{run.finished_at || run.requested_at || '--'}</td>
                          <td className="py-3 px-4">
                            <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-sm ${
                              run.status === 'success' || run.status === 'completed'
                                ? 'bg-green-100 text-green-700' 
                                : run.status === 'failed'
                                ? 'bg-red-100 text-red-700'
                                : run.status === 'running'
                                ? 'bg-blue-100 text-blue-700'
                                : 'bg-yellow-100 text-yellow-700'
                            }`}>
                              {run.status === 'success' || run.status === 'completed' ? <CheckCircle size={14} /> : 
                               run.status === 'running' ? <Loader2 size={14} className="animate-spin" /> : <AlertCircle size={14} />}
                              {STATUS_CN[run.status] || run.status}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-gray-900">{run.picks_count || 0}</td>
                          <td className="py-3 px-4">
                            {run.picks_count > 0 && (
                              <button
                                onClick={() =>
                                  handleDownload(resolveRunDownloadDate(run), run.screener_id)
                                }
                                className="flex items-center gap-1 px-2 py-1 text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded transition-colors"
                              >
                                <Download size={14} />
                                <span className="text-sm">下载 CSV</span>
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {activeTab === 'config' && (
        <div className="space-y-6">
          <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <Settings size={20} />
                参数配置
              </h3>
              <button
                onClick={handleSaveConfig}
                disabled={saveLoading || configLoading || !cfg}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {saveLoading ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
                保存配置
              </button>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <input
                type="text"
                value={configFilter}
                onChange={(e) => setConfigFilter(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-72 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="搜索筛选器（名称/ID）"
              />
              <select
                value={selectedScreenerId}
                onChange={async (e) => {
                  const id = String(e.target.value || '');
                  setSelectedScreenerId(id);
                  if (id) {
                    await loadScreenerConfig(id);
                  } else {
                    setConfigPayload(null);
                    setParamInputs({});
                    setConfigStatus(null);
                    setConfigError(null);
                  }
                }}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm min-w-[320px] focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">选择筛选器…（{filteredScreeners.length}）</option>
                {filteredScreeners.map((s) => (
                  <option key={s.screener_id} value={s.screener_id}>
                    {s.display_name || s.screener_id}（{s.screener_id}）
                  </option>
                ))}
              </select>
            </div>

            {configStatus && (
              <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                {configStatus}
              </div>
            )}
            {configError && (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {configError}
              </div>
            )}
            {configLoading && (
              <div className="text-sm text-gray-500">
                加载中...
              </div>
            )}
          </div>

          {cfg && cfgFields.length === 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              该筛选器没有可配置参数。
            </div>
          )}

          {cfg && cfgFields.length > 0 && (
            <div className="space-y-4">
              {groups.keys.map((groupKey, idx) => {
                const groupFields = groups.grouped.get(groupKey) || [];
                groupFields.sort((a, b) => String(a.path).localeCompare(String(b.path)));
                const rootSchema =
                  groupKey !== '基本' &&
                  Object.prototype.hasOwnProperty.call(cfgProps, groupKey)
                    ? cfgProps[groupKey]
                    : null;
                const groupLabel =
                  groupKey === '基本'
                    ? '基本参数'
                    : String(
                        rootSchema && typeof rootSchema === 'object'
                          ? rootSchema.x_display_name || rootSchema.title || groupKey
                          : groupKey
                      ).trim() || groupKey;

                return (
                  <details
                    key={groupKey}
                    className="bg-white rounded-lg border border-gray-200"
                    open={idx === 0}
                  >
                    <summary className="cursor-pointer px-6 py-4 font-medium text-gray-900">
                      {groupLabel}（{groupFields.length}）
                    </summary>
                    <div className="px-6 pb-6 overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-gray-200">
                            <th className="text-left py-3 pr-4 text-sm font-medium text-gray-700">参数</th>
                            <th className="text-left py-3 pr-4 text-sm font-medium text-gray-700">当前值</th>
                            <th className="text-left py-3 pr-4 text-sm font-medium text-gray-700">默认值</th>
                            <th className="text-left py-3 pr-4 text-sm font-medium text-gray-700">说明</th>
                          </tr>
                        </thead>
                        <tbody>
                          {groupFields.map((field) => {
                            const currentValue = getByPath(cfgCurrentParams, field.path);
                            const defaultValue = getByPath(cfgDefaultParams, field.path);
                            const descParts = [];
                            if (field.description) descParts.push(field.description);
                            if (field.unit) descParts.push(`单位：${field.unit}`);
                            const hasMin =
                              field.min !== undefined &&
                              field.min !== null &&
                              String(field.min) !== '';
                            const hasMax =
                              field.max !== undefined &&
                              field.max !== null &&
                              String(field.max) !== '';
                            if (hasMin || hasMax) {
                              const minLabel = hasMin ? String(field.min) : '?';
                              const maxLabel = hasMax ? String(field.max) : '?';
                              descParts.push(`范围：${minLabel} ~ ${maxLabel}`);
                            }
                            const hasStep =
                              field.step !== undefined &&
                              field.step !== null &&
                              String(field.step) !== '';
                            if (hasStep) descParts.push(`步进：${String(field.step)}`);
                            const label = String(field.display_name || '').trim();
                            return (
                              <tr key={field.path} className="border-b border-gray-100 align-top">
                                <td className="py-3 pr-4">
                                  {label ? (
                                    <div className="space-y-1">
                                      <div className="font-medium text-gray-900">{label}</div>
                                      <div className="text-xs text-gray-400 font-mono">{field.path}</div>
                                    </div>
                                  ) : (
                                    <div className="text-sm text-gray-900 font-mono">{field.path}</div>
                                  )}
                                </td>
                                <td className="py-3 pr-4">
                                  <input
                                    type="text"
                                    value={String(paramInputs[field.path] ?? (currentValue === undefined ? '' : String(currentValue)))}
                                    onChange={(e) =>
                                      setParamInputs((prev) => ({
                                        ...prev,
                                        [field.path]: e.target.value,
                                      }))
                                    }
                                    className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    placeholder="留空表示使用默认值；可输入 null"
                                  />
                                </td>
                                <td className="py-3 pr-4 text-sm text-gray-600">
                                  {defaultValue === undefined ? '--' : String(defaultValue)}
                                </td>
                                <td className="py-3 pr-4 text-sm text-gray-600">
                                  {descParts.length ? descParts.join('；') : '--'}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </details>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
