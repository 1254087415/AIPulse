import { describe, expect, it } from 'vitest'
import { isSafeUrl } from '../url'

describe('isSafeUrl', () => {
  it('returns true for http URLs', () => {
    expect(isSafeUrl('http://example.com')).toBe(true)
  })

  it('returns true for https URLs', () => {
    expect(isSafeUrl('https://example.com/path?query=1')).toBe(true)
  })

  it('returns false for javascript scheme URLs', () => {
    expect(isSafeUrl('javascript:alert(1)')).toBe(false)
  })

  it('returns false for data scheme URLs', () => {
    expect(isSafeUrl('data:text/html,<script>alert(1)</script>')).toBe(false)
  })

  it('returns false for invalid URLs', () => {
    expect(isSafeUrl('not a url')).toBe(false)
  })

  it('returns false for empty string', () => {
    expect(isSafeUrl('')).toBe(false)
  })

  it('returns false for file scheme URLs', () => {
    expect(isSafeUrl('file:///etc/passwd')).toBe(false)
  })

  it('returns false for mailto scheme URLs', () => {
    expect(isSafeUrl('mailto:test@example.com')).toBe(false)
  })
})
