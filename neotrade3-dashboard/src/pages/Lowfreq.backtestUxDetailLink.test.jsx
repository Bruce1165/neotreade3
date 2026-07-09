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
        pool_size: 1,
        tracked_count: 0,
        holding_count: 1,
        closed_count: 0,
        holding_return_pct: 10.57,
        realized_return_pct: 0.0,
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

describe('Lowfreq backtest UX detail links', () => {
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

  it('treats unknown backtest status as an error state instead of endless running', async () => {
    const payloads = buildPayloads()
    localStorage.setItem('neotrade3_last_backtest_report_id', 'report-unknown')
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/lowfreq/backtest/reports?limit=10') {
        return Promise.resolve({ reports: [] })
      }
      if (url === '/api/lowfreq/backtest/status?report_id=report-unknown') {
        return Promise.resolve({
          job: {
            status: 'unknown',
            reason: 'status_file_missing',
          },
        })
      }
      return Promise.resolve(payloads[url])
    })

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '回测报告' })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '回测报告' }))

    expect(await screen.findByText('回测状态异常')).toBeTruthy()
    expect(screen.getAllByText('status_file_missing').length).toBeGreaterThan(0)
    expect(screen.queryByText('报告生成中')).toBeNull()
  })

  it('shows execution mode and current detail link when backtest status resolves to done', async () => {
    const payloads = buildPayloads()
    localStorage.setItem('neotrade3_last_backtest_report_id', 'report-done')
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/lowfreq/backtest/reports?limit=10') {
        return Promise.resolve({ reports: [] })
      }
      if (url === '/api/lowfreq/backtest/status?report_id=report-done') {
        return Promise.resolve({
          job: {
            status: 'done',
          },
          execution_mode: 'unbounded_opportunity',
          summary: {
            total_return_pct: 12.34,
            annualized_return_pct: 8.76,
            max_drawdown_pct: -3.21,
            sharpe_ratio: 1.11,
          },
          execution_action_summary: {
            buy: 2,
            reserve: 1,
          },
          exit_quality: {
            lookahead_trading_days: 10,
            count: 4,
            post_exit_runup_pct: {
              p50: 3.2,
              p75: 6.8,
              p90: 11.4,
              max: 15.6,
              gt_10pct_rate: 25.0,
            },
          },
          next_session: {
            next_trading_day: '2026-06-10',
            signal_summary: {
              candidate_count: 3,
              entry_count: 1,
            },
            candidates: [
              {
                code: '300308',
                name: '中际旭创',
                sector: 'I88',
                sector_name: '光模块',
                role: '龙头',
                buy_score: 97.0,
              },
            ],
          },
          pdf_url: '/reports/report-done.pdf',
          json_url: '/reports/report-done.json',
        })
      }
      return Promise.resolve(payloads[url])
    })

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '回测报告' })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '回测报告' }))

    expect(await screen.findByText('运行方式：unbounded_opportunity')).toBeTruthy()
    expect(screen.getByText('报告编号：report-done')).toBeTruthy()
    expect(screen.getByText('本次回测输出包含什么')).toBeTruthy()
    expect(screen.getByText('回测总收益')).toBeTruthy()
    expect(screen.getByText('+12.34%')).toBeTruthy()
    expect(screen.getByLabelText('回测开始日期').getAttribute('type')).toBe('date')
    expect(screen.getByLabelText('回测结束日期').getAttribute('type')).toBe('date')
    expect(screen.getByText('执行摘要')).toBeTruthy()
    expect(screen.getAllByText('退出质量评估').length).toBeGreaterThan(0)
    expect(screen.getAllByText('下一交易日信号').length).toBeGreaterThan(0)
    expect(screen.getByText('下一交易日')).toBeTruthy()
    expect(screen.getByText('2026-06-10')).toBeTruthy()
    expect(screen.getByText('卖出后涨幅 P90')).toBeTruthy()
    expect(screen.getByText('+11.40%')).toBeTruthy()
    expect(screen.getByText('前 5 候选')).toBeTruthy()
    expect(screen.getByText('中际旭创 · 300308')).toBeTruthy()
    expect(screen.getByRole('link', { name: '查看明细' }).getAttribute('href')).toBe('/lowfreq/backtest-reports/report-done')
  })

  it('uses detail page links for history reports and hides missing detail links', async () => {
    const payloads = buildPayloads()
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/lowfreq/backtest/reports?limit=10') {
        return Promise.resolve({
          reports: [
            {
              report_id: 'report-has-json',
              start_date: '2026-05-01',
              end_date: '2026-06-01',
              summary: { total_return_pct: 9.87 },
              pdf_url: '/reports/report-has-json.pdf',
              json_url: '/reports/report-has-json.json',
            },
            {
              report_id: 'report-no-json',
              start_date: '2026-04-01',
              end_date: '2026-05-01',
              summary: { total_return_pct: -1.23 },
              pdf_url: '/reports/report-no-json.pdf',
              json_url: null,
            },
          ],
        })
      }
      return Promise.resolve(payloads[url])
    })

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '回测报告' })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '回测报告' }))

    expect(await screen.findByText('最近 10 次回测报告')).toBeTruthy()
    expect(screen.getByRole('link', { name: '明细' }).getAttribute('href')).toBe('/lowfreq/backtest-reports/report-has-json')
    expect(screen.getAllByText('PDF').length).toBeGreaterThan(0)
    expect(screen.getAllByText('明细').length).toBe(1)
  })
})
