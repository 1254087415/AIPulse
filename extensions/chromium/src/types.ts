export type SubmitMode = 'archive' | 'knowledge_check';

declare global {
  const __E2E__: boolean;
}

export interface SubtitleOption {
  id: string;
  lan: string;
  lanDoc: string;
  subtitleUrl: string;
}

export interface SubtitleEntry {
  from: number;
  to: number;
  content: string;
}

export interface VideoMetadata {
  title: string;
  platform: string;
  url: string;
  subtitleOptions: SubtitleOption[];
  subtitleEntries: SubtitleEntry[];
  selectedSubtitleLan: string;
  // Douyin official share short link (https://v.douyin.com/xxx), preferred by
  // the download pipeline when present.
  shareUrl?: string;
}

export interface FoundLink {
  url: string;
  platform: string;
  title?: string;
  metadata?: VideoMetadata;
}

export interface SubmitPayload {
  url: string;
  title?: string;
  content_type_hint?: string;
  source: 'browser_extension';
  mode: SubmitMode;
  tags?: string[];
  subtitle_text?: string;
  subtitle_language?: string;
}

export interface SubmitResult {
  task_id: string;
  url: string;
}
