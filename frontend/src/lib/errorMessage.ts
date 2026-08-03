/**
 * Error & technical-detail sanitizers for AIPulse web dashboard.
 *
 * 设计依据：spec §8.4 — 后端 sanitize + 前端统一文案；不直接展示原始报错。
 *
 * 导出：
 *  - summarizeError(raw)         → { summary, technical }，失败 tab / 来源卡 / 关注卡错误
 *  - summarizeTrigger(raw)       → 把 APScheduler 的 repr（`interval[0:30:00]` /
 *                                  `cron[hour='8', minute='0']`）转译为中文可读文案
 *  - summarizeClassPath(raw)     → { display, technical }，类路径末段作展示
 *  - summarizeFuncPath(raw)      → { display, technical }，模块:函数作展示
 *
 * 「technical」字段作为 title/tooltip 或折叠「技术详情」展示，原始报错信息可查但不刺眼。
 */

export interface ErrorSummary {
  /** 用户可见的中文友好文案（≤ 120 字符）。 */
  summary: string
  /** 原始报错，可放在 title/tooltip 或折叠区；不可读/无意义时为 null。 */
  technical: string | null
}

export interface TechnicalSummary {
  /** 卡片主区域展示的短名（无技术路径噪音）。 */
  display: string
  /** 折叠区 / tooltip 展示的完整路径。 */
  technical: string
}

/* ------------------------------------------------------------------ */
/* Error mapping                                                       */
/* ------------------------------------------------------------------ */

const STATUS_PATTERNS: ReadonlyArray<{
  test: (raw: string) => boolean
  summary: string
}> = [
  // 401: API Key 失效（Kimi / OpenAI / Anthropic 共用文案）
  {
    test: (r) =>
      /invalid[_ ]authentication[_ ]error/i.test(r) ||
      /api[_ ]key.{0,40}(invalid|expired|not[_ ]?valid)/i.test(r) ||
      /the api key appears to be invalid/i.test(r) ||
      /incorrect api key/i.test(r) ||
      /pass a valid api key/i.test(r),
    summary: 'API Key 失效，请到 系统 页检查 LLM 配置',
  },
  // 401: 通用鉴权失败
  {
    test: (r) => /\b401\b/.test(r) || /unauthorized/i.test(r),
    summary: '鉴权失败，请到 系统 页检查 Token',
  },
  // 402: 欠费
  {
    test: (r) => /\b402\b/.test(r) || /payment[_ ]required/i.test(r),
    summary: '账户欠费或余额不足',
  },
  // 403: 权限不足
  {
    test: (r) => /\b403\b/.test(r) || /permission[_ ]denied/i.test(r),
    summary: '没有权限访问该资源',
  },
  // 404
  {
    test: (r) => /\b404\b/.test(r) || /not[_ ]found/i.test(r),
    summary: '资源不存在或已下线',
  },
  // 408 / timeout
  {
    test: (r) =>
      /\b408\b/.test(r) ||
      /\btimeout\b/i.test(r) ||
      /readtimeout/i.test(r) ||
      /timed[_ ]?out/i.test(r),
    summary: '请求超时，请稍后重试',
  },
  // 413
  {
    test: (r) => /\b413\b/.test(r) || /payload[_ ]too[_ ]large/i.test(r),
    summary: '请求内容过大',
  },
  // 429
  {
    test: (r) => /\b429\b/.test(r) || /rate[_ ]limit/i.test(r) || /too[_ ]many[_ ]requests/i.test(r),
    summary: '请求过于频繁，请稍后重试',
  },
  // 5xx
  {
    test: (r) =>
      /\b(500|502|503|504)\b/.test(r) ||
      /internal[_ ]server[_ ]error/i.test(r) ||
      /service[_ ]unavailable/i.test(r) ||
      /bad[_ ]gateway/i.test(r),
    summary: '服务暂时不可用，请稍后重试',
  },
  // httpx 连接错误
  {
    test: (r) =>
      /connect[_ ]error/i.test(r) ||
      /connection[_ ]refused/i.test(r) ||
      /failed to establish a new connection/i.test(r),
    summary: '无法连接到上游服务',
  },
  // DNS / SSL / TLS
  {
    test: (r) =>
      /(dns|certificate|ssl|tls)[ _]?(lookup|error|verify|handshake|fail)/i.test(r) ||
      /name or service not known/i.test(r),
    summary: '网络层错误，请检查网络或稍后重试',
  },
]

