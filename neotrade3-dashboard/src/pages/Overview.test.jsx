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

vi.mock('react-router-dom', () => ({
  Link: ({ to, children, className }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}))

function buildWorkbenchPayload() {
  return {
    meta: {
      as_of_date: '2026-06-09',
      latest_data_date: '2026-06-09',
      execution_mode: 'unbounded_opportunity',
      autopilot_enabled: true,
      summary_text: '当前处于进攻阶段，操作倾向进攻，风险低，关注机器人，自动执行开启',
      daily_ops_status: 'ok',
      daily_ops_status_text: '正常',
      latest_data_synced: true,
    },
    market_summary: {
      phase_label: '进攻阶段',
      bias_label: '进攻',
      risk_label: '低',
      summary_text: '当前处于进攻阶段，操作倾向进攻，风险低，关注机器人，自动执行开启',
      evidence: ['phase=bull', 'confidence=0.72', 'focus_theme=机器人'],
    },
    daily_ops: {
      available: true,
      run_date: '2026-06-09',
      status: 'ok',
      status_text: '正常',
      status_kind: 'active',
      latest_trade_date: '2026-06-09',
      latest_data_synced: true,
      latest_data_synced_text: '已追平',
      provider: 'tushare',
      overdue_shifted_count: 2,
      inconsistency_count: 0,
      pending_intents_after: 3,
      finished_at: '2026-06-09T15:45:54Z',
      summary_text: '最近一轮每日任务成功，数据已追平到最新交易日，关键链路正常。',
      steps: [
        {
          step_id: 'authoritative_update',
          step_label: '权威行情更新',
          status: 'ok',
          status_text: '正常',
          status_kind: 'active',
        },
        {
          step_id: 'lowfreq_sim_daily',
          step_label: '低频日运行',
          status: 'ok',
          status_text: '正常',
          status_kind: 'active',
        },
      ],
    },
    hot_sectors: [
      {
        sector_code: 'BK001',
        sector_name: '机器人',
        heat_score: 88.5,
        status: 'active',
        status_text: '主升',
        leader_count: 1,
        middle_count: 1,
        follower_count: 0,
        actionable_count: 1,
        summary_text: '主线#1，趋势rising，主升',
        representatives: [
          { name: '领涨一号', role_text: '龙头' },
          { name: '中军一号', role_text: '中军' },
        ],
      },
    ],
    tracking_list: [
      {
        code: '600001',
        name: '领涨一号',
        sector: '机器人',
        role_text: '龙头',
        certainty_score: 82.0,
        tracking_stage_text: '建仓层',
        tracking_status: 'entry_ready',
        tracking_status_text: '可建仓',
        summary_text: '突破确认',
        first_seen_at: '2026-06-09',
        last_changed_at: '2026-06-09T09:35:00Z',
        is_new_today: true,
      },
    ],
    positions: [
      {
        code: '600001',
        name: '领涨一号',
        sector: '机器人',
        role_text: '龙头',
        position_status: 'stable',
        position_status_text: '稳定',
        buy_price: 10.0,
        current_price: 10.8,
        pnl_pct: 8.0,
        near_top_text: '未见顶',
        buy_date: '2026-06-03',
        holding_days: 4,
        exit_risk: 'low',
        exit_risk_text: '低',
        summary_text: '未触发正式退出条件',
      },
    ],
    trade_ledger: [
      {
        trade_date: '2026-06-09',
        action: 'buy',
        action_text: '买入',
        code: '600001',
        name: '领涨一号',
        sector: '机器人',
        price: 10.0,
        size_or_weight: 1000,
        reason_tag: 'entry_signal',
        reason_text: 'buy_score=92.0',
        source: 'auto',
        source_text: '自动',
        signal_date: '2026-06-08',
      },
    ],
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

  it('loads workbench data from a single endpoint and renders key sections', async () => {
    mockFetchApi.mockResolvedValue(buildWorkbenchPayload())

    render(<Overview />)

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/lowfreq/workbench?date=2026-06-09&ensure_generated=false',
        {},
        { timeoutMs: 60000 },
      )
    })

    expect(screen.getByText('今日总览')).toBeTruthy()
    expect(screen.getByText('今日结论')).toBeTruthy()
    expect(screen.getByText('风险与阻塞')).toBeTruthy()
    expect(screen.getByText('建议动作')).toBeTruthy()
    expect(screen.getByText('重点摘要')).toBeTruthy()
    expect(screen.getByText('每日运行与数据更新')).toBeTruthy()
    expect(screen.getByText('大盘阶段判断')).toBeTruthy()
    expect(screen.getAllByText('当前人气板块').length).toBeGreaterThan(0)
    expect(screen.getByText('当前跟踪股票池')).toBeTruthy()
    expect(screen.getByText('当前建仓股票池')).toBeTruthy()
    expect(screen.getAllByText('交易台账').length).toBeGreaterThan(0)
    expect(screen.getAllByText('领涨一号').length).toBeGreaterThan(0)
    expect(screen.getByText('主升')).toBeTruthy()
    expect(screen.getByText('今日新增')).toBeTruthy()
    expect(screen.getByText('自动')).toBeTruthy()
    expect(screen.getByText('已追平')).toBeTruthy()
    expect(screen.getByText('权威行情更新')).toBeTruthy()
  })

  it('shows error banner when workbench request fails', async () => {
    mockFetchApi.mockRejectedValue(new Error('工作台聚合失败'))

    render(<Overview />)

    await waitFor(() => {
      expect(screen.getByText('工作台聚合失败')).toBeTruthy()
    })

    expect(screen.getAllByText('当前人气板块').length).toBeGreaterThan(0)
    expect(screen.getByText('暂无人气板块')).toBeTruthy()
  })

  it('refreshes workbench payload when date selector triggers onRefresh', async () => {
    mockFetchApi.mockResolvedValue(buildWorkbenchPayload())

    render(<Overview />)

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledTimes(1)
    })

    fireEvent.click(screen.getByTestId('date-selector-stub'))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledTimes(2)
    })
  })
})
