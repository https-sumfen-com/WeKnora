import { defineStore } from 'pinia'

const STORAGE_KEY = 'weknora_embedded'

export const useEmbeddedStore = defineStore('embedded', {
  state: () => ({
    embedded: sessionStorage.getItem(STORAGE_KEY) === '1',
  }),
  actions: {
    enable() {
      this.embedded = true
      sessionStorage.setItem(STORAGE_KEY, '1')
    },
    disable() {
      this.embedded = false
      sessionStorage.removeItem(STORAGE_KEY)
    },
  },
})
