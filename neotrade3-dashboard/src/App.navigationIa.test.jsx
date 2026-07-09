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

describe('App navigation IA', () => {
  beforeEach(() => {
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

  it('shows only the target top-level navigation entries', async () => {
    window.history.pushState({}, '', '/')

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Overview Page')).toBeTruthy()
    })

    expect(screen.getByRole('link', { name: '今日总览' })).toBeTruthy()
    expect(screen.getByRole('link', { name: '主线审阅' })).toBeTruthy()
    expect(screen.getByRole('link', { name: '选股工作台' })).toBeTruthy()
    expect(screen.getByRole('link', { name: '运维中心' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: '筛选器' })).toBeNull()
    expect(screen.queryByRole('link', { name: '单股核验' })).toBeNull()
  })

  it('keeps lowfreq detail routes active on the workspace entry', async () => {
    window.history.pushState({}, '', '/lowfreq/backtest-reports/report-001')

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('LowfreqBacktestReport Page')).toBeTruthy()
    })

    expect(screen.getByRole('link', { name: '选股工作台' }).className).toContain('bg-blue-50')
    expect(screen.getByRole('link', { name: '运维中心' }).className).not.toContain('bg-blue-50')
  })

  it('marks ops route active on the ops entry', async () => {
    window.history.pushState({}, '', '/ops')

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('OpsCenter Page')).toBeTruthy()
    })

    expect(screen.getByRole('link', { name: '运维中心' }).className).toContain('bg-blue-50')
    expect(screen.getByRole('link', { name: '选股工作台' }).className).not.toContain('bg-blue-50')
  })
})
