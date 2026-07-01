import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import StockCheck from './StockCheck'

const mockUseApp = vi.fn()
const mockFetchApi = vi.fn()

vi.mock('../context/AppContext', () => ({
  useApp: () => mockUseApp(),
}))

vi.mock('../services/api', () => ({
  fetchApi: (...args) => mockFetchApi(...args),
}))

vi.mock('../components/DateSelector', () => ({
  default: () => <div data-testid="date-selector-stub">DateSelector</div>,
}))

describe('StockCheck', () => {
  beforeEach(() => {
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('shows validation error when stock code is empty', async () => {
    render(<StockCheck />)

    fireEvent.click(screen.getByRole('button', { name: '检查' }))

    expect(screen.getByText('请输入股票代码')).toBeTruthy()
    expect(mockFetchApi).not.toHaveBeenCalled()
  })

  it('requests stock check and renders returned result', async () => {
    mockFetchApi.mockResolvedValue({
      stock_code: '600000',
      target_date: '2026-06-09',
      checks: {
        certainty: {
          value: 0.87,
          message: '高确定性',
        },
        hot_sectors: {
          message: '命中热门板块',
          matches: [
            {
              sector: '机器人',
              role: 'leaders',
              buy_signal: true,
              suggested_entry: '观察回踩',
            },
          ],
        },
        weekly_duck_head: {
          explain_cn: '周线形态成立',
        },
        screeners: {
          items: [
            {
              screener_id: 'shi_pan_xian',
              name: '势盘线',
              result: true,
              explain_cn: '通过',
            },
            {
              screener_id: 'cup_handle_v4',
              name: '杯柄形态',
              result: false,
              explain_cn: '未通过',
            },
          ],
        },
      },
    })

    render(<StockCheck />)

    fireEvent.change(screen.getByPlaceholderText('例如：600000'), {
      target: { value: '600000' },
    })
    fireEvent.click(screen.getByRole('button', { name: '检查' }))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/check-stock?code=600000&date=2026-06-09',
        {},
        { timeoutMs: 45000 },
      )
    })

    expect(screen.getByText('基本信息')).toBeTruthy()
    expect(screen.getByText('高确定性')).toBeTruthy()
    expect(screen.getByText('命中热门板块')).toBeTruthy()
    expect(screen.getByText('周线形态成立')).toBeTruthy()
    expect(screen.getByText('势盘线')).toBeTruthy()
    expect(screen.getByText('杯柄形态')).toBeTruthy()
    expect(screen.getAllByText('可出手')[0].closest('span')?.getAttribute('aria-label')).toContain('一级状态：建仓')
    const passBadge = screen
      .getAllByText('通过')
      .find((node) => node.closest('span')?.getAttribute('aria-label'))
    expect(passBadge?.closest('span')?.getAttribute('aria-label')).toContain('一级状态：检查结果')
    expect(screen.getByRole('link', { name: '600000' }).getAttribute('href')).toBe(
      'https://stockpage.10jqka.com.cn/600000/',
    )
  })
})
