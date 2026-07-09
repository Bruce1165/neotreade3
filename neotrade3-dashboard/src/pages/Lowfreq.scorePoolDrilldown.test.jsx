import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
      },
      sectors: [],
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
    '/api/lowfreq-score/pool/600001?date=2026-06-09&event_limit=20': {
      _meta: { status: 'ok', contract: 'lowfreq-score/pool-item.v1alpha1' },
      meta: { as_of_date: '2026-06-09', event_limit: 20 },
      item: {
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
      events: [
        {
          event_id: 'evt-1',
          code: '600001',
          event_type: 'entered_holding',
          event_date: '2026-05-20',
          trigger_source: 'operation_logic.positions',
          price: 12.3,
          note: '正式买点成立并进入持有',
        },
      ],
      snapshots: [
        {
          trade_date: '2026-06-09',
          code: '600001',
          state: '持有中',
          close_price: 13.6,
          buy_price: 12.3,
          unrealized_return_pct: 10.57,
          realized_return_pct: null,
        },
      ],
    },
  }
}

describe('Lowfreq score pool drilldown', () => {
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

  it('opens a right-side drawer and loads score pool item details', async () => {
    const payloads = buildPayloads()
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Lowfreq />)

    fireEvent.click(screen.getByRole('button', { name: '股票池与台账' }))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq-score/pool?date=2026-06-09&limit=500',
        {},
        { timeoutMs: 45000 },
      )
    })

    fireEvent.click(screen.getByRole('button', { name: '查看明细' }))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq-score/pool/600001?date=2026-06-09&event_limit=20',
        {},
        { timeoutMs: 45000 },
      )
    })

    const dialog = await screen.findByRole('dialog', { name: '股票池明细' })

    expect(dialog).toBeTruthy()
    expect(within(dialog).getByText('当前状态')).toBeTruthy()
    expect(within(dialog).getByText('近期事件')).toBeTruthy()
    expect(within(dialog).getByText('最新快照')).toBeTruthy()
    expect(screen.getAllByText('领涨一号').length).toBeGreaterThan(0)
    expect(within(dialog).getByText('正式买点成立并进入持有')).toBeTruthy()
    expect(within(dialog).getAllByText('2026-06-09').length).toBeGreaterThan(0)
  })

  it('shows a local drawer error when the drilldown request fails', async () => {
    const payloads = buildPayloads()
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/lowfreq-score/pool/600001?date=2026-06-09&event_limit=20') {
        return Promise.reject(new Error('detail unavailable'))
      }
      return Promise.resolve(payloads[url])
    })

    render(<Lowfreq />)

    fireEvent.click(screen.getByRole('button', { name: '股票池与台账' }))

    await screen.findByText('领涨一号')
    fireEvent.click(screen.getByRole('button', { name: '查看明细' }))

    expect(await screen.findByRole('dialog', { name: '股票池明细' })).toBeTruthy()
    expect(await screen.findByText('detail unavailable')).toBeTruthy()
    expect(screen.getAllByText('领涨一号').length).toBeGreaterThan(0)
  })
})
