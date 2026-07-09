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

function buildPayloads() {
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
        {
          code: '600002',
          name: '跟踪二号',
          sector: 'I65',
          sector_name: '机器人',
          state: '已清仓',
          tracking_since: '2026-04-29',
          buy_date: '2026-05-01',
          buy_price: 10.0,
          sell_price: 12.0,
          realized_return_pct: 20.0,
        },
      ],
    },
    '/api/lowfreq-score/summary?date=2026-06-09&limit=12': {
      _meta: { status: 'ok', contract: 'lowfreq-score/summary.v1alpha1' },
      meta: { as_of_date: '2026-06-09' },
      summaries: [
        {
          period_type: 'day',
          period_start: '2026-06-09',
          period_end: '2026-06-09',
          tracked_count: 1,
          holding_count: 1,
          closed_count: 0,
          pool_return_pct: 10.57,
          capture_quality: 0.5,
          top_exit_quality: null,
        },
      ],
    },
  }
}

describe('Lowfreq scorePool baseline', () => {
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

  it('opens stock pool tab on lowfreq-score contract without legacy portfolio fetch', async () => {
    const payloads = buildPayloads()
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '股票池与台账' })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '股票池与台账' }))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq-score/pool?date=2026-06-09&limit=500',
        {},
        { timeoutMs: 45000 },
      )
    })

    expect(screen.getByText('统一股票池')).toBeTruthy()
    expect(screen.getByText('阶段汇总')).toBeTruthy()
    expect(screen.getByText('股票池总数')).toBeTruthy()
    expect(screen.getAllByText('机器人').length).toBeGreaterThan(0)
    expect(screen.queryByText('I65')).toBeNull()
    expect(mockFetchApi).not.toHaveBeenCalledWith(
      '/api/lowfreq/portfolio?date=2026-06-09',
      {},
      { timeoutMs: 45000 },
    )
  })

  it('creates buy intent from candidates tab via lowfreq-score endpoint', async () => {
    const payloads = buildPayloads()
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/lowfreq-score/manual/buy-intent') {
        return Promise.resolve({ ok: true })
      }
      return Promise.resolve(payloads[url])
    })

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '候选与人工' })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '候选与人工' }))
    fireEvent.click(await screen.findByRole('button', { name: '买进(T+1)' }))

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

  it('records abandon action from candidates tab via lowfreq-score endpoint', async () => {
    const payloads = buildPayloads()
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/lowfreq-score/manual/abandon') {
        return Promise.resolve({ ok: true })
      }
      return Promise.resolve(payloads[url])
    })

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '候选与人工' })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '候选与人工' }))
    fireEvent.click(await screen.findByRole('button', { name: '放弃' }))

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

  it('prefers sector_name over sector code in candidates and scorePool views', async () => {
    const payloads = buildPayloads()
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '候选与人工' })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '候选与人工' }))
    expect(await screen.findAllByText('机器人')).toBeTruthy()
    expect(screen.queryByText('I65')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '股票池与台账' }))
    expect(await screen.findByText('统一股票池')).toBeTruthy()
    expect(screen.queryByText('I65')).toBeNull()
  })
})
