import { describe, expect, it } from 'vitest'
import { formatDateTime } from '../format'

describe('formatDateTime', () => {
  it('formats a Date instance to zh-CN locale string', () => {
    const date = new Date('2024-01-15T08:30:00.000Z')
    const result = formatDateTime(date)
    expect(result).toContain('2024')
    expect(result).toContain('15')
  })

  it('formats an ISO string to zh-CN locale string', () => {
    const result = formatDateTime('2024-01-15T08:30:00.000Z')
    expect(result).toContain('2024')
    expect(result).toContain('15')
  })

  it('returns default fallback when value is null', () => {
    expect(formatDateTime(null)).toBe('')
  })

  it('returns default fallback when value is empty string', () => {
    expect(formatDateTime('')).toBe('')
  })

  it('returns custom fallback when provided and value is null', () => {
    expect(formatDateTime(null, '未知时间')).toBe('未知时间')
  })

  it('returns default fallback when value is undefined', () => {
    expect(formatDateTime(undefined as unknown as string | Date | null)).toBe('')
  })

  it('returns custom fallback when value is undefined', () => {
    expect(formatDateTime(undefined as unknown as string | Date | null, '未知时间')).toBe('未知时间')
  })
})
