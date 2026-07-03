export type SubmitMode = 'archive' | 'knowledge_check';

export interface FoundLink {
  url: string;
  platform: string;
  title?: string;
}

export interface SubmitPayload {
  url: string;
  content_type_hint?: string;
  source: 'browser_extension';
  mode: SubmitMode;
}

export interface SubmitResult {
  task_id: string;
  url: string;
}
