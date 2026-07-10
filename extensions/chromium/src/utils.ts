import type { FoundLink } from './types';

const TRACKING_PARAMS = [
  'spm_id_from',
  'from_source',
  'from_spmid',
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_content',
  'share_source',
  'share_medium',
  'timestamp',
  'vd_source',
  'spm_id_from',
];

export function cleanTrackingParams(url: string): string {
  try {
    const parsed = new URL(url);
    for (const param of TRACKING_PARAMS) {
      parsed.searchParams.delete(param);
    }
    return parsed.toString();
  } catch {
    return url;
  }
}

export function dedupeLinks(links: FoundLink[]): FoundLink[] {
  const seen = new Set<string>();
  const result: FoundLink[] = [];
  for (const link of links) {
    const cleaned = cleanTrackingParams(link.url);
    if (!seen.has(cleaned)) {
      seen.add(cleaned);
      result.push({ ...link, url: cleaned });
    }
  }
  return result;
}
