import { defineStore } from 'pinia'
import { ref } from 'vue'
import { screeningApi, marketApi, type ScreeningResult } from '@/api'

export const useScreeningStore = defineStore('screening', () => {
  const results = ref<ScreeningResult[]>([])
  const currentResult = ref<ScreeningResult | null>(null)
  const latestTradeDate = ref<string>('')
  const running = ref(false)

  async function fetchLatestDate() {
    const res = await marketApi.latestTradeDate()
    latestTradeDate.value = res.data.trade_date
    return res.data.trade_date
  }

  async function runScreening(schemeId: number, tradeDate: string) {
    running.value = true
    try {
      const res = await screeningApi.run(schemeId, tradeDate)
      currentResult.value = res.data
      return res.data
    } finally {
      running.value = false
    }
  }

  async function fetchResults(schemeId?: number) {
    const res = await screeningApi.results(schemeId)
    results.value = res.data
  }

  async function fetchResult(id: number) {
    const res = await screeningApi.getResult(id)
    currentResult.value = res.data
    return res.data
  }

  return { results, currentResult, latestTradeDate, running, fetchLatestDate, runScreening, fetchResults, fetchResult }
})
