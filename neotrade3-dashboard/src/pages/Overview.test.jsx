import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Overview from './Overview'

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

function buildOverviewPayloads({ autopilotEnabled = false } = {}) {
  return {
    '/api/data/status': {
      latest_available_date: '2026-06-09',
      tushare: {
        resources: {
          concept_theme_cache: {
            last_failure_at: '2026-06-16T07:30:00Z',
            last_failure_reason: 'concept_list_unavailable',
          },
        },
      },
    },
    '/api/sectors/hot?date=2026-06-09&include_sell_signal=true': {
      sectors: [
        {
          name: '机器人',
          code: 'BK001',
          heat_score: 88.5,
          leaders: [
            {
              code: '600001',
              name: '领涨一号',
              buy_signal: true,
              certainty_prob: 0.82,
              certainty_samples: 12,
              risk_level: 'ok',
            },
          ],
          middle: [],
          followers: [],
        },
      ],
      portfolio: {
        total_return_pct: 4.56,
        as_of: '2026-06-09',
        open_positions: [
          {
            code: '600001',
            name: '领涨一号',
            sector: '机器人',
            buy_date: '2026-06-03',
            unrealized_pnl_pct: 2.34,
          },
        ],
      },
    },
    '/api/concepts/mainline?date=2026-06-09&limit=10': {
      concepts: [
        {
          concept_code: 'C001',
          concept_name: '机器人',
          mainline_rank: 1,
          mainline_score: 92.1,
          mainline_streak: 4,
          risk_level: 'warn',
        },
      ],
    },
    '/api/lowfreq/execution/queue?date=2026-06-09&ensure_generated=true': {
      autopilot_enabled: autopilotEnabled,
      queue: [
        {
          intent_id: 'buy-1',
          intent_type: 'buy_intent',
          name: '领涨一号',
          code: '600001',
          sector: '机器人',
          execute_date: '2026-06-09',
          status: 'pending',
          can_execute: true,
          certainty_prob: 0.82,
          certainty_samples: 12,
          risk_level: 'ok',
        },
      ],
    },
    '/api/lowfreq/backtest/window-summary?end_date=2026-06-08&window_trading_days=60': {
      _meta: { status: 'ok' },
      start_date: '2026-03-15',
      end_date: '2026-06-08',
      report: {
        summary: {
          total_return_pct: 12.34,
        },
        pdf_url: '/reports/demo.pdf',
        json_url: '/reports/demo.json',
      },
    },
  }
}