const FALLBACK_SUMMARY = '操作失败，请稍后重试'
const MAX_SUMMARY_LENGTH = 120

function collapseWhitespace(raw: string): string {
  return raw.replace(/\s+/g, ' ').trim()
}

/**
 * Strip the noisy `"Error code: 401 - {'error': {...}}"` Python dict wrapper
 * to expose the inner message so downstream matchers can react to it.
 */
function unwrapPythonDict(raw: string): string {
  // "Error code: 401 - {'error': {'message': '...', 'type': '...'}}"
  // → "The API Key appears to be invalid..."
  const match = raw.match(/Error code:\s*\d+\s*-\s*\{.*?'message':\s*'([^']+)'/i)
  if (match && match[1]) {
    return match[1]
  }
  // Fallback: just strip "Error code: NNN -" prefix
  return raw.replace(/^Error code:\s*\d+\s*-\s*/i, '')
}

function truncateForSummary(raw: string): string {
  const clean = collapseWhitespace(raw)
  if (clean.length <= MAX_SUMMARY_LENGTH) return clean
  return clean.slice(0, MAX_SUMMARY_LENGTH - 1) + '…'
}

/** Normalize the legacy 「业务侧结果字段缺失：X 未填」 → 「业务结果字段缺失：X」。 */
function normalizeMissingFields(raw: string): string | null {
  const m = raw.match(/业务侧结果字段缺失[:：]\s*(.+?)(?:\s*未填)?$/)
  if (!m) return null
  const fields = m[1]
    .split(/[,，]/)
    .map((f) => f.trim())
    .filter(Boolean)
  if (fields.length === 0) return null
  return `业务结果字段缺失：${fields.join('、')}`
}

export function summarizeError(raw: string | null | undefined): ErrorSummary {
  if (!raw || !raw.trim()) {
    return { summary: FALLBACK_SUMMARY, technical: null }
  }

  const cleaned = collapseWhitespace(raw)

  // 0) 业务字段缺失归一化（必须在 patterns 之前，patterns 现在的列表里没它，但
  // 未来加新模式时可能误吞）。
  const normalized = normalizeMissingFields(cleaned)
  if (normalized) {
    return { summary: normalized, technical: cleaned }
  }

  // 1) httpx 3xx redirect with actual status code.
  const redirectMatch = cleaned.match(/redirect[_ ]response.{0,40}'(\d{3})/i)
  if (redirectMatch && redirectMatch[1]) {
    return {
      summary: `采集目标已迁移或重定向（HTTP ${redirectMatch[1]}）`,
      technical: cleaned,
    }
  }

  // 2) Unwrap Python dict wrapper if present.
  const inner = unwrapPythonDict(cleaned)
  const candidates = [inner, cleaned]

  // 3) Try each pattern against both wrapped and inner forms.
  for (const pattern of STATUS_PATTERNS) {
    for (const candidate of candidates) {
      if (pattern.test(candidate)) {
        return { summary: pattern.summary, technical: cleaned }
      }
    }
  }

  // 4) 兜底：截断到 120 字符，超长加省略号；原始信息放在 technical。
  return { summary: truncateForSummary(cleaned), technical: cleaned }
}

/* ------------------------------------------------------------------ */
/* Trigger translation                                                 */
/* ------------------------------------------------------------------ */

const WEEKDAY_NAMES: Record<string, string> = {
  '0': '周日',
  '1': '周一',
  '2': '周二',
  '3': '周三',
  '4': '周四',
  '5': '周五',
  '6': '周六',
  '7': '周日',
  sun: '周日',
  mon: '周一',
  tue: '周二',
  wed: '周三',
  thu: '周四',
  fri: '周五',
  sat: '周六',
}

const TRIGGER_FALLBACK = '未配置'

function parseCronFieldMap(raw: string): Record<string, string> {
  const out: Record<string, string> = {}
  // 匹配 hour='8', minute='0', day_of_week='0-4' 等键值对
  const re = /(\w+)\s*=\s*'([^']*)'/g
  let match: RegExpExecArray | null
  while ((match = re.exec(raw)) !== null) {
    out[match[1]] = match[2]
  }
  return out
}

function pad2(n: string): string {
  return n.padStart(2, '0')
}

