export function formatDateTime(value: string | Date | null, fallback = ''): string {
  if (!value) {
    return fallback
  }

  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) {
    return fallback
  }
  return date.toLocaleString('zh-CN')
}
