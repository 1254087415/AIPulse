<script setup lang="ts">
import type { FollowedUp } from '../../types'
import HealthBadge from './HealthBadge.vue'

defineProps<{
  followedUp: FollowedUp
  syncing?: boolean
}>()

const emit = defineEmits<{
  open: [id: string]
  sync: [id: string]
  delete: [id: string]
}>()
</script>

<template>
  <article class="follow-card">
    <header class="follow-card__header">
      <div class="follow-card__title">
        <h3>{{ followedUp.display_name }}</h3>
        <p class="follow-card__sub">
          <span class="platform">{{ followedUp.platform }}</span>
          <span class="dot">·</span>
          <span class="uid">{{ followedUp.uid }}</span>
        </p>
      </div>
      <HealthBadge :health="followedUp.health" :status="followedUp.status" />
    </header>

    <p v-if="followedUp.last_error" class="follow-card__error" role="alert">
      {{ followedUp.last_error }}
    </p>

    <footer class="follow-card__actions">
      <button type="button" class="btn" @click="emit('open', followedUp.id)">详情</button>
      <button
        type="button"
        class="btn"
        :disabled="syncing"
        @click="emit('sync', followedUp.id)"
      >
        {{ syncing ? '同步中…' : '立即同步' }}
      </button>
      <button type="button" class="btn danger" @click="emit('delete', followedUp.id)">删除</button>
    </footer>
  </article>
</template>

<style scoped>
.follow-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--mist);
  border-radius: 10px;
  background: var(--color-surface, #fff);
  transition: border-color 0.15s ease, transform 0.15s ease;
}

.follow-card:hover {
  border-color: var(--signal);
}

.follow-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.follow-card__title h3 {
  margin: 0 0 4px;
  font-size: 16px;
}

.follow-card__sub {
  margin: 0;
  font-size: 12px;
  color: var(--slate);
}

.dot {
  margin: 0 6px;
}

.follow-card__error {
  font-size: 12px;
  color: #c2410c;
  background: rgba(194, 65, 12, 0.08);
  padding: 6px 10px;
  border-radius: 6px;
}

.follow-card__actions {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 6px 12px;
  border: 1px solid var(--mist);
  border-radius: 6px;
  background: var(--color-surface, #fff);
  font-size: 13px;
  cursor: pointer;
  color: var(--ink);
}

.btn:hover {
  border-color: var(--signal);
  color: var(--signal);
}

.btn[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.danger:hover {
  border-color: #c2410c;
  color: #c2410c;
}
</style>