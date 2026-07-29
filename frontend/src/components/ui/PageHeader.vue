<script setup lang="ts">
/**
 * PageHeader — unified title block for every dashboard view (audit report H3).
 *
 * Replaces the three coexisting header conventions:
 *   A — chinese title + chinese subtitle
 *   B — english eyebrow ("FOLLOW-UP" / "LEARNING QUEUE" / "ACTION REQUIRED")
 *   C — "Phase N" placeholder pill (sources / keywords / jobs / digests)
 *
 * Usage:
 *   <PageHeader title="关注列表" subtitle="2 个 UP 主 · 全部启用">
 *     <template #actions>
 *       <AppButton variant="primary">添加 UP 主</AppButton>
 *     </template>
 *   </PageHeader>
 */
interface Props {
  /** Main title — short noun phrase (e.g. "关注列表", "处理记录"). */
  title: string
  /** Optional one-line supporting copy (e.g. "2 个 UP 主 · 全部启用"). */
  subtitle?: string
  /** Optional id on the heading element so `aria-labelledby` keeps working. */
  headingId?: string
}

withDefaults(defineProps<Props>(), {
  subtitle: '',
  headingId: undefined,
})
</script>

<template>
  <header class="page-header">
    <div class="page-header__text">
      <h2 :id="headingId" class="page-header__title">{{ title }}</h2>
      <p v-if="subtitle" class="page-header__subtitle">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin: 0 0 20px;
}

.page-header__text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.page-header__title {
  margin: 0;
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.page-header__subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.4;
}

.page-header__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
</style>