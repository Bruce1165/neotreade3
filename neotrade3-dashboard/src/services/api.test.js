import { afterEach, describe, expect, it, vi } from 'vitest'

import { API_ERROR_EVENT, downloadApi, fetchApi } from './api'

describe('fetchApi', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns parsed JSON for successful JSON responses', async () => {
    const payload = { ok: true, value: 42 }
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: {
        get: vi.fn().mockReturnValue('application/json; charset=utf-8'),
      },
      json: vi.fn().mockResolvedValue(payload),
      text: vi.fn(),
    })

    await expect(fetchApi('/api/example')).resolves.toEqual(payload)
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/example',
      expect.objectContaining({
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      }),
    )
  })

  it('returns text for successful non-JSON responses', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: {
        get: vi.fn().mockReturnValue('text/plain'),
      },
      text: vi.fn().mockResolvedValue('plain-text'),
    })

    await expect(fetchApi('healthz')).resolves.toBe('plain-text')
  })

  it('extracts nested API error messages from JSON error responses', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: {
        get: vi.fn().mockReturnValue('application/json'),
      },
      json: vi.fn().mockResolvedValue({
        error: {
          message: 'detailed backend error',
        },
      }),
      text: vi.fn(),
    })

    await expect(fetchApi('/api/example')).rejects.toThrow(
      'detailed backend error',
    )
  })

  it('preserves API error code and details for structured UI handling', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      headers: {
        get: vi.fn().mockReturnValue('application/json'),
      },
      json: vi.fn().mockResolvedValue({
        error: {
          code: 'authoritative_source_unavailable',
          message: 'authoritative source unavailable for resource: concept_theme_cache',
          details: {
            resource: 'concept_theme_cache',
            provider: 'tushare',
            fallback_attempted: false,
            fallback_provider: null,
          },
        },
      }),
      text: vi.fn(),
    })

    await expect(fetchApi('/api/example')).rejects.toMatchObject({
      message: 'authoritative source unavailable for resource: concept_theme_cache',
      code: 'authoritative_source_unavailable',
      status: 503,
      details: {
        resource: 'concept_theme_cache',
        provider: 'tushare',
        fallback_attempted: false,
        fallback_provider: null,
      },
    })
  })

  it('maps AbortError to a timeout message', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue({ name: 'AbortError' })

    await expect(
      fetchApi('/api/example', {}, { timeoutMs: 5 }),
    ).rejects.toThrow('请求超时：后端不可达或响应过慢（/api）')
  })

  it('emits a global api error event when http request fails', async () => {
    const onApiError = vi.fn()
    window.addEventListener(API_ERROR_EVENT, onApiError)
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      headers: {
        get: vi.fn().mockReturnValue('application/json'),
      },
      json: vi.fn().mockResolvedValue({
        error: {
          code: 'authoritative_source_unavailable',
          message: 'authoritative source unavailable for resource: concept_theme_cache',
        },
      }),
      text: vi.fn(),
    })

    await expect(fetchApi('/api/example')).rejects.toThrow(
      'authoritative source unavailable for resource: concept_theme_cache',
    )

    expect(onApiError).toHaveBeenCalledTimes(1)
    expect(onApiError.mock.calls[0][0].detail).toMatchObject({
      endpoint: '/api/example',
      message: 'authoritative source unavailable for resource: concept_theme_cache',
      status: 503,
      code: 'authoritative_source_unavailable',
    })

    window.removeEventListener(API_ERROR_EVENT, onApiError)
  })
})

describe('downloadApi', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns raw response for successful download requests', async () => {
    const response = {
      ok: true,
      status: 200,
      headers: {
        get: vi.fn().mockReturnValue('text/csv; charset=utf-8'),
      },
      blob: vi.fn(),
    }
    globalThis.fetch = vi.fn().mockResolvedValue(response)

    await expect(downloadApi('/api/download.csv')).resolves.toBe(response)
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/download.csv',
      expect.objectContaining({}),
    )
  })

  it('emits a global api error event when download request fails with http status', async () => {
    const onApiError = vi.fn()
    window.addEventListener(API_ERROR_EVENT, onApiError)
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      headers: {
        get: vi.fn().mockReturnValue('text/csv; charset=utf-8'),
      },
      json: vi.fn(),
    })

    await expect(downloadApi('/api/download.csv')).rejects.toMatchObject({
      message: 'HTTP 500',
      status: 500,
      endpoint: '/api/download.csv',
    })

    expect(onApiError).toHaveBeenCalledTimes(1)
    expect(onApiError.mock.calls[0][0].detail).toMatchObject({
      endpoint: '/api/download.csv',
      message: 'HTTP 500',
      status: 500,
      code: null,
    })

    window.removeEventListener(API_ERROR_EVENT, onApiError)
  })
})
