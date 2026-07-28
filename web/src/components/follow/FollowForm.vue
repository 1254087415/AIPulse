<script setup lang="ts">
import { reactive, computed } from 'vue'
import type { FollowedUpCreate } from '../../types'

const emit = defineEmits<{
  submit: [payload: FollowedUpCreate]
  cancel: []
}>()

const form = reactive({
  platform: 'bilibili',
  uid: '',
  display_name: '',
  profile_url: '',
  collector_strategy: 'uapi' as 'uapi' | 'html',
  fetch_interval_minutes: 30,
})

const profileUrlAuto = computed(() => {
  if (form.platform === 'bilibili' && form.uid) {
    return `https://space.bilibili.com/${form.uid}`
  }
  return form.profile_url
})

const isValid = computed(() => {
  if (!form.uid) return false
  const url = form.platform === 'bilibili' ? profileUrlAuto.value : form.profile_url
  return !!url && /^https?:\/\//.test(url)
})

function onSubmit() {
  if (!isValid.value) return
  const payload: FollowedUpCreate = {
    platform: form.platform,
    uid: form.uid.trim(),
    display_name: form.display_name.trim() || null,
    profile_url:
      form.platform === 'bilibili' ? profileUrlAuto.value : form.profile_url.trim(),
    collector_strategy: form.collector_strategy,
    fetch_interval_minutes: form.fetch_interval_minutes,
  }
  emit('submit', payload)
}
</script>

<template>
  <form class="follow-form" aria-label="添加 UP 主" @submit.prevent="onSubmit">
    <div class="field">
      <label for="platform">平台</label>
      <select id="platform" v-model="form.platform">
        <option value="bilibili">B站</option>
      </select>
    </div>

    <div class="field">
      <label for="uid">UID / MID</label>
      <input
        id="uid"
        v-model="form.uid"
        type="text"
        inputmode="numeric"
        placeholder="例：123456"
        required
      />
    </div>

    <div class="field">
      <label for="display_name">昵称（留空自动从 B 站抓）</label>
      <input
        id="display_name"
        v-model="form.display_name"
        type="text"
        placeholder="可选"
      />
    </div>

    <div v-if="form.platform !== 'bilibili'" class="field">
      <label for="profile_url">profile_url</label>
      <input
        id="profile_url"
        v-model="form.profile_url"
        type="url"
        placeholder="https://..."
        required
      />
    </div>

    <p v-else class="hint">
      profile_url 将自动填为 <code>{{ profileUrlAuto || 'https://space.bilibili.com/<uid>' }}</code>
    </p>

    <div class="row">
      <div class="field">
        <label for="collector_strategy">采集策略</label>
        <select id="collector_strategy" v-model="form.collector_strategy">
          <option value="uapi">uapi（官方 API）</option>
          <option value="html">html（页面解析）</option>
        </select>
      </div>
      <div class="field">
        <label for="interval">同步间隔（分钟）</label>
        <input
          id="interval"
          v-model.number="form.fetch_interval_minutes"
          type="number"
          min="1"
          max="10080"
        />
      </div>
    </div>

    <div class="actions">
      <button type="button" class="btn ghost" @click="emit('cancel')">取消</button>
      <button type="submit" class="btn primary" :disabled="!isValid">添加</button>
    </div>
  </form>
</template>

<style scoped>
.follow-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-size: 12px;
  color: var(--slate);
  font-weight: 600;
}

.field input,
.field select {
  padding: 8px 10px;
  border: 1px solid var(--mist);
  border-radius: 6px;
  background: var(--color-surface, #fff);
  font-size: 14px;
}

.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 6px;
}

.btn {
  padding: 8px 14px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  border: 1px solid var(--mist);
  background: var(--color-surface, #fff);
  color: var(--ink);
}

.btn.primary {
  background: var(--signal);
  border-color: var(--signal);
  color: #fff;
}

.btn.primary[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.ghost {
  background: transparent;
}

.hint {
  font-size: 12px;
  color: var(--slate);
}

.hint code {
  background: rgba(0, 0, 0, 0.04);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
}
</style>