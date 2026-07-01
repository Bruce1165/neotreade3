import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const mockGetDataStatus = vi.fn()
const mockGetTradingDay = vi.fn()

vi.mock('./services/api', () => ({
  getDataStatus: (...args) => mockGetDataStatus(...args),
  getTradingDay: (...args) => mockGetTradingDay(...args),
}))

vi.mock('./pages/Overview', () => ({
  default: () => <div>Overview Page</div>,
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

vi.mock('./pages/MarketIntelligence', () => ({
  default: () => <div>MarketIntelligence Page</div>,
}))

describe('App shared copy', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/')
    mockGetTradingDay.mockResolvedValue({
      is_trading_day: true,
      nearest_trading_day: '2026-06-17',
      max_trading_day: '2026-06-17',
    })
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

  it('shows neutral api header copy instead of connected', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Overview Page')).toBeTruthy()
    })

    expect(screen.getByText('团队控制台：审阅 / 监控 / 复盘')).toBeTruthy()
    expect(screen.getByText('API:')).toBeTruthy()
    expect(screen.getByText('本地模式')).toBeTruthy()
    expect(screen.queryByText('Connected')).toBeNull()
  })

  it('shows updated tushare banner wording when credit is insufficient', async () => {
    mockGetDataStatus.mockResolvedValue({
      latest_available_date: '2026-06-17',
      tushare: {
        credit_insufficient: true,
        last_credit_insufficient_at: '2026-06-17T09:00:00Z',
        last_credit_insufficient_api: 'daily',
      },
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Tushare 黄旗：')).toBeTruthy()
    })

    expect(screen.getByText('Tushare 黄旗：')).toBeTruthy()
    expect(screen.getByText('检测到 Tushare 积分不足，日线主源可能受影响。')).toBeTruthy()
  })
})
