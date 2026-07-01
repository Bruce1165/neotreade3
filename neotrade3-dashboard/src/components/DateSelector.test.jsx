import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import DateSelector from './DateSelector'

const mockUseApp = vi.fn()
const mockGetTradingDay = vi.fn()
const mockGetDataStatus = vi.fn()

vi.mock('../context/AppContext', () => ({
  useApp: () => mockUseApp(),
}))

vi.mock('../services/api', () => ({
  getTradingDay: (...args) => mockGetTradingDay(...args),
  getDataStatus: (...args) => mockGetDataStatus(...args),
}))

describe('DateSelector', () => {
  const realDate = Date

  beforeEach(() => {
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
      setSelectedDate: vi.fn(),
    })
    mockGetTradingDay.mockResolvedValue({
      is_trading_day: true,
      nearest_trading_day: '2026-06-09',
      max_trading_day: '2026-06-09',
    })
    mockGetDataStatus.mockResolvedValue({
      latest_available_date: '2026-06-09',
    })

    globalThis.Date = class extends realDate {
      constructor(...args) {
        if (args.length === 0) {
          return new realDate('2026-06-10T09:30:00Z')
        }
        return new realDate(...args)
      }

      static now() {
        return new realDate('2026-06-10T09:30:00Z').getTime()
      }
    }
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    globalThis.Date = realDate
  })

  it('clamps future date input to today', async () => {
    const setSelectedDate = vi.fn()
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
      setSelectedDate,
    })

    render(<DateSelector />)

    await waitFor(() => {
      expect(mockGetTradingDay).toHaveBeenCalledWith('2026-06-09')
      expect(mockGetDataStatus).toHaveBeenCalled()
    })

    const input = screen.getByDisplayValue('2026-06-09')
    fireEvent.change(input, { target: { value: '2026-06-11' } })

    expect(setSelectedDate).toHaveBeenCalledWith('2026-06-10')
  })

  it('shows non-trading-day guidance and switches to suggested trading day', async () => {
    const setSelectedDate = vi.fn()
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-08',
      setSelectedDate,
    })
    mockGetTradingDay.mockResolvedValue({
      is_trading_day: false,
      nearest_trading_day: '2026-06-09',
      max_trading_day: '2026-06-09',
    })
    mockGetDataStatus.mockResolvedValue({
      latest_available_date: '2026-06-09',
    })

    render(<DateSelector />)

    await waitFor(() => {
      expect(screen.getByText('所选日期不是有效的交易日')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: /切换到 2026-06-09/i }))

    expect(setSelectedDate).toHaveBeenCalledWith('2026-06-09')
  })

  it('reloads data status before calling external refresh handler', async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined)

    render(<DateSelector onRefresh={onRefresh} />)

    await waitFor(() => {
      expect(mockGetDataStatus).toHaveBeenCalledTimes(1)
    })

    fireEvent.click(screen.getByRole('button', { name: '刷新' }))

    await waitFor(() => {
      expect(mockGetDataStatus).toHaveBeenCalledTimes(2)
      expect(onRefresh).toHaveBeenCalledTimes(1)
    })
  })
})
