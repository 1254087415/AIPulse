export interface Hotspot {
  id: string
  title: string
  url: string
  summary: string | null
  source_type: string
  heat_score: number
  importance: string
  category: string | null
  published_at: string | null
}

export interface Keyword {
  id: string
  value: string
  is_active: boolean
  notify_on_match: boolean
}

export interface Source {
  id: string
  name: string
  source_type: string
  collector_class: string
  config: Record<string, unknown> | null
  default_weight: number
  fetch_interval_minutes: number
  is_active: boolean
  last_fetched_at: string | null
  last_error: string | null
  failed_at: string | null
  created_at: string
  updated_at: string
}

export interface DailyDigest {
  id: string
  date: string
  title: string
  content: string
  top_hotspot_ids: string[] | null
  generated_at: string
  pushed_at: string | null
}

export interface Job {
  id: string
  name: string
  func: string
  trigger: string
  next_run_time: string | null
}
