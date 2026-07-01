import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import MarketIntelligence from './MarketIntelligence'

const mockUseApp = vi.fn()
const mockGetReviewBoard = vi.fn()
const mockGetDecisionSummary = vi.fn()

vi.mock('../context/AppContext', () => ({
  useApp: () => mockUseApp(),
}))

vi.mock('../services/api', () => ({
  getMarketIntelligenceReviewBoard: (...args) => mockGetReviewBoard(...args),
  getMarketIntelligenceDecisionSummary: (...args) => mockGetDecisionSummary(...args),
}))

vi.mock('../components/DateSelector', () => ({
  default: ({ onRefresh, loading }) => (
    <button data-testid="date-selector-stub" onClick={onRefresh} disabled={loading}>
      DateSelector
    </button>
  ),
}))

function buildReviewBoardPayload() {
  return {
    trade_date: '2026-06-09',
    review_focus: {
      theme: {
        concept_code: '886042.TI',
        concept_name: '存储芯片',
        board_score: 39,
        base_score: 27,
        resonance_score: 12,
      },
      candidate: {
        stock_code: '000333',
        stock_name: '美的集团',
        recommendation_status: '推荐',
        special_markers: ['boundary_recovered_candidate'],
        special_marker_notes: ['因补齐渗透率标注后恢复为推荐，需人工重点复核主题集中度'],
      },
    },
    theme_summary: {
      items: [
        {
          concept_code: '886042.TI',
          concept_name: '存储芯片',
          board_score: 39,
          base_score: 27,
          resonance_score: 12,
          total_score: 39,
          config_candidate_count: 1,
          institutional_candidate_count: 0,
          trading_candidate_count: 2,
          thematic_tags: {
            ai_related: { result: true },
            kshape_direction: { value: 'up' },
            penetration_stage: { value: '10_30' },
          },
          ths_mainline: {
            trend_state: 'rising',
            risk_level: 'warn',
            mainline_rank: 3,
          },
          config_top_stocks: [
            { stock_name: '兆易创新' },
          ],
          institutional_top_stocks: [],
          trading_top_stocks: [
            { stock_name: '北方华创' },
            { stock_name: '德明利' },
          ],
        },
      ],
    },
    candidate_summary: {
      items: [
        {
          stock_code: '000333',
          stock_name: '美的集团',
          recommendation_rank: 1,
          recommendation_status: '推荐',
          recommendation_reasons: [
            '龙头身份：交易型龙头',
            '命中 AI 宽口径主线',
          ],
          risk_flags: ['single_role_only'],
          leader_summary: {
            candidate_types: ['trading_leader'],
          },
          thematic_tags: {
            ai_related: { result: true },
            kshape_direction: { value: 'up' },
            penetration_stage: { value: '10_30' },
          },
          special_markers: ['boundary_recovered_candidate'],
          special_marker_notes: ['因补齐渗透率标注后恢复为推荐，需人工重点复核主题集中度'],
        },
      ],
    },
    links: [
      {
        stock_code: '000333',
        stock_name: '美的集团',
        recommendation_status: '推荐',
        candidate_types: ['trading_leader'],
        penetration_values: ['10_30'],
        special_markers: ['boundary_recovered_candidate'],
        special_marker_notes: ['因补齐渗透率标注后恢复为推荐，需人工重点复核主题集中度'],
        matched_themes: [
          { concept_name: '存储芯片' },
        ],
      },
    ],
  }
}

function buildDecisionSummaryPayload() {
  return {
    trade_date: '2026-06-09',
    summary: {
      mainline_concentration: 'focused',
      ai_focus: 'focused',
      kshape_interference: 'low',
      recommendation_concentration: 'mixed',
    },
    counts: {
      recommended: 5,
      watchlist: 2,
      avoid: 0,
      recommended_ai: 4,
      recommended_kshape_down: 0,
      watch_kshape_down: 1,
    },
  }
}

function createDeferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('MarketIntelligence', () => {
  beforeEach(() => {
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('loads review board and decision summary data', async () => {
    mockGetReviewBoard.mockResolvedValue(buildReviewBoardPayload())
    mockGetDecisionSummary.mockResolvedValue(buildDecisionSummaryPayload())

    render(<MarketIntelligence />)

    await waitFor(() => {
      expect(mockGetReviewBoard).toHaveBeenCalledWith('2026-06-09', 10)
      expect(mockGetDecisionSummary).toHaveBeenCalledWith('2026-06-09', 10)
    })

    expect(screen.getByText('主线审阅')).toBeTruthy()
    expect(screen.getByText('主线集中度')).toBeTruthy()
    expect(screen.getByText('焦点候选（建议层）')).toBeTruthy()
    expect(screen.getAllByText('存储芯片').length).toBeGreaterThan(0)
    expect(screen.getAllByText('美的集团').length).toBeGreaterThan(0)
    expect(screen.getByText('配置龙头：')).toBeTruthy()
    expect(screen.getByText('联动摘要')).toBeTruthy()
    expect(screen.getByText('当前焦点按主线分优先确定')).toBeTruthy()
    expect(screen.getAllByText('主线分').length).toBeGreaterThan(0)
    expect(screen.getAllByText('共振分').length).toBeGreaterThan(0)
    expect(screen.getByText('龙头身份：交易型龙头 / 命中 AI 宽口径主线')).toBeTruthy()
    expect(screen.getByText('single_role_only')).toBeTruthy()
    expect(screen.getAllByText('边界恢复').length).toBeGreaterThan(0)
    expect(
      screen.getAllByText('因补齐渗透率标注后恢复为推荐，需人工重点复核主题集中度').length
    ).toBeGreaterThan(0)
    expect(screen.getByText('日线主源：Tushare，Tencent 仅作 safety-net')).toBeTruthy()
    expect(screen.getAllByRole('link', { name: '000333' }).length).toBeGreaterThan(0)
    expect(screen.getAllByText('886042.TI').every((node) => node.closest('a') === null)).toBe(true)
  })

  it('renders authoritative source error details when backend returns structured failure', async () => {
    mockGetReviewBoard.mockRejectedValue(
      Object.assign(new Error('authoritative source unavailable for resource: concept_theme_cache'), {
        code: 'authoritative_source_unavailable',
        details: {
          resource: 'concept_theme_cache',
          provider: 'tushare',
          fallback_attempted: false,
          fallback_provider: null,
        },
      })
    )
    mockGetDecisionSummary.mockResolvedValue(buildDecisionSummaryPayload())

    render(<MarketIntelligence />)

    expect(await screen.findByText('权威数据源不可用：concept_theme_cache')).toBeTruthy()
    expect(screen.getByText('资源：concept_theme_cache')).toBeTruthy()
    expect(screen.getByText('主源：tushare')).toBeTruthy()
    expect(screen.getByText('已尝试 safety-net：否')).toBeTruthy()
    expect(screen.getByText('safety-net：未使用')).toBeTruthy()
  })

  it('renders decision summary block before review board completes', async () => {
    const reviewBoardDeferred = createDeferred()
    mockGetReviewBoard.mockReturnValue(reviewBoardDeferred.promise)
    mockGetDecisionSummary.mockResolvedValue(buildDecisionSummaryPayload())

    render(<MarketIntelligence />)

    expect(await screen.findByText('主线集中度')).toBeTruthy()
    expect(screen.getByText('AI 聚焦')).toBeTruthy()
    expect(screen.queryByText('决策摘要加载中...')).toBeNull()
    expect(screen.getByText('主线审阅加载中...')).toBeTruthy()

    reviewBoardDeferred.resolve(buildReviewBoardPayload())

    expect(await screen.findByText('焦点候选（建议层）')).toBeTruthy()
    expect(screen.getAllByText('存储芯片').length).toBeGreaterThan(0)
  })
})
