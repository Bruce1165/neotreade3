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
  }
}

describe('Lowfreq tools tab', () => {
  beforeEach(() => {
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('keeps screener and stock check tools under workbench tools tab', async () => {
    const payloads = buildTodayPayloads()
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '辅助工具' })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '辅助工具' }))

    expect(screen.getAllByText('辅助工具').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: '进入筛选器' }).getAttribute('href')).toBe('/screeners')
    expect(screen.getByRole('link', { name: '进入单股核验' }).getAttribute('href')).toBe('/stock-check')
  })
})
