import { describe, it, expect } from 'vitest'
import {
  summarizeError,
  summarizeTrigger,
  summarizeClassPath,
  summarizeFuncPath,
} from '../errorMessage'

describe('summarizeError', () => {
  it('returns a friendly message for Kimi 401 invalid_authentication_error', () => {
    const raw =
      "Error code: 401 - {'error': {'message': 'The API Key appears to be invalid or may have expired. Please verify your credentials and try again.', 'type': 'invalid_authentication_error'}}"

    const result = summarizeError(raw)

    expect(result.summary).toBe('API Key 失效，请到 系统 页检查 LLM 配置')
    expect(result.technical).toBe(raw)
  })

  it('returns a friendly message for plain invalid_authentication_error', () => {
    const result = summarizeError('invalid_authentication_error')
    expect(result.summary).toBe('API Key 失效，请到 系统 页检查 LLM 配置')
  })

  it('returns a friendly message for API key not valid', () => {
    const result = summarizeError('API Key not valid. Please pass a valid API key.')
    expect(result.summary).toBe('API Key 失效，请到 系统 页检查 LLM 配置')
  })

  it('preserves Chinese business-side missing field error but normalizes prefix', () => {
    const result = summarizeError('业务侧结果字段缺失：hotspot_id, note_path 未填')
    expect(result.summary).toBe('业务结果字段缺失：hotspot_id、note_path')
    expect(result.technical).toBe('业务侧结果字段缺失：hotspot_id, note_path 未填')
  })

  it('returns a friendly message for httpx 301 redirect error', () => {
    const result = summarizeError(
      "Redirect response '301 Moved Permanently' for url 'https://example.com/old-path'",
    )
    expect(result.summary).toBe('采集目标已迁移或重定向（HTTP 301）')
  })

  it('returns a friendly message for httpx ConnectError', () => {
    const result = summarizeError('ConnectError: Connection refused')
    expect(result.summary).toBe('无法连接到上游服务')
  })

  it('returns a friendly message for timeout', () => {
    const result = summarizeError('ReadTimeout: timeout after 30s')
    expect(result.summary).toBe('请求超时，请稍后重试')
  })

  it('returns a friendly message for 429 rate limit', () => {
    const result = summarizeError('Error code: 429 - rate_limit_exceeded')
    expect(result.summary).toBe('请求过于频繁，请稍后重试')
  })

  it('returns a friendly message for 5xx server errors', () => {
    expect(summarizeError('Error code: 500 - internal_server_error').summary).toBe(
      '服务暂时不可用，请稍后重试',
    )
    expect(summarizeError('Error code: 503 - service_unavailable').summary).toBe(
      '服务暂时不可用，请稍后重试',
    )
  })

  it('returns a friendly message for 403 permission errors', () => {
    expect(summarizeError('Error code: 403 - permission_denied').summary).toBe('没有权限访问该资源')
  })

  it('returns a friendly message for 404 not found', () => {
    expect(summarizeError('Error code: 404 - not_found').summary).toBe('资源不存在或已下线')
  })

  it('falls back to truncated generic message for unknown errors', () => {
    const long = 'Unknown failure with a very long stack trace: ' + 'x'.repeat(500)
    const result = summarizeError(long)

    expect(result.summary.length).toBeLessThanOrEqual(120)
    expect(result.summary.endsWith('…')).toBe(true)
    expect(result.technical).toBe(long)
  })

  it('returns empty-state fallback for null/empty input', () => {
    expect(summarizeError(null).summary).toBe('操作失败，请稍后重试')
    expect(summarizeError(undefined).summary).toBe('操作失败，请稍后重试')
    expect(summarizeError('').summary).toBe('操作失败，请稍后重试')
    expect(summarizeError(null).technical).toBeNull()
  })
})

describe('summarizeTrigger', () => {
  it('translates interval minutes', () => {
    expect(summarizeTrigger('interval[0:30:00]')).toBe('每 30 分钟')
    expect(summarizeTrigger('interval[0:01:00]')).toBe('每 1 分钟')
    expect(summarizeTrigger('interval[0:05:00]')).toBe('每 5 分钟')
  })

  it('translates interval hours', () => {
    expect(summarizeTrigger('interval[6:00:00]')).toBe('每 6 小时')
    expect(summarizeTrigger('interval[1:00:00]')).toBe('每 1 小时')
  })

  it('translates interval days when days > 0', () => {
    // Python timedelta.__str__: "7 days, 0:00:00"
    expect(summarizeTrigger('interval[7 days, 0:00:00]')).toBe('每 7 天')
  })

  it('translates interval seconds', () => {
    expect(summarizeTrigger('interval[0:00:30]')).toBe('每 30 秒')
  })

  it('translates cron daily', () => {
    expect(summarizeTrigger("cron[hour='8', minute='0']")).toBe('每天 08:00')
    expect(summarizeTrigger("cron[hour='8', minute='30']")).toBe('每天 08:30')
  })

  it('translates cron weekday (0-4 → 工作日)', () => {
    expect(summarizeTrigger("cron[day_of_week='0-4', hour='9', minute='0']")).toBe('工作日 09:00')
  })

  it('translates cron weekend (sat,sun → 周末)', () => {
    expect(summarizeTrigger("cron[day_of_week='sat,sun', hour='10', minute='0']")).toBe(
      '周末 10:00',
    )
  })

  it('translates cron weekend (0,6 → 周末)', () => {
    expect(summarizeTrigger("cron[day_of_week='0,6', hour='10', minute='0']")).toBe('周末 10:00')
  })

  it('translates cron specific day of week', () => {
    expect(summarizeTrigger("cron[day_of_week='1', hour='9', minute='0']")).toBe('每周一 09:00')
  })

  it('falls back to original when format is unrecognized', () => {
    expect(summarizeTrigger('some-other-format')).toBe('some-other-format')
  })

  it('handles empty input', () => {
    expect(summarizeTrigger('')).toBe('未配置')
    expect(summarizeTrigger(null)).toBe('未配置')
    expect(summarizeTrigger(undefined)).toBe('未配置')
  })
})

describe('summarizeClassPath', () => {
  it('extracts short class name and keeps full path as technical', () => {
    const result = summarizeClassPath('aipulse.collectors.arxiv.ArxivCollector')
    expect(result.display).toBe('ArxivCollector')
    expect(result.technical).toBe('aipulse.collectors.arxiv.ArxivCollector')
  })

  it('handles already-short input', () => {
    const result = summarizeClassPath('ArxivCollector')
    expect(result.display).toBe('ArxivCollector')
    expect(result.technical).toBe('ArxivCollector')
  })

  it('falls back gracefully for empty input', () => {
    expect(summarizeClassPath('').display).toBe('未配置')
    expect(summarizeClassPath('').technical).toBe('')
  })
})

describe('summarizeFuncPath', () => {
  it('keeps module:func and stores full path as technical', () => {
    const result = summarizeFuncPath('aipulse.scheduler.jobs.followed_up_scan:run_scan')
    expect(result.display).toBe('followed_up_scan:run_scan')
    expect(result.technical).toBe('aipulse.scheduler.jobs.followed_up_scan:run_scan')
  })

  it('handles already-short input', () => {
    const result = summarizeFuncPath('foo:bar')
    expect(result.display).toBe('foo:bar')
    expect(result.technical).toBe('foo:bar')
  })

  it('falls back gracefully for empty input', () => {
    expect(summarizeFuncPath('').display).toBe('未配置')
    expect(summarizeFuncPath('').technical).toBe('')
  })
})