import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Screeners from './Screeners'

const mockUseApp = vi.fn()
const mockFetchApi = vi.fn()

vi.mock('../context/AppContext', () => ({
  useApp: () => mockUseApp(),
}))

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    fetchApi: (...args) => mockFetchApi(...args),
  }
})

vi.mock('../components/DateSelector', () => ({
  default: ({ onRefresh, loading }) => (
    <button data-testid="date-selector-stub" onClick={onRefresh} disabled={loading}>
      DateSelector
    </button>
  ),
}))

function buildRunsPayloads() {
  return {
    [`/api/screeners?date=2026-06-09`]: {
      screeners_registry: {
        screeners: [
          {
            screener_id: 'shi_pan_xian',
            display_name: '势盘线',
            enabled: true,
            notes: '盘中强势筛选',
            tags: ['intraday'],
          },
          {
            screener_id: 'cup_handle_v4',
            display_name: '杯柄形态',
            enabled: false,
            notes: '形态筛选',
            tags: ['pattern'],
          },
        ],
      },
    },
    [`/api/screeners/runs?date=2026-06-09`]: {
      screener_runs: [
        {
          screener_id: 'shi_pan_xian',
          target_date: '2026-06-08',
          requested_at: '2026-06-09T09:35:00Z',
          finished_at: '2026-06-09T09:36:00Z',
          status: 'completed',
          picks_count: 3,
        },
      ],
    },
    '/api/screeners/bulk-runs?limit=1': {
      bulk_runs: [
        {
          target_date: '2026-06-09',
        },
      ],
    },
  }
}

function buildConfigPayload() {
  return {
    screener_config: {
      screener_id: 'shi_pan_xian',
      updated_at: '2026-06-09T10:00:00Z',
      schema: {
        type: 'object',
        properties: {
          threshold: {
            type: 'number',
            title: '阈值',
            description: '信号阈值',
          },
        },
      },
      default_parameters: {
        threshold: 1.5,
      },
      current_parameters: {
        threshold: 2.0,
      },
    },
  }
}

describe('Screeners', () => {
  beforeEach(() => {
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
    })
    vi.stubGlobal('fetch', vi.fn())
    window.URL.createObjectURL = vi.fn(() => 'blob:mock')
    window.URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('loads screener summary and recent runs', async () => {
    const payloads = buildRunsPayloads()
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))

    render(<Screeners />)

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/screeners?date=2026-06-09',
        {},
        { timeoutMs: 45000 },
      )
    })

    expect(screen.getByText('筛选器管理')).toBeTruthy()
    expect(screen.getByText('当日运行记录')).toBeTruthy()
    expect(screen.getByText('最近批量运行日期')).toBeTruthy()
    expect(screen.getByText('势盘线')).toBeTruthy()
    expect(screen.getByText('杯柄形态')).toBeTruthy()
    expect(screen.getByText('最近运行记录')).toBeTruthy()
    expect(screen.getByText('已完成')).toBeTruthy()
    expect(screen.getByText('2026-06-09')).toBeTruthy()
    expect(screen.getByText('2026-06-09T09:36:00Z')).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy()
  })

  it('keeps screener list visible when recent runs block fails', async () => {
    const payloads = buildRunsPayloads()
    mockFetchApi.mockImplementation((url) => {
      if (url === '/api/screeners/runs?date=2026-06-09') {
        return Promise.reject(new Error('最近运行记录请求超时'))
      }
      return Promise.resolve(payloads[url])
    })

    render(<Screeners />)

    await waitFor(() => {
      expect(screen.getByText('筛选器列表')).toBeTruthy()
    })

    expect(screen.getByText('势盘线')).toBeTruthy()
    expect(screen.getByText('杯柄形态')).toBeTruthy()
    expect(screen.getByText('最近运行记录请求超时')).toBeTruthy()
  })

  it('loads screener config and saves edited parameters', async () => {
    const runsPayloads = buildRunsPayloads()
    const configPayload = buildConfigPayload()

    mockFetchApi.mockImplementation((url, options) => {
      if (url === '/api/screeners/config/shi_pan_xian' && !options?.method) {
        return Promise.resolve(configPayload)
      }
      if (url === '/api/screeners/config/shi_pan_xian' && options?.method === 'POST') {
        return Promise.resolve(configPayload)
      }
      return Promise.resolve(runsPayloads[url])
    })

    render(<Screeners />)

    await waitFor(() => {
      expect(screen.getByText('势盘线')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: '参数配置' }))

    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: 'shi_pan_xian' } })

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/screeners/config/shi_pan_xian',
        {},
        { timeoutMs: 45000 },
      )
    })

    expect(screen.getByText(/已加载：shi_pan_xian/)).toBeTruthy()

    const input = screen.getByDisplayValue('2')
    fireEvent.change(input, { target: { value: '2.5' } })
    fireEvent.click(screen.getByRole('button', { name: '保存配置' }))

    await waitFor(() => {
      expect(mockFetchApi).toHaveBeenCalledWith(
        '/api/screeners/config/shi_pan_xian',
        {
          method: 'POST',
          body: JSON.stringify({
            current_parameters: {
              threshold: 2.5,
            },
            requested_by: 'dashboard.react',
          }),
        },
      )
    })

    expect(screen.getByText('保存成功')).toBeTruthy()
  })

  it('shows http status when download fails', async () => {
    const payloads = buildRunsPayloads()
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))
    global.fetch.mockResolvedValue({
      ok: false,
      status: 500,
      headers: {
        get: vi.fn().mockReturnValue('text/csv; charset=utf-8'),
      },
    })

    render(<Screeners />)

    await waitFor(() => {
      expect(screen.getByText('势盘线')).toBeTruthy()
    })

    fireEvent.click(screen.getAllByRole('button', { name: '下载 CSV' })[0])

    await waitFor(() => {
      expect(screen.getByText('下载失败：HTTP 500')).toBeTruthy()
    })
  })

  it('downloads recent run with run target date instead of selected date', async () => {
    const payloads = buildRunsPayloads()
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))
    const originalCreateElement = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tagName) => {
      const element = originalCreateElement(tagName)
      if (tagName === 'a') {
        element.click = vi.fn()
      }
      return element
    })
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: {
        get: vi.fn().mockReturnValue('text/csv; charset=utf-8'),
      },
      blob: () => Promise.resolve(new Blob(['csv'])),
    })

    render(<Screeners />)

    await waitFor(() => {
      expect(screen.getByText('势盘线')).toBeTruthy()
    })

    fireEvent.click(screen.getAllByRole('button', { name: '下载 CSV' })[0])

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/screeners/runs/2026-06-08/shi_pan_xian/download.csv',
        expect.objectContaining({})
      )
    })
  })
})
