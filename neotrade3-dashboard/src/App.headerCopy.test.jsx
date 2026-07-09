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

describe('App header copy', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/')
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

  it('shows workspace-oriented environment copy in header', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Overview Page')).toBeTruthy()
    })

    expect(screen.getByText('团队控制台：审阅 / 监控 / 复盘')).toBeTruthy()
    expect(screen.getByText('当前环境：')).toBeTruthy()
    expect(screen.getByText('本地工作区')).toBeTruthy()
    expect(screen.queryByText('API:')).toBeNull()
    expect(screen.queryByText('本地模式')).toBeNull()
  })
})
