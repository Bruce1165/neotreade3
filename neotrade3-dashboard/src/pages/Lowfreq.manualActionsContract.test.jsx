import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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

vi.mock('react-router-dom', () => ({
  Link: ({ to, children, className }) => (
    <a href={to} className={className}>
      {children}
    </a>
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
    '/api/lowfreq-score/pool?date=2026-06-09&limit=500': {
      _meta: { status: 'ok', contract: 'lowfreq-score/pool.v1alpha1' },
      meta: {
        as_of_date: '2026-06-09',
        states: ['跟踪', '持有中', '已清仓'],
      },
      summary: {
        pool_size: 3,
        tracked_count: 1,
        holding_count: 1,
        closed_count: 1,
        holding_return_pct: 10.57,
        realized_return_pct: 20.0,
      },
      ui_contract: {
        state_enum: ['跟踪', '持有中', '已清仓'],
      },
      pool: [
        {
          code: '600001',
          name: '领涨一号',
          sector: 'I65',
          sector_name: '机器人',
          state: '持有中',
          tracking_since: '2026-05-18',
          buy_date: '2026-05-20',
          buy_price: 12.3,
          last_price: 13.6,
          current_return_pct: 10.57,
        },
      ],
    },
    '/api/lowfreq-score/events?date=2026-06-09&limit=120': {
      _meta: { status: 'ok', contract: 'lowfreq-score/events.v1alpha1' },
      meta: { as_of_date: '2026-06-09' },
      ui_contract: { event_type_enum: ['tracked', 'entered_holding', 'top_detected', 'closed'] },
      events: [],
    },
    '/api/lowfreq-score/summary?date=2026-06-09&limit=12': {
      _meta: { status: 'ok', contract: 'lowfreq-score/summary.v1alpha1' },
      meta: { as_of_date: '2026-06-09' },
      ui_contract: { period_type_enum: ['day', 'month'] },
      summaries: [],
    },
  }
}

describe('Lowfreq manual actions contract', () => {
  beforeEach(() => {
    const storage = {}
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
    })
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key) => (key in storage ? storage[key] : null)),
      setItem: vi.fn((key, value) => {
        storage[key] = String(value)
      }),
      removeItem: vi.fn((key) => {
        delete storage[key]
      }),
      clear: vi.fn(() => {
        Object.keys(storage).forEach((key) => {
          delete storage[key]
        })
      }),
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('submits buy intent through lowfreq-score contract with display sector name', async () => {
    const payloads = buildTodayPayloads()
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/lowfreq-score/manual/buy-intent') {
        return Promise.resolve({ ok: true })
      }
      return Promise.resolve(payloads[url])
    })

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByText('盘面详情')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '候选与人工' }))

    await waitFor(() => {
      expect(screen.getByText('候选阅读区 (1)')).toBeTruthy()
      expect(screen.getByText('人工动作区')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '买进(T+1)' }))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq-score/manual/buy-intent',
        {
          method: 'POST',
          body: JSON.stringify({
            code: '600001',
            name: '领涨一号',
            sector: '机器人',
            role: 'leader',
            buy_score: 92,
            requested_date: '2026-06-09',
            requested_by: 'dashboard.react',
          }),
        },
        { timeoutMs: 30000 },
      )
    })

    expect(mockFetchApi).not.toHaveBeenCalledWith(
      '/api/lowfreq/manual/buy-intent',
      expect.anything(),
      expect.anything(),
    )
  })

  it('submits abandon through lowfreq-score contract', async () => {
    const payloads = buildTodayPayloads()
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/lowfreq-score/manual/abandon') {
        return Promise.resolve({ ok: true })
      }
      return Promise.resolve(payloads[url])
    })

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByText('盘面详情')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '候选与人工' }))

    await waitFor(() => {
      expect(screen.getByText('候选阅读区 (1)')).toBeTruthy()
      expect(screen.getByText('人工动作区')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '放弃' }))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq-score/manual/abandon',
        {
          method: 'POST',
          body: JSON.stringify({
            code: '600001',
            requested_date: '2026-06-09',
            requested_by: 'dashboard.react',
          }),
        },
        { timeoutMs: 30000 },
      )
    })

    expect(mockFetchApi).not.toHaveBeenCalledWith(
      '/api/lowfreq/manual/abandon',
      expect.anything(),
      expect.anything(),
    )
  })
})
