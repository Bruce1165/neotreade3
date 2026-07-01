import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, Flame, Link2, RefreshCw, Target } from 'lucide-react'

import DateSelector from '../components/DateSelector'
import StockCodeLink from '../components/StockCodeLink'
import { useApp } from '../context/AppContext'
import { createBlockState, resolveBlock, startBlock } from '../services/asyncBlocks'
import {
  getMarketIntelligenceDecisionSummary,
  getMarketIntelligenceReviewBoard,
} from '../services/api'

const TOP_N = 10

function summaryStateText(kind, value) {
  const normalized = String(value || '').trim().toLowerCase()
  if (kind === 'kshape') {
    if (normalized === 'low') return '低'
    if (normalized === 'medium') return '中'
    if (normalized === 'high') return '高'
    return normalized || '--'
  }
  if (normalized === 'focused') return '集中'
  if (normalized === 'mixed') return '混合'
  if (normalized === 'weak') return '偏弱'
  return normalized || '--'
}

function summaryStateClass(kind, value) {
  const normalized = String(value || '').trim().toLowerCase()
  if (kind === 'kshape') {
    if (normalized === 'low') return 'text-green-700 bg-green-50 border-green-100'
    if (normalized === 'medium') return 'text-orange-700 bg-orange-50 border-orange-100'
    if (normalized === 'high') return 'text-red-700 bg-red-50 border-red-100'
    return 'text-gray-700 bg-gray-50 border-gray-100'
  }
  if (normalized === 'focused') return 'text-blue-700 bg-blue-50 border-blue-100'
  if (normalized === 'mixed') return 'text-orange-700 bg-orange-50 border-orange-100'
  if (normalized === 'weak') return 'text-gray-700 bg-gray-50 border-gray-100'
  return 'text-gray-700 bg-gray-50 border-gray-100'
}

function recommendationClass(value) {
  const normalized = String(value || '').trim()
  if (normalized === '推荐') return 'text-green-700 bg-green-50 border-green-100'
  if (normalized === '观察') return 'text-orange-700 bg-orange-50 border-orange-100'
  if (normalized === '回避') return 'text-red-700 bg-red-50 border-red-100'
  return 'text-gray-700 bg-gray-50 border-gray-100'
}

function riskText(value) {
  const normalized = String(value || '').trim()
  if (normalized === 'ok') return '正常'
  if (normalized === 'warn') return '注意'
  if (normalized === 'exit') return '回避'
  return normalized || '--'
}

function trendText(value) {
  const normalized = String(value || '').trim()
  if (normalized === 'rising') return '走强'
  if (normalized === 'falling') return '走弱'
  if (normalized === 'consolidating') return '整理'
  if (normalized === 'diverging') return '分化'
  return normalized || '--'
}

function candidateTypeText(value) {
  const normalized = String(value || '').trim()
  if (normalized === 'config_leader') return '配置型龙头'
  if (normalized === 'institutional_attention') return '机构关注'
  if (normalized === 'trading_leader') return '交易型龙头'
  return normalized || '--'
}

function specialMarkerText(value) {
  const normalized = String(value || '').trim()
  if (normalized === 'boundary_recovered_candidate') return '边界恢复'
  return normalized || '--'
}

function specialMarkerClass() {
  return 'text-amber-800 bg-amber-50 border-amber-200'
}

function buildDisplayError(err) {
  const error = err && typeof err === 'object' ? err : null
  const code = String(error?.code || '').trim()
  const details = error?.details && typeof error.details === 'object' ? error.details : {}
  const message = String(error?.message || err || '').trim() || '请求失败'
  if (code !== 'authoritative_source_unavailable') {
    return {
      message,
      lines: [],
    }
  }
  const resource = String(details.resource || '').trim() || '--'
  const provider = String(details.provider || '').trim() || '--'
  const fallbackAttempted = details.fallback_attempted === true ? '是' : '否'
  const fallbackProvider = String(details.fallback_provider || '').trim() || '未使用'
  return {
    message: `权威数据源不可用：${resource}`,
    lines: [
      `资源：${resource}`,
      `主源：${provider}`,
      `已尝试 safety-net：${fallbackAttempted}`,
      `safety-net：${fallbackProvider}`,
      `后端信息：${message}`,
    ],
  }
}

