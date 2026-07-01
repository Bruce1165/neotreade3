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
              sector: '机器人',
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
    '/api/lowfreq/portfolio?date=2026-06-09': {
      portfolio: {
        strategy: 'low_freq_v16_advanced',
        as_of: '2026-06-09',
        initial_capital: 1000000,
        total_value: 1080600,
        cash: 320000,
        total_return_pct: 8.06,
        open_positions: [
          {
            code: '600001',
            name: '领涨一号',
            sector: '机器人',
            buy_date: '2026-05-20',
            hold_days: 15,
            buy_price: 12.3,
            current_price: 13.6,
            market_value: 200000,
            unrealized_pnl_pct: 10.57,
            peak_return_pct: 18.2,
            process_stage: 'exit_watch',
            buy_progress_label: '早窗',
            wave_phase: '3浪',
            market_exit_state: 'review',
            market_exit_hits: 2,
            system_exit_grace_used: true,
            system_exit_grace_scope: 'market',
            system_exit_grace_date: '2026-06-08',
            sell_reason: '创业板见顶确认候选',
          },
        ],
        closed_trades: [
          {
            code: '600002',
            name: '跟踪二号',
            sector: '机器人',
            buy_date: '2026-05-01',
            sell_date: '2026-06-06',
            shares: 1000,
            buy_price: 10.0,
            sell_price: 12.0,
            realized_pnl: 2000,
            return_pct: 20.0,
            peak_return_pct: 26.0,
            buy_progress_label: '前置布局',
            wave_phase: '1浪',
            process_stage: 'closed',
            sell_reason: '板块见顶确认',
            system_exit_grace_used: false,
          },
        ],
        manual_intents: [
          {
            code: '600001',
            name: '机器人',
            intent_type: 'buy_intent',
            status: 'pending',
            requested_date: '2026-06-09',
            created_at: '2026-06-09 10:30:00',
          },
        ],
      },
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

  it('creates a buy intent from candidates tab', async () => {
    const payloads = buildTodayPayloads()
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/lowfreq/manual/buy-intent') {
        return Promise.resolve({ ok: true })
      }
      return Promise.resolve(payloads[url])
    })

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByText('今日快照')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '候选池' }))

    await waitFor(() => {
      expect(screen.getByText('候选池 (1)')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '买进(T+1)' }))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq/manual/buy-intent',
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

  it('opens trade record tab without white screen when portfolio fields are partial', async () => {
    const payloads = buildTodayPayloads()
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '交易记录' })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '交易记录' }))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq/portfolio?date=2026-06-09',
        {},
        { timeoutMs: 45000 },
      )
    })

    expect(screen.getByText('当前组合累计收益')).toBeTruthy()
    expect(screen.getByText('持仓明细')).toBeTruthy()
    expect(screen.getByText('捕捉 / 持有 / 退出全过程')).toBeTruthy()
    expect(screen.getByText('人工干预记录')).toBeTruthy()
    expect(screen.getAllByRole('columnheader', { name: '名称' }).length).toBeGreaterThan(0)
    expect(screen.getAllByText('机器人').length).toBeGreaterThan(0)
    expect(screen.getByText('初始资金:')).toBeTruthy()
    expect(screen.getByText('早窗 / 3浪')).toBeTruthy()
    expect(screen.getAllByText('grace:market @ 2026-06-08').length).toBeGreaterThan(0)
  })
})
