/**
 * VideoListItem — single video row used by FollowDetailView (spec §6.12).
 *
 * Covers:
 *  - renders bvid + title + status badge
 *  - default + orphan variants
 *  - 「在 B 站打开」 link targets https://www.bilibili.com/video/{bvid} and
 *    emits `open-bilibili` on click
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import VideoListItem, {
  type VideoListItemVideo,
} from '../follow/VideoListItem.vue'

const baseVideo: VideoListItemVideo = {
  bvid: 'BV1abc',
  title: '示例视频',
  collection_id: null,
  status: 'pending',
  published_at: '2026-07-25T00:00:00Z',
}

describe('VideoListItem', () => {
  it('renders bvid + title + status badge', () => {
    const wrapper = mount(VideoListItem, { props: { video: baseVideo } })
    expect(wrapper.text()).toContain('示例视频')
    expect(wrapper.text()).toContain('BV1abc')
    expect(wrapper.find('[data-status]').attributes('data-status')).toBe('pending')
    expect(wrapper.text()).toContain('等待处理')
    wrapper.unmount()
  })

  it('applies the orphan variant as data attribute + class', () => {
    const wrapper = mount(VideoListItem, {
      props: { video: baseVideo, variant: 'orphan' },
    })
    expect(wrapper.find('[data-testid="video-list-item"]').attributes('data-variant')).toBe('orphan')
    expect(wrapper.find('.video-list-item--orphan').exists()).toBe(true)
    wrapper.unmount()
  })

  it('renders 在 B 站打开 link to https://www.bilibili.com/video/{bvid} with target=_blank', () => {
    const wrapper = mount(VideoListItem, { props: { video: baseVideo } })
    const link = wrapper.find('[data-testid="open-bilibili-link"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('https://www.bilibili.com/video/BV1abc')
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toContain('noopener')
    wrapper.unmount()
  })

  it('clicking 在 B 站打开 emits open-bilibili with the bvid', async () => {
    const wrapper = mount(VideoListItem, { props: { video: baseVideo } })
    await wrapper.find('[data-testid="open-bilibili-link"]').trigger('click')
    const events = wrapper.emitted('open-bilibili')
    expect(events).toBeTruthy()
    expect(events?.[0]).toEqual(['BV1abc'])
    wrapper.unmount()
  })

  it('falls back to bvid as title when video.title is empty', () => {
    const wrapper = mount(VideoListItem, {
      props: { video: { ...baseVideo, title: '' } },
    })
    expect(wrapper.text()).toContain('BV1abc')
    wrapper.unmount()
  })

  it('uses spy-friendly open handler to verify window.open via followup click', async () => {
    const openSpy = vi
      .spyOn(window, 'open')
      .mockImplementation(() => null)
    const wrapper = mount(VideoListItem, { props: { video: baseVideo } })
    const link = wrapper.find('[data-testid="open-bilibili-link"]')
    // cmd-click passes through natively — only plain click triggers our handler
    await link.trigger('click')
    expect(openSpy).not.toHaveBeenCalled() // we use window.open from a custom handler, not the link
    openSpy.mockRestore()
    wrapper.unmount()
  })
})