describe('Overview', () => {
  beforeEach(() => {
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('loads overview data and renders key summary blocks', async () => {
    const payloads = buildOverviewPayloads()
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Overview />)

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith('/api/data/status', {}, { timeoutMs: 45000 })
    })

    expect(mockFetchApi).toHaveBeenCalledWith(
      '/api/lowfreq/backtest/window-summary?end_date=2026-06-08&window_trading_days=60',
      {},
      { timeoutMs: 60000 },
    )
    expect(screen.getByText('今日总览')).toBeTruthy()
    expect(screen.getAllByText('2026-06-09').length).toBeGreaterThan(0)
    expect(screen.getByText('当前 authoritative 口径')).toBeTruthy()
    expect(screen.getByText('日线主源：Tushare')).toBeTruthy()
    expect(screen.getByText('safety-net：Tencent')).toBeTruthy()
    expect(
      screen.getByText('最近异常：concept_theme_cache @ 2026-06-16T07:30:00Z (concept_list_unavailable)')
    ).toBeTruthy()
    expect(screen.getByText('+4.56%')).toBeTruthy()
    expect(screen.getByText('当前虚拟组合累计收益｜数据日期：2026-06-09')).toBeTruthy()
    expect(screen.getAllByText('领涨一号').length).toBeGreaterThan(0)
    expect(screen.getAllByText('机器人').length).toBeGreaterThan(0)
    expect(screen.getByText('危险状态 1')).toBeTruthy()
    expect(screen.getByText('窗口回测总收益：')).toBeTruthy()
    expect(screen.getByText('下载 PDF')).toBeTruthy()
  })

  it('limits top sectors summary and list to five items', async () => {
    const payloads = buildOverviewPayloads()
    payloads['/api/sectors/hot?date=2026-06-09&include_sell_signal=true'] = {
      sectors: Array.from({ length: 6 }, (_, index) => ({
        name: `板块${index + 1}`,
        code: `BK00${index + 1}`,
        heat_score: 90 - index,
        leaders: [],
        middle: [],
        followers: [],
      })),
      portfolio: {
        total_return_pct: 4.56,
        as_of: '2026-06-09',
        open_positions: [],
      },
    }
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Overview />)

    await waitFor(() => {
      expect(screen.getByText('热门板块 Top5')).toBeTruthy()
    })

    expect(screen.getByText('5')).toBeTruthy()
    expect(screen.getByText('板块1')).toBeTruthy()
    expect(screen.getByText('板块5')).toBeTruthy()
    expect(screen.queryByText('板块6')).toBeNull()
  })

  it('hides recovered tushare failures when last_ok_at is newer than last_failure_at', async () => {
    const payloads = buildOverviewPayloads()
    payloads['/api/data/status'] = {
      latest_available_date: '2026-06-09',
      tushare: {
        resources: {
          daily_prices: {
            last_failure_at: '2026-06-16T11:22:14Z',
            last_failure_reason: 'tushare_not_installed',
            last_ok_at: '2026-06-17T01:13:39Z',
          },
        },
      },
    }
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Overview />)

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith('/api/data/status', {}, { timeoutMs: 45000 })
    })

    expect(screen.getByText('当前 authoritative 口径')).toBeTruthy()
    expect(screen.queryByText(/最近异常：/)).toBeNull()
  })

  it('toggles autopilot and refreshes queue data', async () => {
    let autopilotEnabled = false
    mockFetchApi.mockImplementation((url, options) => {
      if (url === '/api/lowfreq/settings/autopilot') {
        const payload = JSON.parse(options.body)
        autopilotEnabled = Boolean(payload.enabled)
        return Promise.resolve({ ok: true })
      }
      const payloads = buildOverviewPayloads({ autopilotEnabled })
      return Promise.resolve(payloads[url])
    })

    render(<Overview />)

    await waitFor(() => {
      expect(screen.getByText('当前模式：人工执行队列（方案2）')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('checkbox'))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq/settings/autopilot',
        {
          method: 'POST',
          body: JSON.stringify({
            enabled: true,
            requested_by: 'dashboard.react',
          }),
        },
        { timeoutMs: 30000 },
      )
    })

    await waitFor(() => {
      expect(screen.getByText('当前模式：自动执行（方案1）')).toBeTruthy()
    })
  })

  it('distinguishes concept avoid badges from position exit badges', async () => {
    const payloads = buildOverviewPayloads()
    payloads['/api/concepts/mainline?date=2026-06-09&limit=10'] = {
      concepts: [
        {
          concept_code: 'C001',
          concept_name: '机器人',
          mainline_rank: 1,
          mainline_score: 92.1,
          mainline_streak: 4,
          risk_level: 'exit',
        },
      ],
    }
    payloads['/api/lowfreq/execution/queue?date=2026-06-09&ensure_generated=true'] = {
      autopilot_enabled: false,
      queue: [
        {
          intent_id: 'sell-1',
          intent_type: 'sell_intent',
          name: '领涨一号',
          code: '600001',
          sector: '机器人',
          execute_date: '2026-06-09',
          status: 'pending',
          can_execute: true,
          risk_level: 'exit',
          sell_reason: 'sector_cooldown',
        },
      ],
    }
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Overview />)

    await waitFor(() => {
      expect(screen.getByText('回避 1')).toBeTruthy()
    })

    expect(screen.getAllByText('回避')[0].closest('span')?.getAttribute('aria-label')).toContain('一级状态：不满足条件')
    expect(screen.getAllByText('离场信号')[0].closest('span')?.getAttribute('aria-label')).toContain('一级状态：离场')
  })

  it('keeps overview usable when backtest block times out', async () => {
    const payloads = buildOverviewPayloads()
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/lowfreq/backtest/window-summary?end_date=2026-06-08&window_trading_days=60') {
        return Promise.reject(new Error('请求超时：窗口回测过慢'))
      }
      return Promise.resolve(payloads[url])
    })

    render(<Overview />)

    await waitFor(() => {
      expect(screen.getByText('当前 authoritative 口径')).toBeTruthy()
    })

    expect(screen.getByText('主线概念（Top10）')).toBeTruthy()
    expect(screen.getByText('买入 / 卖出 / 调整仓位（执行队列）')).toBeTruthy()
    expect(screen.getByText('昨日回测（窗口 60 交易日）')).toBeTruthy()
    expect(screen.getByText('请求超时：窗口回测过慢')).toBeTruthy()
    expect(screen.queryByText('HTTP 500')).toBeNull()
  })
})
