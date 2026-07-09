import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import LowfreqBacktestReport from './LowfreqBacktestReport'

const mockFetchApi = vi.fn()

vi.mock('../services/api', () => ({
  fetchApi: (...args) => mockFetchApi(...args),
}))

function renderReportPage({
  path = '/lowfreq/backtest-reports/report-1',
  routePath = '/lowfreq/backtest-reports/:reportId',
} = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={routePath} element={<LowfreqBacktestReport />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('LowfreqBacktestReport', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders core sections and download links from detail payload', async () => {
    mockFetchApi.mockResolvedValue({
      execution_mode: 'unbounded_opportunity',
      pdf_url: '/reports/report-1.pdf',
      json_url: '/reports/report-1.json',
      summary: {
        total_return_pct: 12.34,
        annual_return_pct: 8.76,
        max_drawdown_pct: -3.21,
        total_trades: 7,
      },
      execution_action_summary: {
        buy: 2,
        reserve: 1,
      },
      exit_quality: {
        lookahead_trading_days: 10,
        count: 4,
        post_exit_runup_pct: {
          p90: 11.4,
          max: 15.6,
          gt_10pct_rate: 25.0,
        },
      },
      next_session: {
        next_trading_day: '2026-06-10',
        signal_summary: {
          candidate_count: 3,
        },
        candidates: [
          {
            code: '300308',
            name: '中际旭创',
            sector_name: '光模块',
            role: '龙头',
            buy_score: 97,
          },
        ],
      },
      recent_trades: [
        {
          code: '300308',
          name: '中际旭创',
          role: '龙头',
          buy_date: '2026-05-20',
          buy_price: 12.3,
          sell_date: '2026-06-03',
          sell_price: 14.1,
          return_pct: 14.63,
          hold_days: 10,
          sell_reason: '到达退出窗口',
        },
      ],
    })

    renderReportPage()

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq/backtest/report-detail?report_id=report-1',
        {},
        { timeoutMs: 45000 },
      )
    })

    expect(screen.getByText('回测报告详情')).toBeTruthy()
    expect(screen.getByText('报告编号：report-1')).toBeTruthy()
    expect(screen.getByRole('link', { name: '返回选股工作台' }).getAttribute('href')).toBe('/lowfreq')
    expect(screen.getByRole('link', { name: '下载 PDF' }).getAttribute('href')).toBe('/reports/report-1.pdf')
    expect(screen.getByRole('link', { name: '下载 JSON' }).getAttribute('href')).toBe('/reports/report-1.json')
    expect(screen.getByText('回测总收益')).toBeTruthy()
    expect(screen.getByText('+12.34%')).toBeTruthy()
    expect(screen.getByText('执行摘要')).toBeTruthy()
    expect(screen.getByText('退出质量评估')).toBeTruthy()
    expect(screen.getByText('下一交易日信号')).toBeTruthy()
    expect(screen.getByText('最近交易样本')).toBeTruthy()
    expect(screen.getByText('中际旭创 · 300308')).toBeTruthy()
  })

  it('shows error state when detail request fails', async () => {
    mockFetchApi.mockRejectedValue(new Error('详情读取失败'))

    renderReportPage({
      path: '/lowfreq/backtest-reports/report-failed',
    })

    expect(await screen.findByText('报告读取失败')).toBeTruthy()
    expect(screen.getByText('详情读取失败')).toBeTruthy()
  })

  it('shows missing report id state without issuing a request', async () => {
    renderReportPage({
      path: '/',
      routePath: '/',
    })

    expect(await screen.findByText('报告读取失败')).toBeTruthy()
    expect(screen.getByText('报告编号缺失')).toBeTruthy()
    expect(mockFetchApi).not.toHaveBeenCalled()
  })

  it('falls back safely when optional detail fields are missing', async () => {
    mockFetchApi.mockResolvedValue({
      summary: {
        total_return_pct: null,
        annual_return_pct: null,
        max_drawdown_pct: null,
        total_trades: null,
      },
      execution_action_summary: {},
      exit_quality: {},
      next_session: {},
      recent_trades: [],
    })

    renderReportPage({
      path: '/lowfreq/backtest-reports/report-partial',
    })

    expect(await screen.findByText('报告编号：report-partial')).toBeTruthy()
    expect(screen.getAllByText('--').length).toBeGreaterThan(0)
    expect(screen.getByText('暂无执行动作摘要')).toBeTruthy()
    expect(screen.getByText('暂无候选信号')).toBeTruthy()
    expect(screen.getByText('暂无交易样本')).toBeTruthy()
    expect(screen.queryByRole('link', { name: '下载 PDF' })).toBeNull()
    expect(screen.queryByRole('link', { name: '下载 JSON' })).toBeNull()
  })
})
