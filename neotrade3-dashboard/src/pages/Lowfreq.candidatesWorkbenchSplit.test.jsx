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

function buildCandidatesPayload() {
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
              manual: {},
            },
          ],
          middle: [
            {
              code: '600002',
              name: '排队二号',
              sector: 'I65',
              sector_name: '机器人',
              role: 'middle',
              buy_score: 80,
              buy_signal: true,
              return_5d: 6.5,
              manual: {
                buy_intent_pending: true,
                buy_execute_date: 'T+1',
              },
            },
          ],
          followers: [
            {
              code: '600003',
              name: '放弃三号',
              sector: 'I65',
              sector_name: '机器人',
              role: 'follower',
              buy_score: 61,
              buy_signal: false,
              return_5d: -1.2,
              manual: {
                abandoned: true,
              },
            },
          ],
        },
      ],
    },
  }
}

describe('Lowfreq candidates workbench split', () => {
  beforeEach(() => {
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('separates read zone and action zone while keeping queued or abandoned names out of pending list', async () => {
    const payloads = buildCandidatesPayload()
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '候选池' })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '候选池' }))

    await waitFor(() => {
      expect(screen.getByText('候选阅读区 (3)')).toBeTruthy()
      expect(screen.getByText('人工动作区')).toBeTruthy()
    })

    expect(screen.getByText('待处理列表')).toBeTruthy()
    expect(screen.getAllByText('领涨一号').length).toBe(2)
    expect(screen.getAllByText('排队二号').length).toBe(1)
    expect(screen.getAllByText('放弃三号').length).toBe(1)
    expect(screen.getAllByRole('button', { name: '买进(T+1)' }).length).toBe(1)
    expect(screen.getAllByRole('button', { name: '放弃' }).length).toBe(1)
  })

  it('keeps buy and abandon actions working from the action zone', async () => {
    const payloads = buildCandidatesPayload()
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/lowfreq/manual/buy-intent') {
        return Promise.resolve({ ok: true })
      }
      if (url === '/api/lowfreq/manual/abandon') {
        return Promise.resolve({ ok: true })
      }
      return Promise.resolve(payloads[url])
    })

    render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '候选池' })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '候选池' }))

    await waitFor(() => {
      expect(screen.getByText('候选阅读区 (3)')).toBeTruthy()
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
            sector: 'I65',
            role: 'leader',
            buy_score: 92,
            requested_date: '2026-06-09',
            requested_by: 'dashboard.react',
          }),
        },
        { timeoutMs: 30000 },
      )
    })

    fireEvent.click(screen.getByRole('button', { name: '放弃' }))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq/manual/abandon',
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
  })
})
