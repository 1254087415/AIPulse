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

export interface Job {
  id: string
  name: string
  func: string
  trigger: string
  next_run_time: string | null
}
