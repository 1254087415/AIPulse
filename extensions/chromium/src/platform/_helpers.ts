import type { FoundLink } from '../types';

export function extractMatches(
  candidates: Iterable<string>,
  patterns: { pattern: RegExp; platform: string; transform?: (match: RegExpMatchArray) => string }[],
  title: string | undefined
): FoundLink[] {
  const links: FoundLink[] = [];
  for (const candidate of candidates) {
    if (!candidate) continue;
    for (const { pattern, platform, transform } of patterns) {
      const match = candidate.match(pattern);
      if (match) {
        links.push({
          url: transform ? transform(match) : match[0],
          platform,
          title: title || undefined,
        });
        break;
      }
    }
  }
  return links;
}
