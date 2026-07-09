import { onMounted, onUnmounted } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { API_BASE } from '../api/client'

export function useSse(path: string) {
  const queryClient = useQueryClient()
  let eventSource: EventSource | null = null

  onMounted(() => {
    eventSource = new EventSource(`${API_BASE}${path}`)
    eventSource.addEventListener('hotspot.new', () => {
      queryClient.invalidateQueries({ queryKey: ['hotspots'], exact: false })
    })
  })

  onUnmounted(() => {
    eventSource?.close()
  })
}
