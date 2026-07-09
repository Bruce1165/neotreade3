import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const mockGetDataStatus = vi.fn()

vi.mock('./services/api', () => ({
  getDataStatus: (...args) => mockGetDataStatus(...args),
}))

vi.mock('./pages/Overview', () => ({
  default: () => <div>Overview Page</div>,
}))

vi.mock('./pages/OpsCenter', () => ({
  default: () => <div>OpsCenter Page</div>,
}))

vi.mock('./pages/Screeners', () => ({
  default: () => <div>Screeners Page</div>,
}))

vi.mock('./pages/StockCheck', () => ({
  default: () => <div>StockCheck Page</div>,
}))

vi.mock('./pages/Lowfreq', () => ({
  default: () => <div>Lowfreq Page</div>,
}))

vi.mock('./pages/LowfreqBacktestReport', () => ({
  default: () => <div>LowfreqBacktestReport Page</div>,
}))

vi.mock('./pages/MarketIntelligence', () => ({
  default: () => <div>MarketIntelligence Page</div>,
}))

describe('App tushare banner', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/')
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('does not render tushare banner when credit is sufficient', async () => {
    mockGetDataStatus.mockResolvedValue({
      latest_available_date: '2026-06-17',
      tushare: {
        credit_insufficient: false,
      },
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Overview Page')).toBeTruthy()
    })

    expect(screen.queryByText('Tushare 黄旗：')).toBeNull()
    expect(screen.queryByText('查看详细信息')).toBeNull()
  })

  it('renders summary copy and details entry when tushare credit is insufficient', async () => {
    mockGetDataStatus.mockResolvedValue({
      latest_available_date: '2026-06-17',
      tushare: {
        credit_insufficient: true,
        last_credit_insufficient_at: '2026-07-05T14:20:00Z',
        last_credit_insufficient_api: '/api/daily-bars',
        last_tushare_ok_at: '2026-07-04T09:30:00Z',
        last_tushare_ok_api: '/api/trading-day',
      },
    })

    render(<App />)

    expect(await screen.findByText('Tushare 黄旗：')).toBeTruthy()
    expect(screen.getByText('检测到 Tushare 积分不足，日线主源可能受影响。')).toBeTruthy()
    expect(screen.getByText('查看详细信息')).toBeTruthy()
    expect(screen.queryByText('last_insufficient=2026-07-05T14:20:00Z')).toBeNull()
    expect(screen.queryByText('api=/api/daily-bars')).toBeNull()
  })
})
