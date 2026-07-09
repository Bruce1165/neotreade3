import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
    <button onClick={onRefresh} disabled={loading} type="button">
      刷新运维中心
    </button>
  ),
}))

function buildPayload(selectedDate) {
  return {
    meta: {
      as_of_date: selectedDate,
      latest_trade_date: selectedDate,
      latest_data_date: selectedDate,
      snapshot_generated_at: `${selectedDate}T08:10:00Z`,
    },
    inspection: {
      overall_status: 'ok',
      overall_status_text: '正常',
      overall_status_kind: 'active',
      risk_level: 'low',
      risk_level_text: '低风险',
      risk_level_kind: 'watch',
      summary_text: `${selectedDate} 巡检正常`,
    },
    checklist: [],
    pipeline_steps: [],
    exceptions: [],
    evidence: {
      latest_run_date: selectedDate,
      latest_data_date: selectedDate,
      expected_trade_date: selectedDate,
      overdue_shifted_count: 0,
      inconsistency_count: 0,
      pending_intents_after: 0,
    },
  }
}

describe('OpsCenter reload behavior', () => {
  let selectedDate = '2026-06-09'

  beforeEach(() => {
    selectedDate = '2026-06-09'
    mockUseApp.mockImplementation(() => ({
      selectedDate,
    }))
    mockGetOpsCenterSummary.mockImplementation((date) => Promise.resolve(buildPayload(date)))
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('reloads current date when refresh is clicked', async () => {
    render(<OpsCenter />)

    await waitFor(() => {
      expect(mockGetOpsCenterSummary).toHaveBeenCalledTimes(1)
    })
    expect(mockGetOpsCenterSummary).toHaveBeenNthCalledWith(1, '2026-06-09')

    fireEvent.click(screen.getByRole('button', { name: '刷新运维中心' }))

    await waitFor(() => {
      expect(mockGetOpsCenterSummary).toHaveBeenCalledTimes(2)
    })
    expect(mockGetOpsCenterSummary).toHaveBeenNthCalledWith(2, '2026-06-09')
  })

  it('reloads new date when selectedDate changes', async () => {
    const { rerender } = render(<OpsCenter />)

    await waitFor(() => {
      expect(mockGetOpsCenterSummary).toHaveBeenCalledTimes(1)
    })
    expect(mockGetOpsCenterSummary).toHaveBeenNthCalledWith(1, '2026-06-09')

    selectedDate = '2026-06-10'
    rerender(<OpsCenter />)

    await waitFor(() => {
      expect(mockGetOpsCenterSummary).toHaveBeenCalledTimes(2)
    })
    expect(mockGetOpsCenterSummary).toHaveBeenNthCalledWith(2, '2026-06-10')
  })
})
