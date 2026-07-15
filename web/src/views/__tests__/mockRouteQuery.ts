import { reactive } from 'vue'

export const mockRouteQuery = reactive<{ query: Record<string, string | string[]> }>({ query: {} })
