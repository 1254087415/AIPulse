import { onMounted, onUnmounted, readonly, ref, type Ref } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { createUseSseController, type SseStatus } from './useSseHelpers'

export function useSse(path: string): { status: Readonly<Ref<SseStatus>> } {
  const queryClient = useQueryClient()
  const status = ref<SseStatus>('connecting')

  const controller = createUseSseController({
    path,
    status,
    invalidateQueries: (options) => queryClient.invalidateQueries(options),
  })

  onMounted(() => controller.start())
  onUnmounted(() => controller.stop())

  return { status: readonly(status) }
}
