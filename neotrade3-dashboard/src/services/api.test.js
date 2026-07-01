import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchApi } from './api'

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
})
