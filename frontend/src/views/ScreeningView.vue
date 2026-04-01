<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useSchemeStore } from '@/stores/scheme'
import { useScreeningStore } from '@/stores/screening'
import { schemesApi, screeningApi } from '@/api'
import type { Scheme, ForwardPerformance, ForwardSummaryDay } from '@/api'
import { ElMessage } from 'element-plus'
import ResultTable from '@/components/ResultTable.vue'

const schemeStore = useSchemeStore()
const screeningStore = useScreeningStore()

const selectedSchemeId = ref<number | null>(null)
const selectedDate = ref('')
const fullScheme = ref<Scheme | null>(null)
const forwardData = ref<ForwardPerformance | null>(null)
const checkedRuleIds = ref<number[]>([])

onMounted(async () => {
  await Promise.all([schemeStore.fetchSchemes(), screeningStore.fetchLatestDate()])
  selectedDate.value = screeningStore.latestTradeDate
  if (schemeStore.schemes.length > 0) {
    selectedSchemeId.value = schemeStore.schemes[0]!.id
  }
})

const selectedScheme = computed(() =>
  schemeStore.schemes.find(s => s.id === selectedSchemeId.value) || null
)

async function runScreening() {
  if (!selectedSchemeId.value || !selectedDate.value) {
    ElMessage.warning('请选择方案和日期')
    return
  }
  forwardData.value = null
  try {
    const [, schemeRes] = await Promise.all([
      screeningStore.runScreening(selectedSchemeId.value, selectedDate.value),
      schemesApi.get(selectedSchemeId.value),
    ])
    fullScheme.value = schemeRes.data
    ElMessage.success('选股完成')
    // 后台异步获取后续表现（不阻塞主结果展示）
    const resultId = screeningStore.currentResult?.id
    if (resultId) {
      screeningApi.getForward(resultId).then(r => { forwardData.value = r.data }).catch(() => {})
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '选股失败')
  }
}

// Sync checkedRuleIds whenever the loaded scheme changes (default: all checked)
watch(fullScheme, (scheme) => {
  checkedRuleIds.value = scheme?.rules?.filter(r => r.enabled).map(r => r.id) ?? []
})

const enabledRules = computed(() => fullScheme.value?.rules?.filter(r => r.enabled) ?? [])

// Stocks from current result that pass all checked rules
const filteredDetails = computed(() => {
  const details = screeningStore.currentResult?.details ?? []
  if (checkedRuleIds.value.length === 0) return details
  return details.filter(stock => {
    const rr = stock.rule_results ?? {}
    return checkedRuleIds.value.every(rid => rr[String(rid)] === true)
  })
})

// Recompute forward summary based on filteredDetails
const computedSummary = computed((): ForwardPerformance['summary'] => {
  if (!forwardData.value) return {}
  const result: ForwardPerformance['summary'] = {}
  const dates = forwardData.value.forward_dates
  ;(['t1', 't2', 't3'] as const).forEach((t, idx) => {
    const dateStr = dates[idx]
    if (!dateStr) return
    const vals = filteredDetails.value
      .map(s => forwardData.value!.stocks[s.ts_code]?.[t]?.pct_vs_t0)
      .filter((v): v is number => v != null)
    result[t] = {
      date: dateStr,
      avg_return: vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null,
      positive_count: vals.filter(v => v > 0).length,
      flat_count: vals.filter(v => v === 0).length,
      negative_count: vals.filter(v => v < 0).length,
      total_count: vals.length,
    }
  })
  return result
})

function toggleAllRules() {
  if (checkedRuleIds.value.length === enabledRules.value.length) {
    checkedRuleIds.value = []
  } else {
    checkedRuleIds.value = enabledRules.value.map(r => r.id)
  }
}

function fwdSummaryColor(val: number | null | undefined) {
  if (val == null) return ''
  return val > 0 ? 'color:#f56c6c;font-weight:700' : val < 0 ? 'color:#67c23a;font-weight:700' : ''
}

function fwdSummaryLabel(s: ForwardSummaryDay | undefined) {
  if (!s) return { date: '-', ret: '-', bar: '' }
  const sign = (s.avg_return ?? 0) > 0 ? '+' : ''
  const ret = s.avg_return != null ? `${sign}${s.avg_return.toFixed(2)}%` : '暂无数据'
  const total = s.total_count || 1
  const pos = Math.round((s.positive_count / total) * 100)
  return { date: s.date, ret, pos, neg: Math.round((s.negative_count / total) * 100), total: s.total_count }
}

