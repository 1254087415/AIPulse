import { describe, expect, it } from 'vitest'
import {
  formatDateTime,
  formatImportanceLabel,
  formatInterval,
  formatJobName,
  formatSourceLabel,
  formatStatusLabel,
} from '../format'

describe('formatDateTime', () => {
  it('formats valid values as YYYY-MM-DD HH:mm', () => {
    expect(formatDateTime('2026-07-24T11:05:59')).toBe('2026-07-24 11:05')
  })

  it('formats UTC timestamps in Asia/Shanghai', () => {
    expect(formatDateTime('2026-07-25T14:32:18Z')).toBe('2026-07-25 22:32')
  })

  it('formats date-only values without a timezone shift', () => {
    expect(formatDateTime('2026-07-29')).toBe('2026-07-29 00:00')
  })

  it('uses an em dash for missing values and preserves invalid values', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime(undefined)).toBe('—')
    expect(formatDateTime('not-a-date')).toBe('not-a-date')
  })
})

describe('display labels', () => {
  it('uses one interval expression', () => {
    expect(formatInterval(30)).toBe('30 分钟')
  })

  it.each([
    ['queued', '排队中'],
    ['pending', '等待处理'],
    ['running', '处理中'],
    ['completed', '已完成'],
    ['done', '已完成'],
    ['partial', '部分完成'],
    ['failed', '失败'],
    ['timeout', '超时'],
    ['worth_learning', '值得学习'],
    ['worth_notified', '已通知'],
    ['skipped', '已跳过'],
    ['archived', '已归档'],
    ['healthy', '健康'],
    ['warning', '需关注'],
    ['error', '异常'],
    ['active', '启用'],
    ['paused', '已暂停'],
    ['auth_failed', '认证失败'],
  ])('translates status %s', (status, label) => {
    expect(formatStatusLabel(status)).toBe(label)
  })

  it.each([
    ['high', '高'],
    ['medium', '中'],
    ['low', '低'],
  ])('translates importance %s', (importance, label) => {
    expect(formatImportanceLabel(importance)).toBe(label)
  })

  it.each([
    ['bilibili_up', 'B 站 UP 主'],
    ['arxiv', 'arXiv'],
    ['rss', 'RSS'],
  ])('translates source %s', (source, label) => {
    expect(formatSourceLabel(source)).toBe(label)
  })

  it('keeps unknown source labels intact', () => {
    expect(formatSourceLabel('wechat_mp')).toBe('wechat_mp')
  })

  it.each([
    ['Scan all enabled followed UP主', '扫描全部已启用 UP 主'],
    ['sync_all_sources', '同步全部来源'],
    ['generate_daily_digest', '生成每日摘要'],
    ['scan_obsidian_vault_job', '扫描 Obsidian 仓库'],
  ])('translates scheduled job name %s', (name, label) => {
    expect(formatJobName(name)).toBe(label)
  })

  it('uses an em dash for a missing status', () => {
    expect(formatStatusLabel(undefined)).toBe('—')
  })

  it('keeps unknown user-facing labels intact', () => {
    expect(formatStatusLabel('自定义状态')).toBe('自定义状态')
    expect(formatJobName('自定义任务')).toBe('自定义任务')
  })
})
