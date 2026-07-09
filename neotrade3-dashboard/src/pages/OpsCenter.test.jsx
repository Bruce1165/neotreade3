import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import OpsCenter from './OpsCenter'

const mockUseApp = vi.fn()
const mockGetOpsCenterSummary = vi.fn()

vi.mock('../context/AppContext', () => ({
  useApp: () => mockUseApp(),
}))

vi.mock('../services/api', () => ({
  getOpsCenterSummary: (...args) => mockGetOpsCenterSummary(...args),
}))

vi.mock('../components/DateSelector', () => ({
  default: ({ onRefresh, loading }) => (
    <button data-testid="date-selector-stub" onClick={onRefresh} disabled={loading}>
      DateSelector
    </button>
  ),
}))

function buildPayload() {
  return {
    meta: {
      as_of_date: '2026-06-09',
      latest_trade_date: '2026-06-09',
      latest_data_date: '2026-06-09',
      snapshot_generated_at: '2026-06-09T08:10:00Z',
    },
    inspection: {
      overall_status: 'ok',
      overall_status_text: '正常',
      overall_status_kind: 'active',
      risk_level: 'low',
      risk_level_text: '低风险',
      risk_level_kind: 'watch',
      summary_text: '2026-06-09 巡检正常，数据已追平到目标交易日，关键链路未发现摘要层异常。',
    },
    checklist: [
      {
        item_id: 'data_freshness',
        item_label: '数据追平',
        status: 'ok',
        status_text: '正常',
        status_kind: 'active',
        summary: '最新数据日 2026-06-09，目标交易日 2026-06-09。',
      },
      {
        item_id: 'screeners_bulk_run',
        item_label: '筛选器批跑',
        status: 'ok',
        status_text: '正常',
        status_kind: 'active',
        summary: '批跑状态 ok，记录数 6。',
      },
    ],
    pipeline_steps: [
      {
        step_id: 'authoritative_update',
        step_label: '权威行情更新',
        status: 'ok',
        status_text: '正常',
        status_kind: 'active',
        finished_at: '2026-06-09T08:10:00Z',
      },
      {
        step_id: 'screeners_bulk_run',
        step_label: '筛选器批跑',
        status: 'ok',
        status_text: '正常',
        status_kind: 'active',
        finished_at: '2026-06-09T08:05:00Z',
      },
    ],
    exceptions: [],
    evidence: {
      latest_run_date: '2026-06-09',
      latest_data_date: '2026-06-09',
      expected_trade_date: '2026-06-09',
      overdue_shifted_count: 2,
      inconsistency_count: 0,
      pending_intents_after: 3,
    },
  }
}

describe('OpsCenter', () => {
  beforeEach(() => {
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders ops center summary from authoritative endpoint', async () => {
    mockGetOpsCenterSummary.mockResolvedValue(buildPayload())

    render(<OpsCenter />)

    await waitFor(() => {
      expect(mockGetOpsCenterSummary).toHaveBeenCalledWith('2026-06-09')
    })

    expect(screen.getByText('运维中心')).toBeTruthy()
    expect(screen.getByText('每日巡检')).toBeTruthy()
    expect(screen.getByText('关键链路状态')).toBeTruthy()
    expect(screen.getByText('异常处置摘要')).toBeTruthy()
    expect(screen.getAllByText('低风险').length).toBeGreaterThan(0)
    expect(screen.getByText('权威行情更新')).toBeTruthy()
    expect(screen.getByText('当前无异常摘要')).toBeTruthy()
  })

  it('renders exception summaries returned by backend', async () => {
    const payload = buildPayload()
    payload.inspection = {
      ...payload.inspection,
      overall_status: 'critical',
      overall_status_text: '严重异常',
      overall_status_kind: 'avoid',
      risk_level: 'severe',
      risk_level_text: '严重风险',
      risk_level_kind: 'avoid',
      summary_text: '2026-06-09 巡检发现 1 条异常摘要，当前风险等级为 严重风险。',
    }
    payload.exceptions = [
      {
        exception_id: 'authoritative_update_failed',
        title: '权威行情更新失败',
        severity: 'severe',
        severity_text: '严重',
        severity_kind: 'avoid',
        impact_scope: '权威行情',
        summary: '当日权威行情更新步骤返回失败，主链数据更新不可视为完成。',
        next_action: '检查权威更新步骤输出与数据源可用性。',
      },
    ]
    mockGetOpsCenterSummary.mockResolvedValue(payload)

    render(<OpsCenter />)

    await waitFor(() => {
      expect(screen.getByText('权威行情更新失败')).toBeTruthy()
    })

    expect(screen.getByText('影响范围：')).toBeTruthy()
    expect(screen.getByText('权威行情')).toBeTruthy()
    expect(screen.getByText('下一步：')).toBeTruthy()
    expect(screen.getByText('检查权威更新步骤输出与数据源可用性。')).toBeTruthy()
  })

  it('shows page error when summary request fails', async () => {
    mockGetOpsCenterSummary.mockRejectedValue(new Error('运维中心聚合失败'))

    render(<OpsCenter />)

    await waitFor(() => {
      expect(screen.getByText('运维中心聚合失败')).toBeTruthy()
    })

    expect(screen.getByText('运维中心')).toBeTruthy()
  })
})
