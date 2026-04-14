import { storeToRefs } from 'pinia'
import { useEmbeddedStore } from '@/stores/embedded'

/**
 * Exposes a reactive `embedded` boolean for hiding brand elements
 * when WeKnora is embedded in a parent system via iframe.
 */
export function useEmbedded() {
  const store = useEmbeddedStore()
  const { embedded } = storeToRefs(store)
  return { embedded }
}
