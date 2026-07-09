import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const mockGetDataStatus = vi.fn()

vi.mock('./context/AppContext', () => ({
  AppProvider: ({ children }) => children,
}))

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

describe('App lowfreq backtest report route', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/lowfreq/backtest-reports/report-1')
    mockGetDataStatus.mockResolvedValue({
      latest_available_date: '2026-06-17',
      tushare: {
        credit_insufficient: false,
      },
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders lowfreq backtest report page on detail route', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('LowfreqBacktestReport Page')).toBeTruthy()
    })

    expect(screen.getByText('团队控制台：审阅 / 监控 / 复盘')).toBeTruthy()
    expect(screen.getByText('LowfreqBacktestReport Page')).toBeTruthy()
  })
})
