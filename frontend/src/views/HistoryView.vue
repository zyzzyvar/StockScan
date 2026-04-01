<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useScreeningStore } from '@/stores/screening'
import { useSchemeStore } from '@/stores/scheme'
import { schemesApi } from '@/api'
import type { Scheme } from '@/api'
import { ElMessage } from 'element-plus'
import ResultTable from '@/components/ResultTable.vue'

const screeningStore = useScreeningStore()
const schemeStore = useSchemeStore()

const selectedResult = ref<any>(null)
const selectedScheme = ref<Scheme | null>(null)

onMounted(async () => {
  await Promise.all([
    screeningStore.fetchResults(),
    schemeStore.fetchSchemes()
  ])
})

function schemeName(id: number) {
  return schemeStore.schemes.find(s => s.id === id)?.name || `方案 ${id}`
}

async function viewResult(id: number) {
  try {
    const result = await screeningStore.fetchResult(id)
    selectedResult.value = result
    // Fetch full scheme with rules for the rule detail popover
    const schemeRes = await schemesApi.get(result.scheme_id)
    selectedScheme.value = schemeRes.data
  } catch {
    ElMessage.error('加载失败')
  }
}
</script>

<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="selectedResult ? 10 : 24">
        <el-card>
          <template #header>历史选股记录</template>
          <el-table :data="screeningStore.results" stripe @row-click="(row: any) => viewResult(row.id)" style="cursor: pointer">
            <el-table-column label="日期" width="110">
              <template #default="{ row }">{{ row.trade_date }}</template>
            </el-table-column>
            <el-table-column label="方案">
              <template #default="{ row }">{{ schemeName(row.scheme_id) }}</template>
            </el-table-column>
            <el-table-column prop="total_stocks" label="扫描" width="70" />
            <el-table-column prop="full_match_count" label="全匹配" width="70" />
            <el-table-column prop="partial_match_count" label="部分匹配" width="80" />
            <el-table-column label="耗时" width="80">
              <template #default="{ row }">{{ row.duration_seconds?.toFixed(1) }}s</template>
            </el-table-column>
            <el-table-column label="运行时间" width="150">
              <template #default="{ row }">{{ row.created_at?.slice(0, 16).replace('T', ' ') }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col v-if="selectedResult" :span="14">
        <ResultTable
          :result="selectedResult"
          :scheme="selectedScheme"
          :forward="null"
        />
      </el-col>
    </el-row>
  </div>
</template>