function exportCsv() {
  const result = screeningStore.currentResult
  if (!result?.details?.length) return
  const fwd = forwardData.value
  const fwdDates = fwd?.forward_dates ?? []
  const headers = ['代码', '名称', '收盘价', '当日涨幅%', ...fwdDates.map((d, i) => `T+${i + 1}(${d})`), '换手率%', '流通市值(亿)', '匹配规则数', '总规则数', '全匹配']
  const rows = result.details.map(d => {
    const fwdCols = fwdDates.map((_, i) => {
      const key = `t${i + 1}` as 't1' | 't2' | 't3'
      const v = fwd?.stocks?.[d.ts_code]?.[key]
      return v?.pct_vs_t0 != null ? `${v.pct_vs_t0 > 0 ? '+' : ''}${v.pct_vs_t0.toFixed(2)}%` : ''
    })
    return [d.ts_code, d.stock_name || '', d.close?.toFixed(2) || '', d.pct_chg?.toFixed(2) || '', ...fwdCols, d.turnover_rate?.toFixed(2) || '', d.circ_mv ? (d.circ_mv / 10000).toFixed(2) : '', d.matched_rules, d.total_rules, d.is_full_match ? '是' : '否']
  })
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `选股结果_${result.trade_date}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div style="max-width:1800px; margin:0 auto">
    <!-- 控制面板 -->
    <el-card style="margin-bottom:16px">
      <el-form inline>
        <el-form-item label="选股方案">
          <el-select v-model="selectedSchemeId" placeholder="选择方案" style="width:240px">
            <el-option
              v-for="s in schemeStore.schemes" :key="s.id"
              :label="s.name + (s.is_builtin ? ' [内置]' : '')" :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="交易日期">
          <el-date-picker
            v-model="selectedDate" type="date"
            format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="选择日期"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="screeningStore.running"
            :disabled="!selectedSchemeId || !selectedDate"
            @click="runScreening"
            :icon="screeningStore.running ? undefined : 'Search'"
          >
            {{ screeningStore.running ? '正在筛选...' : '开始选股' }}
          </el-button>
          <el-button
            v-if="screeningStore.currentResult?.details?.length"
            @click="exportCsv" :icon="'Download'"
          >导出CSV</el-button>
        </el-form-item>
      </el-form>
      <div v-if="selectedScheme" style="margin-top:8px; color:#666; font-size:13px">
        <el-tag size="small" :type="selectedScheme.match_mode === 'all' ? 'primary' : 'warning'">
          {{ selectedScheme.match_mode === 'all' ? '全部匹配' : `部分匹配 (≥${selectedScheme.min_match}条)` }}
        </el-tag>
        <span style="margin-left:8px">{{ selectedScheme.rule_count }} 条规则</span>
        <span v-if="selectedScheme.description" style="margin-left:8px">{{ selectedScheme.description }}</span>
      </div>
    </el-card>

    <!-- 选股统计 -->
    <el-card v-if="screeningStore.currentResult" style="margin-bottom:16px">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-statistic title="总扫描股票" :value="screeningStore.currentResult.total_stocks" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="完全匹配" :value="screeningStore.currentResult.full_match_count">
            <template #suffix><el-tag type="success" size="small">全部规则</el-tag></template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="部分匹配" :value="screeningStore.currentResult.partial_match_count">
            <template #suffix><el-tag type="warning" size="small">≥最低规则</el-tag></template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic
            title="耗时"
            :value="screeningStore.currentResult.duration_seconds?.toFixed(1) || '-'"
            suffix="秒"
          />
        </el-col>
      </el-row>
    </el-card>

    <!-- 后续表现汇总 -->
    <el-card v-if="forwardData" style="margin-bottom:16px">
      <template #header>
        <span style="font-weight:600">
          等权组合后续表现
          <span style="font-size:13px; color:#888; font-weight:400; margin-left:8px">
            — 若按选股日收盘价等权买入，后续各交易日平均收益
          </span>
          <span v-if="enabledRules.length > 0" style="font-size:13px; color:#409eff; font-weight:400; margin-left:12px">
            当前 {{ filteredDetails.length }} 只
          </span>
        </span>
      </template>

      <!-- 规则复选框过滤 -->
      <div v-if="enabledRules.length > 0"
        style="margin-bottom:14px; padding:10px 14px; background:#f5f7fa; border-radius:6px; display:flex; align-items:flex-start; gap:10px; flex-wrap:wrap">
        <span style="font-size:13px; color:#606266; white-space:nowrap; padding-top:2px; flex-shrink:0">按规则筛选：</span>
        <el-checkbox-group v-model="checkedRuleIds" size="small" style="display:flex; flex-wrap:wrap; gap:6px">
          <el-checkbox
            v-for="r in enabledRules" :key="r.id" :value="r.id"
            style="margin-right:0; height:auto"
          >{{ r.name }}</el-checkbox>
        </el-checkbox-group>
        <el-button link size="small" style="flex-shrink:0; padding-top:2px" @click="toggleAllRules">
          {{ checkedRuleIds.length === enabledRules.length ? '全不选' : '全选' }}
        </el-button>
      </div>

      <el-row :gutter="24">
        <el-col v-for="t in (['t1','t2','t3'] as const)" :key="t" :span="8">
          <template v-if="computedSummary[t] && computedSummary[t]!.total_count > 0">
            <div style="text-align:center; padding:8px 0">
              <div style="font-size:13px; color:#888; margin-bottom:4px">
                {{ fwdSummaryLabel(computedSummary[t]).date }}
              </div>
              <div style="font-size:28px; font-weight:700; margin-bottom:8px"
                :style="fwdSummaryColor(computedSummary[t]!.avg_return)">
                {{ fwdSummaryLabel(computedSummary[t]).ret }}
              </div>
              <div style="display:flex; justify-content:center; gap:12px; font-size:13px">
                <span style="color:#f56c6c">↑ {{ computedSummary[t]!.positive_count }} 只</span>
                <span style="color:#909399">→ {{ computedSummary[t]!.flat_count }} 只</span>
                <span style="color:#67c23a">↓ {{ computedSummary[t]!.negative_count }} 只</span>
              </div>
              <el-progress
                style="margin-top:8px"
                :percentage="computedSummary[t]!.total_count > 0
                  ? Math.round(computedSummary[t]!.positive_count / computedSummary[t]!.total_count * 100)
                  : 0"
                :color="'#f56c6c'"
                :stroke-width="6"
                :format="(p: number) => `胜率 ${p}%`"
              />
            </div>
          </template>
          <template v-else>
            <div style="text-align:center; color:#bbb; padding:20px 0; font-size:13px">暂无数据</div>
          </template>
        </el-col>
      </el-row>
    </el-card>

    <!-- 结果表格 -->
    <ResultTable
      v-if="screeningStore.currentResult"
      :result="screeningStore.currentResult"
      :scheme="fullScheme"
      :forward="forwardData"
    />
  </div>
</template>