function describeCronDayOfWeek(value: string): string {
  // 范围 mon-fri
  if (/^mon-fri$/i.test(value)) return '工作日'
  // 范围 sat,sun / sun,sat / 0,6 / 6,0 / 5-6 / sat-sun
  if (/^(sat,sun|sun,sat|sat-sun|sun-sat)$/i.test(value)) return '周末'
  if (/^(0,6|6,0|5-6|6-5)$/.test(value)) return '周末'
  // 范围 0-4 或 1-5 → 工作日（cron / APScheduler 两种约定都覆盖）
  if (/^(0-4|1-5)$/.test(value)) return '工作日'
  // 单一数字 / 名称
  const named = WEEKDAY_NAMES[value]
  if (named) return `每${named}`
  // 离散值，如 1,3,5 / mon,wed,fri / 5,6
  if (/^[\d,\-]+$/.test(value) || /^[a-z,]+$/i.test(value)) {
    const parts = value.split(',').map((v) => WEEKDAY_NAMES[v.trim()]).filter(Boolean)
    if (parts.length > 0) {
      // 全部工作日 → 工作日；全部周末 → 周末
      const workdays = parts.filter((p) => /^[一二三四五]/.test(p))
      const weekend = parts.filter((p) => /^[日六]/.test(p))
      if (workdays.length === parts.length && workdays.length >= 4) return '工作日'
      if (weekend.length === parts.length && weekend.length >= 1) return '周末'
      return `每${parts.join('、')}`
    }
  }
  return `周${value}`
}

export function summarizeTrigger(raw: string | null | undefined): string {
  if (!raw || !raw.trim()) return TRIGGER_FALLBACK

  const trimmed = raw.trim()

  // Python timedelta __str__ 格式：
  //   0 天 → "h:mm:ss"        → interval[0:30:00]
  //   N 天 → "N days, h:mm:ss" → interval[7 days, 0:00:00]
  // 解析为天数 / 小时 / 分钟 / 秒四部分。
  const intervalMatch = trimmed.match(
    /^interval\[(?:(\d+)\s*days?,\s*)?(\d+):(\d{2}):(\d{2})\]$/,
  )
  if (intervalMatch) {
    const [, dStr, hStr, mStr, sStr] = intervalMatch
    const days = Number(dStr ?? 0)
    const hours = Number(hStr)
    const minutes = Number(mStr)
    const seconds = Number(sStr)
    if (days > 0) return `每 ${days} 天`
    if (hours > 0) return `每 ${hours} 小时`
    if (minutes > 0) return `每 ${minutes} 分钟`
    if (seconds > 0) return `每 ${seconds} 秒`
    return trimmed
  }

  // cron[field='val', field='val', ...]
  if (trimmed.startsWith('cron[')) {
    const fields = parseCronFieldMap(trimmed)
    const hour = fields.hour ? pad2(fields.hour) : null
    const minute = fields.minute ? pad2(fields.minute) : '00'
    const time = hour ? `${hour}:${minute}` : null
    const dow = fields.day_of_week

    if (dow && time) return `${describeCronDayOfWeek(dow)} ${time}`
    if (dow) return describeCronDayOfWeek(dow)
    if (time) return `每天 ${time}`
    return trimmed
  }

  // 未识别格式，原样返回（仍作为展示兜底）
  return trimmed
}

/* ------------------------------------------------------------------ */
/* Class / function path shortening                                    */
/* ------------------------------------------------------------------ */

export function summarizeClassPath(raw: string | null | undefined): TechnicalSummary {
  const cleaned = (raw ?? '').trim()
  if (!cleaned) return { display: '未配置', technical: '' }

  // "aipulse.collectors.arxiv.ArxivCollector" → "ArxivCollector"
  const segments = cleaned.split('.')
  const display = segments[segments.length - 1] ?? cleaned
  return { display, technical: cleaned }
}

export function summarizeFuncPath(raw: string | null | undefined): TechnicalSummary {
  const cleaned = (raw ?? '').trim()
  if (!cleaned) return { display: '未配置', technical: '' }

  // "aipulse.scheduler.jobs.followed_up_scan:run_scan" → "followed_up_scan:run_scan"
  const lastDot = cleaned.lastIndexOf('.')
  if (lastDot === -1) return { display: cleaned, technical: cleaned }

  const display = cleaned.slice(lastDot + 1)
  return { display, technical: cleaned }
}