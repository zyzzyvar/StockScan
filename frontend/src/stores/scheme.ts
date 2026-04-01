import { defineStore } from 'pinia'
import { ref } from 'vue'
import { schemesApi, type Scheme } from '@/api'

export const useSchemeStore = defineStore('scheme', () => {
  const schemes = ref<Scheme[]>([])
  const currentScheme = ref<Scheme | null>(null)
  const loading = ref(false)

  async function fetchSchemes() {
    loading.value = true
    try {
      const res = await schemesApi.list()
      schemes.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchScheme(id: number) {
    const res = await schemesApi.get(id)
    currentScheme.value = res.data
    return res.data
  }

  async function createScheme(data: Partial<Scheme>) {
    const res = await schemesApi.create(data)
    schemes.value.push(res.data)
    return res.data
  }

  async function updateScheme(id: number, data: Partial<Scheme>) {
    const res = await schemesApi.update(id, data)
    const idx = schemes.value.findIndex(s => s.id === id)
    if (idx >= 0) schemes.value[idx] = { ...schemes.value[idx], ...res.data }
    if (currentScheme.value?.id === id) currentScheme.value = res.data
    return res.data
  }

  async function deleteScheme(id: number) {
    await schemesApi.delete(id)
    schemes.value = schemes.value.filter(s => s.id !== id)
    if (currentScheme.value?.id === id) currentScheme.value = null
  }

  async function copyScheme(id: number) {
    const res = await schemesApi.copy(id)
    schemes.value.push(res.data)
    return res.data
  }

  return { schemes, currentScheme, loading, fetchSchemes, fetchScheme, createScheme, updateScheme, deleteScheme, copyScheme }
})
