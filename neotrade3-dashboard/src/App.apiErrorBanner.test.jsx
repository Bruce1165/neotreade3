import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
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

describe('App api error banner', () => {
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

  it('does not render api error banner by default', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Overview Page')).toBeTruthy()
    })

    expect(screen.queryByText('开发环境未连接：')).toBeNull()
    expect(screen.queryByText('接口失败告警：')).toBeNull()
  })

  it('shows environment banner when local api is unreachable', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Overview Page')).toBeTruthy()
    })

    act(() => {
      window.dispatchEvent(
        new window.CustomEvent('neotrade3:api-error', {
          detail: {
            endpoint: '/api/screeners/runs?date=2026-06-17',
            message: '请求失败：后端不可达（/api）',
            status: null,
            code: 'api_unreachable',
            happenedAt: '2026-07-04T13:00:00Z',
          },
        }),
      )
    })

    await waitFor(() => {
      expect(screen.getByText('开发环境未连接：')).toBeTruthy()
    })

    expect(screen.getByText('本地 API 服务暂未连接，页面会先展示占位信息。')).toBeTruthy()
    expect(screen.getByText('请先启动后端服务或检查本地代理配置。')).toBeTruthy()
    expect(screen.getByText('查看详细信息')).toBeTruthy()
  })

  it('allows dismissing the api error banner', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Overview Page')).toBeTruthy()
    })

    act(() => {
      window.dispatchEvent(
        new window.CustomEvent('neotrade3:api-error', {
          detail: {
            endpoint: '/api/screeners/runs?date=2026-06-17',
            message: '请求失败：后端不可达（/api）',
            status: null,
            code: 'api_unreachable',
            happenedAt: '2026-07-04T13:00:00Z',
          },
        }),
      )
    })

    const closeButton = await screen.findByRole('button', { name: '关闭' })
    act(() => {
      closeButton.click()
    })

    await waitFor(() => {
      expect(screen.queryByText('开发环境未连接：')).toBeNull()
    })
  })
})
