import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Lowfreq from './Lowfreq'

const mockUseApp = vi.fn()
const mockFetchApi = vi.fn()

vi.mock('../context/AppContext', () => ({
  useApp: () => mockUseApp(),
}))

vi.mock('../services/api', () => ({
  fetchApi: (...args) => mockFetchApi(...args),
}))

vi.mock('../components/DateSelector', () => ({
  default: ({ onRefresh, loading }) => (
    <button data-testid="date-selector-stub" onClick={onRefresh} disabled={loading}>
      DateSelector
    </button>
  ),
}))

function buildTodayPayloads() {
  return {
    '/api/market-phase?date=2026-06-09': {
      market_phase: {
        phase: 'bull',
        market_breadth: 0.64,
        market_return_20d: 0.12,
        amount_trend: 'rising',
      },
    },
    '/api/sectors/hot?date=2026-06-09&mode=ths_concept&include_portfolio=0&include_sell_signal=0': {
      _meta: {
        status: 'ok',
        mode: 'ths_concept',
        market_phase: {
          phase: 'bull',
          confidence: 0.83,
        },
      },
      sectors: [
        {
          name: '机器人',
          code: 'BK001',
          heat_score: 88.5,
          meta: {
            mainline_rank: 1,
            mainline_streak: 4,
            trend_state: 'rising',
            risk_level: 'ok',
          },
          upwave: {
            status: 'upwave',
            diffusion: 0.6,
            avg_top3_return_5d: 0.13,
            avg_top3_money_ratio: 1.25,
          },
          leaders: [
            {
              code: '600001',
              name: '领涨一号',
              sector: 'I65',
              sector_name: '机器人',
              role: 'leader',
              buy_score: 92,
              buy_signal: true,
              return_5d: 12.3,
              role_scores: {
                money_ratio: 1.22,
                money_rank: 0.91,
                cap_rank: 0.72,
                return_20d_rank: 0.88,
              },
              risk_level: 'ok',
              manual: {},
            },
          ],
          middle: [],
          followers: [],
        },
      ],
    },
  }
}

describe('Lowfreq', () => {
  beforeEach(() => {
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('loads today snapshot and renders market + sector cards', async () => {
    const payloads = buildTodayPayloads()
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Lowfreq />)

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/market-phase?date=2026-06-09',
        {},
        { timeoutMs: 45000 },
      )
    })

    expect(screen.getByText('低频交易')).toBeTruthy()
    expect(screen.getByText('市场阶段')).toBeTruthy()
    expect(screen.getByText('市场近20日涨跌')).toBeTruthy()
    expect(screen.getByText('市场环境指标，非策略收益')).toBeTruthy()
    expect(screen.getAllByText('机器人').length).toBeGreaterThan(0)
    expect(screen.getAllByText('领涨一号').length).toBeGreaterThan(0)
    expect(screen.getByText('升浪支持')).toBeTruthy()
    expect(screen.getAllByText('满足出手条件').length).toBeGreaterThan(0)
    expect(screen.getAllByText('满足出手条件')[0].closest('span')?.getAttribute('aria-label')).toContain('一级状态：建仓')
  })

  it('shows fallback instead of NaN percent when market phase fields are missing', async () => {
    const payloads = buildTodayPayloads()
    payloads['/api/market-phase?date=2026-06-09'] = {
      market_phase: {
        phase: 'bull',
        amount_trend: 'rising',
      },
    }
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByText('市场阶段')).toBeTruthy()
    })

    expect(screen.queryByText('NaN%')).toBeNull()
    expect(screen.getAllByText('--').length).toBeGreaterThan(0)
  })

  it('keeps hot sectors visible when market phase block fails', async () => {
    const payloads = buildTodayPayloads()
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/market-phase?date=2026-06-09') {
        return Promise.reject(new Error('市场阶段请求超时'))
      }
      return Promise.resolve(payloads[url])
    })

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByText('热门板块')).toBeTruthy()
    })

    expect(screen.getByText('市场阶段请求超时')).toBeTruthy()
    expect(screen.getAllByText('机器人').length).toBeGreaterThan(0)
  })

})
