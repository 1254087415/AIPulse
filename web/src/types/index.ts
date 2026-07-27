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

export type FollowedUpStatus = 'active' | 'paused' | 'auth_failed'
export type FollowedUpHealth = 'healthy' | 'warning' | 'error'
export type CollectorStrategy = 'uapi' | 'html'

export interface FollowedUp {
  id: string
  platform: string
  uid: string
  display_name: string
  profile_url: string
  collector_strategy: CollectorStrategy
  last_cursor_id: string | null
  fetch_interval_minutes: number
  is_active: boolean
  status: FollowedUpStatus
  health: FollowedUpHealth
  last_checked_at: string | null
  last_error: string | null
  failed_at: string | null
  config: Record<string, unknown> | null
  created_at: string
  updated_at: string
  deleted_at: string | null
}

export interface FollowedUpCreate {
  platform: string
  uid: string
  display_name?: string | null
  profile_url: string
  collector_strategy?: CollectorStrategy
  fetch_interval_minutes?: number
  config?: Record<string, unknown> | null
}

export interface FollowedUpUpdate {
  display_name?: string | null
  collector_strategy?: CollectorStrategy
  fetch_interval_minutes?: number
  is_active?: boolean | null
  status?: FollowedUpStatus | null
  config?: Record<string, unknown> | null
}

export interface FollowedUpHealthSnapshot {
  id: string
  health: FollowedUpHealth
  last_checked_at: string | null
  last_error: string | null
  failed_at: string | null
  is_active: boolean
  status: FollowedUpStatus
  fetch_interval_minutes: number
}

export interface FollowedUpOverview {
  followed_up: FollowedUp
  health: FollowedUpHealthSnapshot
  recent_jobs: Array<Record<string, unknown>>
  recent_learning_events: Array<Record<string, unknown>>
  recent_collections: Array<Record<string, unknown>>
}

export type SummaryJobStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'timeout'
  | 'cancelled'

export interface SummaryJob {
  id: string
  video_id: string
  hotspot_id: string | null
  title: string | null
  up_name: string | null
  status: SummaryJobStatus
  error: string | null
  note_path: string | null
  event_id: string | null
  reminder_id: string | null
  steps_emitted: number | null
  intermediate_steps: Array<Record<string, unknown>>
  created_at: string | null
  updated_at: string | null
  started_at: string | null
  completed_at: string | null
}

export interface SummaryEnqueueResult {
  job_id: string
  status: SummaryJobStatus
  reused: boolean
  video_id: string
}

export type SummaryEventType =
  | 'started'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'timeout'
  | 'closing'
  | 'heartbeat'
  | 'error'

export interface SummaryEvent {
  type: SummaryEventType
  [key: string]: unknown
}

export type SettingsValue = string | number | boolean | null

export interface SettingsSection {
  [key: string]: SettingsValue
}

export interface SettingsResponse {
  kimi: SettingsSection
  obsidian: SettingsSection
  wechat: SettingsSection
  feishu: SettingsSection
}

export type SettingsUpdate = Record<string, SettingsValue | undefined>
