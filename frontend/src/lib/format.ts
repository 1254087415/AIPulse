const STATUS_LABELS: Readonly<Record<string, string>> = {
  queued: '排队中',
  pending: '等待处理',
  running: '处理中',
  completed: '已完成',
  done: '已完成',
  partial: '部分完成',
  failed: '失败',
  timeout: '超时',
  worth_learning: '值得学习',
  worth_notified: '已通知',
  skipped: '已跳过',
  archived: '已归档',
  healthy: '健康',
  warning: '需关注',
  error: '异常',
  active: '启用',
  paused: '已暂停',
  auth_failed: '认证失败',
}

const IMPORTANCE_LABELS: Readonly<Record<string, string>> = {
  high: '高',
  medium: '中',
  low: '低',
}

const JOB_NAME_LABELS: Readonly<Record<string, string>> = {
  'Scan all enabled followed UP主': '扫描全部已启用 UP 主',
  sync_all_sources: '同步全部来源',
  generate_daily_digest: '生成每日摘要',
  scan_obsidian_vault_job: '扫描 Obsidian 仓库',
}

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

function datePart(parts: Intl.DateTimeFormatPart[], type: Intl.DateTimeFormatPartTypes): string {
  return parts.find((part) => part.type === type)?.value ?? ''
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return `${value} 00:00`

  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}+08:00`
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return value

  const parts = DATE_TIME_FORMATTER.formatToParts(date)
  return `${datePart(parts, 'year')}-${datePart(parts, 'month')}-${datePart(parts, 'day')} ${datePart(parts, 'hour')}:${datePart(parts, 'minute')}`
}

export function formatInterval(minutes: number): string {
  return `${minutes} 分钟`
}

export function formatStatusLabel(status: string | null | undefined): string {
  if (!status) return '—'
  return STATUS_LABELS[status.toLowerCase()] ?? status
}

export function formatImportanceLabel(importance: string): string {
  return IMPORTANCE_LABELS[importance.toLowerCase()] ?? importance
}

export function formatJobName(name: string): string {
  return JOB_NAME_LABELS[name] ?? name
}