function BlockMessage({ tone = 'gray', message, onRetry, retryLabel = '重试' }) {
  const toneClass =
    tone === 'red'
      ? 'bg-red-50 border-red-200 text-red-700'
      : 'bg-gray-50 border-gray-200 text-gray-600'
  return (
    <div className={`rounded-lg border p-4 text-sm flex items-center justify-between gap-3 ${toneClass}`}>
      <span>{message}</span>
      {typeof onRetry === 'function' ? (
        <button
          type="button"
          onClick={onRetry}
          className="px-3 py-1 rounded bg-white text-gray-700 border border-gray-200 hover:bg-gray-50"
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  )
}

function ErrorPanel({ error, onRetry }) {
  const displayError = error ? buildDisplayError(error) : null
  if (!displayError) {
    return null
  }
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start justify-between gap-3 text-red-700">
      <div className="flex items-start gap-3">
        <AlertCircle size={20} className="mt-0.5" />
        <div className="space-y-1">
          <div>{displayError.message}</div>
          {displayError.lines.map((line) => (
            <div key={line} className="text-sm text-red-800">
              {line}
            </div>
          ))}
        </div>
      </div>
      {typeof onRetry === 'function' ? (
        <button
          type="button"
          onClick={onRetry}
          className="px-3 py-1 rounded bg-white text-red-700 border border-red-200 hover:bg-red-100"
        >
          重试
        </button>
      ) : null}
    </div>
  )
}

function thematicBadges(tags) {
  const thematicTags = tags && typeof tags === 'object' ? tags : {}
  const badges = []
  const aiRelated = thematicTags.ai_related
  const kshape = thematicTags.kshape_direction
  const penetration = thematicTags.penetration_stage

  if (aiRelated && aiRelated.result) {
    badges.push({
      label: 'AI 相关',
      className: 'text-blue-700 bg-blue-50 border-blue-100',
    })
  }
  if (kshape && kshape.value) {
    const value = String(kshape.value).trim()
    badges.push({
      label: `K 型:${value}`,
      className:
        value === 'up'
          ? 'text-green-700 bg-green-50 border-green-100'
          : value === 'down'
            ? 'text-red-700 bg-red-50 border-red-100'
            : 'text-gray-700 bg-gray-50 border-gray-100',
    })
  }
  if (penetration && penetration.value) {
    badges.push({
      label: `渗透:${String(penetration.value).trim()}`,
      className: 'text-purple-700 bg-purple-50 border-purple-100',
    })
  }
  return badges
}

function topStockNames(theme, key) {
  const list = Array.isArray(theme?.[key]) ? theme[key] : []
  const names = []
  for (const item of list) {
    const name = String(item?.stock_name || '').trim()
    if (name && !names.includes(name)) {
      names.push(name)
    }
  }
  return names.slice(0, 3)
}

function SummaryCard({ title, value, subtitle, kind }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="text-sm font-medium text-gray-500 mb-3">{title}</div>
      <div
        className={`inline-flex items-center px-3 py-1 rounded-full border text-sm font-semibold ${summaryStateClass(
          kind,
          value
        )}`}
      >
        {summaryStateText(kind, value)}
      </div>
      <div className="text-sm text-gray-500 mt-3">{subtitle || '--'}</div>
    </div>
  )
}

