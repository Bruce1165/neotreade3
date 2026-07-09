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
  default: () => <div>DateSelector</div>,
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
      summary_text: '2026-06-09 巡检正常',
    },
    checklist: [],
    pipeline_steps: [],
    exceptions: [],
    evidence: {
      latest_run_date: '2026-06-09',
      expected_trade_date: '2026-06-10',
      overdue_shifted_count: 2,
      inconsistency_count: 0,
      pending_intents_after: 3,
    },
  }
}

describe('OpsCenter footer contract', () => {
  beforeEach(() => {
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders running evidence block with current footer fields', async () => {
    mockGetOpsCenterSummary.mockResolvedValue(buildPayload())

    render(<OpsCenter />)

    await waitFor(() => {
      expect(mockGetOpsCenterSummary).toHaveBeenCalledWith('2026-06-09')
    })

    expect(screen.getByText('运行证据')).toBeTruthy()
    expect(screen.getByText('快照生成')).toBeTruthy()
    expect(screen.getByText('2026-06-09T08:10:00Z')).toBeTruthy()
    expect(screen.getByText('最近任务')).toBeTruthy()
    expect(screen.getAllByText('2026-06-09').length).toBeGreaterThan(0)
    expect(screen.getByText('目标交易日')).toBeTruthy()
    expect(screen.getByText('2026-06-10')).toBeTruthy()
    expect(screen.getByText('顺延待处理')).toBeTruthy()
    expect(screen.getByText('2')).toBeTruthy()
    expect(screen.getByText('收口异常')).toBeTruthy()
    expect(screen.getAllByText('0').length).toBeGreaterThan(0)
    expect(screen.getByText('日后待执行')).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy()
  })

  it('falls back to placeholder when footer fields are missing', async () => {
    const payload = buildPayload()
    payload.meta = {
      ...payload.meta,
      snapshot_generated_at: '',
    }
    payload.evidence = {
      latest_run_date: '',
      expected_trade_date: null,
      overdue_shifted_count: undefined,
      inconsistency_count: '',
      pending_intents_after: null,
    }
    mockGetOpsCenterSummary.mockResolvedValue(payload)

    render(<OpsCenter />)

    await waitFor(() => {
      expect(screen.getByText('运行证据')).toBeTruthy()
    })

    expect(screen.getAllByText('--')).toHaveLength(6)
  })
})
