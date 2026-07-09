<script setup lang="ts">
import { ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { fetchKeywords, createKeyword } from '../api/keywords'
import KeywordList from '../components/keyword/KeywordList.vue'

const newKeyword = ref('')
const queryClient = useQueryClient()
const { data, isLoading } = useQuery({ queryKey: ['keywords'], queryFn: fetchKeywords })
const mutation = useMutation({
  mutationFn: createKeyword,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['keywords'] }),
})

function submit() {
  const value = newKeyword.value.trim()
  if (!value) return
  mutation.mutate(value)
  newKeyword.value = ''
}
</script>

<template>
  <main>
    <h1>关键词</h1>
    <form @submit.prevent="submit">
      <input
        v-model="newKeyword"
        placeholder="输入关键词"
        :disabled="mutation.isPending.value"
      />
      <button type="submit" :disabled="mutation.isPending.value">添加</button>
    </form>
    <p v-if="mutation.error" role="alert">添加失败</p>
    <p v-if="isLoading">加载中...</p>
    <KeywordList v-else :keywords="data?.data ?? []" />
  </main>
</template>

<style scoped>
form {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
input {
  flex: 1;
  padding: 0.5rem;
}
button {
  padding: 0.5rem 1rem;
}
</style>
