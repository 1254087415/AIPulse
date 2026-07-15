<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { Hotspot } from '../../types'
import { formatDateTime } from '../../lib/format'
import { isSafeUrl } from '../../lib/url'

const props = defineProps<{ hotspot: Hotspot }>()
const barWidth = `${Math.min(100, (props.hotspot.heat_score || 0) * 10)}%`
const safeUrl = computed(() => (isSafeUrl(props.hotspot.url) ? props.hotspot.url : null))
</script>

<template>
  <article class="reading panel">
    <div class="reading-body">
      <RouterLink
        :to="`/hotspot/${props.hotspot.id}`"
        class="reading-title"
      >
        {{ props.hotspot.title }}
      </RouterLink>
      <p v-if="props.hotspot.summary" class="reading-summary">
        {{ props.hotspot.summary }}
      </p>
      <div class="reading-meta">
        <span class="tag">{{ props.hotspot.source_type }}</span>
        <span v-if="props.hotspot.category" class="tag">{{ props.hotspot.category }}</span>
        <span class="tag" :class="{ 'tag-signal': props.hotspot.importance === 'high' }">
          {{ props.hotspot.importance }}
        </span>
        <time v-if="props.hotspot.published_at" class="mono slate">{{ formatDateTime(props.hotspot.published_at) }}</time>
        <a
          v-if="safeUrl"
          :href="safeUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="external"
          @click.stop
        >
          原文 →
        </a>
        <span v-else class="external disabled">原文不可用</span>
      </div>
    </div>
    <div class="reading-score" aria-label="热度分数">
      <span class="score-value">{{ props.hotspot.heat_score.toFixed(1) }}</span>
      <span class="score-bar" aria-hidden="true"><i :style="{ width: barWidth }"></i></span>
    </div>
  </article>
</template>

<style scoped>
.reading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}

.reading:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--grid);
}

.reading-body {
  min-width: 0;
  flex: 1;
}

.reading-title {
  display: block;
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--ink);
  margin-bottom: 6px;
}

.reading-title:hover {
  color: var(--signal);
}

.reading-summary {
  font-size: 14px;
  color: var(--slate);
  line-height: 1.55;
  margin: 0 0 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.reading-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.reading-meta time {
  font-size: 11px;
  letter-spacing: 0.02em;
}

.external {
  font-size: 11px;
  color: var(--signal);
  margin-left: auto;
}

.external.disabled {
  color: var(--slate);
  cursor: not-allowed;
}

.reading-score {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  min-width: 56px;
}

.score-value {
  font-family: var(--font-mono);
  font-size: 26px;
  font-weight: 700;
  line-height: 1;
  color: var(--signal);
}

.score-bar {
  display: block;
  width: 56px;
  height: 3px;
  background: var(--mist);
  border-radius: 2px;
  overflow: hidden;
}

.score-bar i {
  display: block;
  height: 100%;
  background: var(--signal);
  border-radius: 2px;
}

@media (max-width: 640px) {
  .reading {
    flex-direction: column;
    gap: 12px;
  }

  .reading-score {
    flex-direction: row;
    align-items: center;
    width: 100%;
  }

  .score-bar {
    flex: 1;
  }

  .external {
    margin-left: 0;
  }
}
</style>
