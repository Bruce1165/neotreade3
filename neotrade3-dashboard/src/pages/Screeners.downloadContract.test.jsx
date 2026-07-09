import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { API_ERROR_EVENT } from '../services/api'
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
    '/api/screeners?date=2026-06-09': {
      screeners_registry: {
        screeners: [
          {
            screener_id: 'shi_pan_xian',
            display_name: '势盘线',
            enabled: true,
            notes: '盘中强势筛选',
            tags: ['intraday'],
          },
        ],
      },
    },
    '/api/screeners/runs?date=2026-06-09': {
      screener_runs: [
        {
          screener_id: 'shi_pan_xian',
          target_date: '2026-06-08',
          requested_at: '2026-06-09T09:35:00Z',
          finished_at: '2026-06-09T09:36:00Z',
          status: 'ok',
          picks_count: 3,
        },
      ],
    },
    '/api/screeners/bulk-runs?limit=1': {
      bulk_runs: [
        {
          target_date: '2026-06-07',
        },
      ],
    },
  }
}

describe('Screeners download contract', () => {
  beforeEach(() => {
    mockUseApp.mockReturnValue({
      selectedDate: '2026-06-09',
    })
    const payloads = buildRunsPayloads()
    mockFetchApi.mockImplementation((url) => Promise.resolve(payloads[url]))
    vi.stubGlobal('fetch', vi.fn())
    window.URL.createObjectURL = vi.fn(() => 'blob:mock')
    window.URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('keeps local error text and emits global api error when download fails', async () => {
    const onApiError = vi.fn()
    window.addEventListener(API_ERROR_EVENT, onApiError)
    global.fetch.mockResolvedValue({
      ok: false,
      status: 500,
      headers: {
        get: vi.fn().mockReturnValue('text/csv; charset=utf-8'),
      },
      json: vi.fn(),
    })

    render(<Screeners />)

    await waitFor(() => {
      expect(screen.getByText('势盘线')).toBeTruthy()
    })

    fireEvent.click(screen.getAllByRole('button', { name: '下载 CSV' })[0])

    await waitFor(() => {
      expect(screen.getByText('下载失败：HTTP 500')).toBeTruthy()
    })

    expect(onApiError).toHaveBeenCalledTimes(1)
    expect(onApiError.mock.calls[0][0].detail).toMatchObject({
      endpoint: '/api/screeners/runs/2026-06-08/shi_pan_xian/download.csv',
      message: 'HTTP 500',
      status: 500,
    })

    window.removeEventListener(API_ERROR_EVENT, onApiError)
  })

  it('keeps download success path unchanged and does not emit global error', async () => {
    const onApiError = vi.fn()
    window.addEventListener(API_ERROR_EVENT, onApiError)
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

    expect(onApiError).not.toHaveBeenCalled()
    expect(screen.queryByText('下载失败：HTTP 500')).toBeNull()

    window.removeEventListener(API_ERROR_EVENT, onApiError)
  })
})