function SpecialMarkerSection({ markers, notes, compact = false }) {
  const safeMarkers = Array.isArray(markers) ? markers.filter(Boolean) : []
  const safeNotes = Array.isArray(notes) ? notes.filter(Boolean) : []
  if (!safeMarkers.length && !safeNotes.length) {
    return null
  }

  return (
    <div className={compact ? 'mt-2 space-y-2' : 'mt-3 space-y-2'}>
      <div className="flex items-center gap-2 flex-wrap">
        {safeMarkers.map((marker) => (
          <span
            key={marker}
            className={`px-2 py-1 rounded-full border text-xs font-medium ${specialMarkerClass()}`}
          >
            {specialMarkerText(marker)}
          </span>
        ))}
      </div>
      {safeNotes.map((note) => (
        <div key={note} className="text-xs text-amber-900">
          {note}
        </div>
      ))}
    </div>
  )
}

export default function MarketIntelligence() {
  const { selectedDate } = useApp()
  const [blocks, setBlocks] = useState({
    reviewBoard: createBlockState(),
    decisionSummary: createBlockState(),
  })

  const loadReviewBoardBlock = useCallback(async () => {
    setBlocks((current) => ({
      ...current,
      reviewBoard: startBlock(current.reviewBoard),
    }))
    try {
      const reviewBoard = await getMarketIntelligenceReviewBoard(selectedDate, TOP_N)
      setBlocks((current) => ({
        ...current,
        reviewBoard: resolveBlock(reviewBoard),
      }))
    } catch (err) {
      setBlocks((current) => ({
        ...current,
        reviewBoard: {
          data: current.reviewBoard?.loaded ? current.reviewBoard?.data ?? null : null,
          loading: false,
          error: err,
          loaded: Boolean(current.reviewBoard?.loaded),
        },
      }))
    }
  }, [selectedDate])

  const loadDecisionSummaryBlock = useCallback(async () => {
    setBlocks((current) => ({
      ...current,
      decisionSummary: startBlock(current.decisionSummary),
    }))
    try {
      const decisionSummary = await getMarketIntelligenceDecisionSummary(selectedDate, TOP_N)
      setBlocks((current) => ({
        ...current,
        decisionSummary: resolveBlock(decisionSummary),
      }))
    } catch (err) {
      setBlocks((current) => ({
        ...current,
        decisionSummary: {
          data: current.decisionSummary?.loaded ? current.decisionSummary?.data ?? null : null,
          loading: false,
          error: err,
          loaded: Boolean(current.decisionSummary?.loaded),
        },
      }))
    }
  }, [selectedDate])

  const fetchData = useCallback(() => {
    void loadReviewBoardBlock()
    void loadDecisionSummaryBlock()
  }, [loadDecisionSummaryBlock, loadReviewBoardBlock])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const loading = blocks.reviewBoard.loading || blocks.decisionSummary.loading
  const reviewBoard = blocks.reviewBoard.data || {}
  const decisionSummary = blocks.decisionSummary.data || {}
  const summary = decisionSummary.summary || {}
  const counts = decisionSummary.counts || {}
  const themes = reviewBoard.theme_summary?.items || []
  const candidates = reviewBoard.candidate_summary?.items || []
  const links = reviewBoard.links || []
  const focusTheme = reviewBoard.review_focus?.theme || null
  const focusCandidate = reviewBoard.review_focus?.candidate || null
  const tradeDate = decisionSummary.trade_date || reviewBoard.trade_date || selectedDate

  return (
    <div className="space-y-6">
      <DateSelector onRefresh={fetchData} loading={loading} />

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">主线审阅</h2>
          <div className="text-gray-500 mt-1">
            先看赛道，再看候选，再核对主线与候选之间的联动关系
          </div>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          刷新
        </button>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4 text-sm text-gray-600">
        审阅日期：<span className="font-medium text-gray-900">{tradeDate || '--'}</span>
        <span className="ml-4">赛道数：{themes.length}</span>
        <span className="ml-4">候选数：{candidates.length}</span>
        <span className="ml-4">日线主源：Tushare，Tencent 仅作 safety-net</span>
      </div>

      {blocks.decisionSummary.loading && !blocks.decisionSummary.loaded ? (
        <BlockMessage message="决策摘要加载中..." />
      ) : blocks.decisionSummary.error && !blocks.decisionSummary.loaded ? (
        <ErrorPanel error={blocks.decisionSummary.error} onRetry={loadDecisionSummaryBlock} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <SummaryCard
            title="主线集中度"
            value={summary.mainline_concentration}
            subtitle={
              focusTheme
                ? `焦点赛道：${focusTheme.concept_name || '--'}`
                : '暂无焦点赛道'
            }
          />
          <SummaryCard
            title="AI 聚焦"
            value={summary.ai_focus}
            subtitle={`推荐中 AI 相关 ${counts.recommended_ai ?? 0} / ${counts.recommended ?? 0}`}
          />
          <SummaryCard
            title="K 型干扰"
            value={summary.kshape_interference}
            subtitle={`推荐下行 ${counts.recommended_kshape_down ?? 0}，观察下行 ${counts.watch_kshape_down ?? 0}`}
            kind="kshape"
          />
          <SummaryCard
            title="推荐集中度"
            value={summary.recommendation_concentration}
            subtitle={`推荐 ${counts.recommended ?? 0}，观察 ${counts.watchlist ?? 0}，回避 ${counts.avoid ?? 0}`}
          />
        </div>
      )}

      {blocks.reviewBoard.loading && !blocks.reviewBoard.loaded ? (
        <BlockMessage message="主线审阅加载中..." />
      ) : blocks.reviewBoard.error && !blocks.reviewBoard.loaded ? (
        <ErrorPanel error={blocks.reviewBoard.error} onRetry={loadReviewBoardBlock} />
      ) : (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Flame size={20} className="text-orange-500" />
                焦点赛道
              </h3>
              {focusTheme ? (
                <div className="space-y-2">
                  <div className="text-lg font-semibold text-gray-900">
                    {focusTheme.concept_name || '--'}
                  </div>
                  <div className="text-sm text-gray-500">{focusTheme.concept_code || '--'}</div>
                  <div className="text-sm text-gray-700">赛道分：{focusTheme.board_score ?? '--'}</div>
                  <div className="text-sm text-gray-700">
                    主线分：{focusTheme.base_score ?? '--'}，共振分：{focusTheme.resonance_score ?? '--'}
                  </div>
                  <div className="text-xs text-gray-500">当前焦点按主线分优先确定</div>
                </div>
              ) : (
                <div className="text-sm text-gray-500">暂无焦点赛道</div>
              )}
            </div>

            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Target size={20} />
                焦点候选（建议层）
              </h3>
              {focusCandidate ? (
                <div className="space-y-2">
                  <div className="text-lg font-semibold text-gray-900">
                    {focusCandidate.stock_name || '--'}
                  </div>
                  <div className="text-sm text-gray-500">
                    <StockCodeLink
                      code={focusCandidate.stock_code}
                      className="hover:text-blue-600 hover:underline"
                    >
                      {focusCandidate.stock_code || '--'}
                    </StockCodeLink>
                  </div>
                  <div>
                    <span
                      className={`inline-flex items-center px-3 py-1 rounded-full border text-sm font-medium ${recommendationClass(
                        focusCandidate.recommendation_status
                      )}`}
                    >
                      {focusCandidate.recommendation_status || '--'}
                    </span>
                  </div>
                  <SpecialMarkerSection
                    markers={focusCandidate.special_markers}
                    notes={focusCandidate.special_marker_notes}
                  />
                </div>
              ) : (
                <div className="text-sm text-gray-500">暂无焦点候选</div>
              )}
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Flame size={20} className="text-orange-500" />
              主线赛道
            </h3>
            {themes.length ? (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {themes.map((theme) => {
                  const configNames = topStockNames(theme, 'config_top_stocks')
                  const institutionalNames = topStockNames(theme, 'institutional_top_stocks')
                  const tradingNames = topStockNames(theme, 'trading_top_stocks')
                  const tags = thematicBadges(theme.thematic_tags)
                  return (
                    <div key={theme.concept_code} className="rounded-lg border border-gray-200 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-lg font-semibold text-gray-900">
                            {theme.concept_name || '--'}
                          </div>
                          <div className="text-sm text-gray-500">{theme.concept_code || '--'}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm text-gray-500">赛道分</div>
                          <div className="text-xl font-bold text-gray-900">
                            {theme.board_score ?? '--'}
                          </div>
                        </div>
                      </div>

                      <div className="mt-3 flex items-center gap-2 flex-wrap">
                        {tags.map((tag) => (
                          <span
                            key={tag.label}
                            className={`px-2 py-1 rounded-full border text-xs font-medium ${tag.className}`}
                          >
                            {tag.label}
                          </span>
                        ))}
                        <span className="px-2 py-1 rounded-full border text-xs font-medium text-gray-700 bg-gray-50 border-gray-100">
                          趋势:{trendText(theme.ths_mainline?.trend_state)}
                        </span>
                        <span className="px-2 py-1 rounded-full border text-xs font-medium text-gray-700 bg-gray-50 border-gray-100">
                          风险:{riskText(theme.ths_mainline?.risk_level)}
                        </span>
                      </div>

                      <div className="mt-4 grid grid-cols-2 xl:grid-cols-4 gap-3 text-sm">
                        <div className="bg-gray-50 rounded-lg p-3">
                          <div className="text-gray-500">主线排名</div>
                          <div className="font-semibold text-gray-900">
                            {theme.ths_mainline?.mainline_rank ?? '--'}
                          </div>
                        </div>
                        <div className="bg-gray-50 rounded-lg p-3">
                          <div className="text-gray-500">主线分</div>
                          <div className="font-semibold text-gray-900">
                            {theme.base_score ?? '--'}
                          </div>
                        </div>
                        <div className="bg-gray-50 rounded-lg p-3">
                          <div className="text-gray-500">共振分</div>
                          <div className="font-semibold text-gray-900">
                            {theme.resonance_score ?? '--'}
                          </div>
                        </div>
                        <div className="bg-gray-50 rounded-lg p-3">
                          <div className="text-gray-500">配置候选</div>
                          <div className="font-semibold text-gray-900">
                            {theme.config_candidate_count ?? 0}
                          </div>
                        </div>
                        <div className="bg-gray-50 rounded-lg p-3">
                          <div className="text-gray-500">机构候选</div>
                          <div className="font-semibold text-gray-900">
                            {theme.institutional_candidate_count ?? 0}
                          </div>
                        </div>
                        <div className="bg-gray-50 rounded-lg p-3">
                          <div className="text-gray-500">交易候选</div>
                          <div className="font-semibold text-gray-900">
                            {theme.trading_candidate_count ?? 0}
                          </div>
                        </div>
                      </div>

                      <div className="mt-4 space-y-2 text-sm">
                        <div className="text-gray-700">
                          配置龙头：
                          <span className="text-gray-900 ml-1">
                            {configNames.length ? configNames.join(' / ') : '--'}
                          </span>
                        </div>
                        <div className="text-gray-700">
                          机构关注：
                          <span className="text-gray-900 ml-1">
                            {institutionalNames.length ? institutionalNames.join(' / ') : '--'}
                          </span>
                        </div>
                        <div className="text-gray-700">
                          交易龙头：
                          <span className="text-gray-900 ml-1">
                            {tradingNames.length ? tradingNames.join(' / ') : '--'}
                          </span>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="text-sm text-gray-500">暂无赛道审阅数据</div>
            )}
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Target size={20} />
              建议层候选
            </h3>
            {candidates.length ? (
              <div className="space-y-4">
                {candidates.map((item) => {
                  const tags = thematicBadges(item.thematic_tags)
                  const candidateTypes = Array.isArray(item.leader_summary?.candidate_types)
                    ? item.leader_summary.candidate_types
                    : []
                  const reasons = Array.isArray(item.recommendation_reasons)
                    ? item.recommendation_reasons
                    : []
                  const riskFlags = Array.isArray(item.risk_flags) ? item.risk_flags : []
                  return (
                    <div key={item.stock_code} className="rounded-lg border border-gray-200 p-4">
                      <div className="flex items-start justify-between gap-3 flex-wrap">
                        <div>
                          <div className="text-lg font-semibold text-gray-900">
                            {item.stock_name || '--'}
                            <StockCodeLink
                              code={item.stock_code}
                              className="ml-2 text-sm text-gray-500 hover:text-blue-600 hover:underline"
                            >
                              {item.stock_code || '--'}
                            </StockCodeLink>
                          </div>
                          <div className="text-sm text-gray-500 mt-1">
                            排名 #{item.recommendation_rank ?? '--'}
                          </div>
                        </div>
                        <span
                          className={`inline-flex items-center px-3 py-1 rounded-full border text-sm font-medium ${recommendationClass(
                            item.recommendation_status
                          )}`}
                        >
                          {item.recommendation_status || '--'}
                        </span>
                      </div>

                      <div className="mt-3 flex items-center gap-2 flex-wrap">
                        {candidateTypes.map((candidateType) => (
                          <span
                            key={candidateType}
                            className="px-2 py-1 rounded-full border text-xs font-medium text-gray-700 bg-gray-50 border-gray-100"
                          >
                            {candidateTypeText(candidateType)}
                          </span>
                        ))}
                        {tags.map((tag) => (
                          <span
                            key={tag.label}
                            className={`px-2 py-1 rounded-full border text-xs font-medium ${tag.className}`}
                          >
                            {tag.label}
                          </span>
                        ))}
                      </div>
                      <SpecialMarkerSection
                        markers={item.special_markers}
                        notes={item.special_marker_notes}
                        compact
                      />

                      <div className="mt-4 text-sm text-gray-700">
                        说明：
                        <span className="text-gray-900 ml-1">
                          {reasons.length ? reasons.join(' / ') : '--'}
                        </span>
                      </div>
                      <div className="mt-2 text-sm text-gray-700">
                        风险标记：
                        <span className="text-gray-900 ml-1">
                          {riskFlags.length ? riskFlags.join(' / ') : '--'}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="text-sm text-gray-500">暂无候选审阅数据</div>
            )}
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Link2 size={20} />
              联动摘要
            </h3>
            {links.length ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">候选</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">建议</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">候选类型</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">渗透阶段</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-700">命中赛道</th>
                    </tr>
                  </thead>
                  <tbody>
                    {links.map((item) => {
                      const candidateTypes = Array.isArray(item.candidate_types)
                        ? item.candidate_types.map(candidateTypeText)
                        : []
                      const matchedThemes = Array.isArray(item.matched_themes)
                        ? item.matched_themes.map((theme) => theme.concept_name).filter(Boolean)
                        : []
                      const penetrationValues = Array.isArray(item.penetration_values)
                        ? item.penetration_values
                        : []
                      return (
                        <tr key={item.stock_code} className="border-b border-gray-100">
                          <td className="py-3 px-4">
                            <div className="text-gray-900 font-medium">{item.stock_name || '--'}</div>
                            <div className="text-gray-500 text-sm">
                              <StockCodeLink
                                code={item.stock_code}
                                className="hover:text-blue-600 hover:underline"
                              >
                                {item.stock_code || '--'}
                              </StockCodeLink>
                            </div>
                            <SpecialMarkerSection
                              markers={item.special_markers}
                              notes={item.special_marker_notes}
                              compact
                            />
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`inline-flex items-center px-2 py-1 rounded-full border text-xs font-medium ${recommendationClass(
                                item.recommendation_status
                              )}`}
                            >
                              {item.recommendation_status || '--'}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-sm text-gray-700">
                            {candidateTypes.length ? candidateTypes.join(' / ') : '--'}
                          </td>
                          <td className="py-3 px-4 text-sm text-gray-700">
                            {penetrationValues.length ? penetrationValues.join(' / ') : '--'}
                          </td>
                          <td className="py-3 px-4 text-sm text-gray-700">
                            {matchedThemes.length ? matchedThemes.join(' / ') : '--'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-sm text-gray-500">暂无联动摘要</div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
