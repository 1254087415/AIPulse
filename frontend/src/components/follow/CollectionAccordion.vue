<script setup lang="ts">
/**
 * CollectionAccordion — single 合集 row used by FollowDetailView.
 *
 * Native <details>/<summary> keeps the markup accessible by default and
 * avoids a 3rd-party accordion dep. When the row is opened the body shows
 * a list of videos (or a placeholder when the collection is empty).
 */
import { computed } from 'vue'
import VideoListItem, { type VideoListItemVideo } from './VideoListItem.vue'

export interface CollectionItem {
  id: string
  title: string
  description?: string | null
  video_count: number
  videos?: VideoListItemVideo[]
}

interface Props {
  collection: CollectionItem
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'open-bilibili', bvid: string): void
}>()

const summary = computed(() => `${props.collection.video_count} 视频`)

const videos = computed(() => props.collection.videos ?? [])
</script>

<template>
  <div class="collection-row" data-testid="collection-row">
    <details>
      <summary>
        <span class="collection-row__title">{{ collection.title }}</span>
        <span class="collection-row__count">{{ summary }}</span>
      </summary>
      <p
        v-if="collection.description"
        class="collection-row__desc"
      >
        {{ collection.description }}
      </p>
      <ul v-if="videos.length > 0" class="collection-row__videos">
        <VideoListItem
          v-for="v in videos"
          :key="v.bvid"
          :video="v"
          @open-bilibili="(bvid: string) => emit('open-bilibili', bvid)"
        />
      </ul>
      <p v-else class="collection-row__empty">该合集暂无视频</p>
    </details>
  </div>
</template>

<style scoped>
.collection-row {
  background: var(--surface-elevated, #fff);
  border: 1px solid var(--border-subtle, #e5e5e5);
  border-radius: var(--radius-sm, 6px);
}

.collection-row details summary {
  padding: 12px 14px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  list-style: none;
}

.collection-row details summary::-webkit-details-marker {
  display: none;
}

.collection-row__title {
  font-weight: 500;
  color: var(--text-primary, #1a1a1a);
}

.collection-row__count {
  font-size: 12px;
  color: var(--text-secondary, #6b6b6b);
}

.collection-row__desc {
  margin: 0;
  padding: 0 14px 12px;
  color: var(--text-secondary, #6b6b6b);
  font-size: 13px;
  line-height: 1.5;
}

.collection-row__videos {
  list-style: none;
  margin: 0;
  padding: 0 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.collection-row__empty {
  margin: 0;
  padding: 0 14px 14px;
  font-size: 12px;
  color: var(--text-secondary, #6b6b6b);
}
</style>
