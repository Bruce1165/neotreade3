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

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function flushMicrotasks() {
  return new Promise((resolve) => {
    setTimeout(resolve, 0)
  })
}

function hasExactText(node, text) {
  return node?.textContent?.replace(/\s+/g, ' ').trim() === text
}

describe('Lowfreq scorePool request guard', () => {
  let selectedDate = '2026-06-09'

  beforeEach(() => {
    const storage = {}
    selectedDate = '2026-06-09'
    mockUseApp.mockImplementation(() => ({
      selectedDate,
    }))
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

  it('ignores stale scorePool responses after selected date changes', async () => {
    const summaryA = deferred()
    const summaryB = deferred()
    const poolB = deferred()

    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/market-phase?date=2026-06-09') {
        return Promise.resolve({
          market_phase: { phase: 'bull', market_breadth: 0.64, market_return_20d: 0.12, amount_trend: 'rising' },
        })
      }
      if (url === '/api/sectors/hot?date=2026-06-09&mode=ths_concept&include_portfolio=0&include_sell_signal=0') {
        return Promise.resolve({ _meta: { status: 'ok' }, sectors: [] })
      }
      if (url === '/api/lowfreq-score/summary?date=2026-06-09&limit=12') {
        return summaryA.promise
      }
      if (url === '/api/lowfreq-score/summary?date=2026-06-10&limit=12') {
        return summaryB.promise
      }
      if (url === '/api/lowfreq-score/pool?date=2026-06-10&limit=500') {
        return poolB.promise
      }
      if (url === '/api/lowfreq-score/pool?date=2026-06-09&limit=500') {
        throw new Error('stale pool request should not be issued')
      }
      throw new Error(`Unexpected URL: ${url}`)
    })

    const view = render(<Lowfreq />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '股票池与台账' })).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '股票池与台账' }))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq-score/summary?date=2026-06-09&limit=12',
        {},
        { timeoutMs: 45000 },
      )
    })

    selectedDate = '2026-06-10'
    view.rerender(<Lowfreq />)

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq-score/summary?date=2026-06-10&limit=12',
        {},
        { timeoutMs: 45000 },
      )
    })

    summaryB.resolve({
      _meta: { status: 'ok', contract: 'lowfreq-score/summary.v1alpha1' },
      meta: { as_of_date: '2026-06-10' },
      summary: {
        pool_size: 8,
        tracked_count: 3,
        holding_count: 2,
        closed_count: 1,
        holding_return_pct: 11.11,
        realized_return_pct: 7.77,
      },
      summaries: [
        {
          period_type: 'day',
          period_start: '2026-06-10',
          period_end: '2026-06-10',
          tracked_count: 3,
          holding_count: 2,
          closed_count: 1,
          pool_return_pct: 11.11,
        },
      ],
    })

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq-score/pool?date=2026-06-10&limit=500',
        {},
        { timeoutMs: 45000 },
      )
    })

    poolB.resolve({
      _meta: { status: 'ok', contract: 'lowfreq-score/pool.v1alpha1' },
      meta: { as_of_date: '2026-06-10', states: ['持有中'] },
      summary: {
        pool_size: 8,
        tracked_count: 3,
        holding_count: 2,
        closed_count: 1,
        holding_return_pct: 11.11,
        realized_return_pct: 7.77,
      },
      pool: [
        {
          code: '600010',
          name: '新日期一号',
          sector: 'I66',
          sector_name: '电池',
          state: '持有中',
          tracking_since: '2026-06-08',
          buy_date: '2026-06-09',
          buy_price: 10.0,
          last_price: 11.2,
          current_return_pct: 12.0,
        },
      ],
    })

    await waitFor(() => {
      expect(
        screen.getByText((_, node) => hasExactText(node, '数据日期: 2026-06-10'))
      ).toBeTruthy()
      expect(screen.getByText('新日期一号')).toBeTruthy()
      expect(screen.getByText('股票池总数')).toBeTruthy()
    })

    summaryA.resolve({
      _meta: { status: 'ok', contract: 'lowfreq-score/summary.v1alpha1' },
      meta: { as_of_date: '2026-06-09' },
      summary: {
        pool_size: 2,
        tracked_count: 1,
        holding_count: 1,
        closed_count: 0,
        holding_return_pct: 1.11,
        realized_return_pct: 0.55,
      },
      summaries: [
        {
          period_type: 'day',
          period_start: '2026-06-09',
          period_end: '2026-06-09',
          tracked_count: 1,
          holding_count: 1,
          closed_count: 0,
          pool_return_pct: 1.11,
        },
      ],
    })

    await flushMicrotasks()

    expect(mockFetchApi).not.toHaveBeenCalledWith(
      '/api/lowfreq-score/pool?date=2026-06-09&limit=500',
      {},
      { timeoutMs: 45000 },
    )
    expect(
      screen.getByText((_, node) => hasExactText(node, '数据日期: 2026-06-10'))
    ).toBeTruthy()
    expect(screen.getByText('新日期一号')).toBeTruthy()
    expect(
      screen.queryByText((_, node) => hasExactText(node, '数据日期: 2026-06-09'))
    ).toBeNull()
  })
})
