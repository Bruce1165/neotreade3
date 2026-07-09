import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Lowfreq from './Lowfreq'
import { TestAppProvider } from '../context/AppContext'

const mockFetchApi = vi.fn()
const mockGetTradingDay = vi.fn()
const mockGetDataStatus = vi.fn()

vi.mock('../context/AppContext', async () => {
  const React = await import('react')
  const TestContext = React.createContext({
    selectedDate: '2026-06-11',
    setSelectedDate: () => {},
  })

  function TestAppProvider({ initialSelectedDate = '2026-06-11', children }) {
    const [selectedDate, setSelectedDate] = React.useState(initialSelectedDate)
    const value = React.useMemo(() => ({ selectedDate, setSelectedDate }), [selectedDate])
    return <TestContext.Provider value={value}>{children}</TestContext.Provider>
  }

  return {
    useApp: () => React.useContext(TestContext),
    TestAppProvider,
  }
})

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    fetchApi: (...args) => mockFetchApi(...args),
    getTradingDay: (...args) => mockGetTradingDay(...args),
    getDataStatus: (...args) => mockGetDataStatus(...args),
  }
})

vi.mock('react-router-dom', () => ({
  Link: ({ to, children, className }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}))

function buildPayloads(date) {
  return {
    [`/api/market-phase?date=${date}`]: {
      market_phase: {
        phase: 'bull',
        market_breadth: 0.64,
        market_return_20d: 0.12,
        amount_trend: 'rising',
      },
    },
    [`/api/sectors/hot?date=${date}&mode=ths_concept&include_portfolio=0&include_sell_signal=0`]: {
      _meta: {
        status: 'ok',
        mode: 'ths_concept',
        market_phase: {
          phase: 'bull',
          confidence: 0.83,
        },
      },
      sectors: [],
    },
    '/api/lowfreq/backtest/reports?limit=10': {
      reports: [],
    },
  }
}

describe('Lowfreq backtest end date sync', () => {
  beforeEach(() => {
    const storage = {}
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
    mockGetTradingDay.mockImplementation(async (date) => ({
      is_trading_day: true,
      nearest_trading_day: date,
      max_trading_day: '2026-06-11',
      calendar_covered_until: '2026-06-11',
    }))
    mockGetDataStatus.mockResolvedValue({
      latest_available_date: '2026-06-11',
      latest_trade_date: '2026-06-11',
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('keeps end date following selectedDate until the user edits it manually', async () => {
    mockFetchApi.mockImplementation((url) => {
      const payloads = {
        ...buildPayloads('2026-06-10'),
        ...buildPayloads('2026-06-11'),
      }
      return Promise.resolve(payloads[url] ?? { reports: [] })
    })

    const view = render(
      <TestAppProvider initialSelectedDate="2026-06-11">
        <Lowfreq />
      </TestAppProvider>
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '回测报告' })).toBeTruthy()
    })

    const globalDateInput = () => view.container.querySelectorAll('input[type="date"]')[0]

    await waitFor(() => {
      expect(globalDateInput().value).toBe('2026-06-11')
    })

    fireEvent.click(screen.getByRole('button', { name: '回测报告' }))

    const endDateInput = await screen.findByLabelText('回测结束日期')
    expect(endDateInput.value).toBe('2026-06-11')

    fireEvent.change(globalDateInput(), {
      target: { value: '2026-06-10' },
    })

    await waitFor(() => {
      expect(globalDateInput().value).toBe('2026-06-10')
      expect(screen.getByLabelText('回测结束日期').value).toBe('2026-06-10')
    })

    fireEvent.change(screen.getByLabelText('回测结束日期'), {
      target: { value: '2026-06-05' },
    })
    expect(screen.getByLabelText('回测结束日期').value).toBe('2026-06-05')

    fireEvent.change(globalDateInput(), {
      target: { value: '2026-06-11' },
    })

    await waitFor(() => {
      expect(globalDateInput().value).toBe('2026-06-11')
      expect(screen.getByLabelText('回测结束日期').value).toBe('2026-06-05')
    })
  })
})
