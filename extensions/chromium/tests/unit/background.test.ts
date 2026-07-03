import { describe, expect, it } from 'vitest';
import { cleanTrackingParams } from '../../src/utils';

describe('background helpers', () => {
  it('cleans url before submit', () => {
    const url = 'https://www.bilibili.com/video/BV1xx411c7mD?utm_source=share';
    expect(cleanTrackingParams(url)).toBe('https://www.bilibili.com/video/BV1xx411c7mD');
  });
});
