import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import StockCodeLink from './StockCodeLink'
import { buildTonghuashunStockUrl, isSupportedAStockCode } from './stockCodeUtils'

describe('StockCodeLink', () => {
  afterEach(() => {
    cleanup()
  })

  it('builds tonghuashun url for supported a-share stock codes', () => {
    expect(isSupportedAStockCode('600000')).toBe(true)
    expect(isSupportedAStockCode('000333')).toBe(true)
    expect(buildTonghuashunStockUrl('600000')).toBe(
      'https://stockpage.10jqka.com.cn/600000/'
    )
  })

  it('keeps non-stock codes as plain text', () => {
    expect(isSupportedAStockCode('886042.TI')).toBe(false)
    expect(isSupportedAStockCode('BK001')).toBe(false)
    expect(buildTonghuashunStockUrl('886042.TI')).toBeNull()

    render(<StockCodeLink code="886042.TI" className="text-gray-500" />)

    expect(screen.getByText('886042.TI').closest('a')).toBeNull()
  })

  it('renders stock codes as outbound links', () => {
    render(<StockCodeLink code="000333" className="text-gray-500" />)

    expect(screen.getByRole('link', { name: '000333' }).getAttribute('href')).toBe(
      'https://stockpage.10jqka.com.cn/000333/'
    )
  })
})
