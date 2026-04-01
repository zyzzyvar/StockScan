<script setup lang="ts">
import type { ScreeningResult, StockResult, Scheme, Rule, ForwardPerformance, ForwardDayData } from '@/api'
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  result: ScreeningResult
  scheme: Scheme | null
  forward: ForwardPerformance | null
}>()

const tableData = computed(() => props.result.details || [])

// ---- 颜色工具 ----
function pctColor(val: number | null | undefined) {
  if (val == null) return ''
  return val > 0 ? 'color:#f56c6c;font-weight:500' : val < 0 ? 'color:#67c23a;font-weight:500' : ''
}

function matchTagType(row: StockResult) {
  return row.is_full_match ? 'success' : 'warning'
}

function matchLabel(row: StockResult) {
  return row.is_full_match ? '全匹配' : `${row.matched_rules}/${row.total_rules}`
}

// ---- 规则明细 popover ----
const METRIC_SNAPSHOT: Record<string, keyof StockResult> = {
  pct_chg: 'pct_chg', turnover_rate: 'turnover_rate', volume_ratio: 'volume_ratio',
  circ_mv: 'circ_mv', pe_ttm: 'pe_ttm', pb: 'pb', close: 'close', vol: 'vol',
}

function formatMetricValue(rule: Rule, row: StockResult): string {
  const snapKey = METRIC_SNAPSHOT[rule.metric]
  if (snapKey) {
    const val = row[snapKey] as number | null
    if (val == null) return '-'
    if (rule.metric === 'circ_mv') return (val / 10000).toFixed(2) + '亿'
    if (rule.metric === 'pct_chg') return val.toFixed(2) + '%'
    if (rule.metric === 'turnover_rate') return val.toFixed(2) + '%'
    if (rule.metric === 'vol') return val.toFixed(0)
    return val.toFixed(2)
  }
  return '-'
}

function ruleRows(row: StockResult) {
  const rules = props.scheme?.rules || []
  return rules.map(r => ({
    rule: r,
    passed: row.rule_results ? row.rule_results[String(r.id)] : undefined,
  }))
}

// ---- T+1/T+2/T+3 ----
function fwdDay(row: StockResult, t: 't1' | 't2' | 't3'): ForwardDayData | null {
  return props.forward?.stocks?.[row.ts_code]?.[t] ?? null
}

function fwdLabel(row: StockResult, t: 't1' | 't2' | 't3'): string {
  const d = fwdDay(row, t)
  if (!d || d.pct_vs_t0 == null) return '-'
  const sign = d.pct_vs_t0 > 0 ? '+' : ''
  return `${d.close?.toFixed(2)} (${sign}${d.pct_vs_t0.toFixed(2)}%)`
}

function fwdStyle(row: StockResult, t: 't1' | 't2' | 't3') {
  const d = fwdDay(row, t)
  return pctColor(d?.pct_vs_t0 ?? null)
}

function fwdHeader(t: 't1' | 't2' | 't3') {
  const dates = props.forward?.forward_dates
  if (!dates) return t.toUpperCase()
  const idx = parseInt(t[1]!) - 1
  const ds = dates[idx]
  if (!ds) return t.toUpperCase()
  return `T+${idx + 1} (${ds.slice(5)})`  // e.g. "T+1 (03-20)"
}

// ---- 复制到剪贴板 ----
const copyMinMatch = ref<number | 'all'>('all')
const copying = ref(false)

const copyCount = computed(() => {
  const details = props.result.details || []
  if (copyMinMatch.value === 'all') return details.length
  return details.filter(d => d.matched_rules >= (copyMinMatch.value as number)).length
})

async function copyToClipboard() {
  const details = props.result.details || []
  const filtered = copyMinMatch.value === 'all'
    ? details
    : details.filter(d => d.matched_rules >= (copyMinMatch.value as number))
  if (!filtered.length) {
    ElMessage.warning('没有符合条件的股票')
    return
  }
  const codes = filtered.map(d => d.ts_code).join('\n')
  try {
    await navigator.clipboard.writeText(codes)
    ElMessage.success(`已复制 ${filtered.length} 只股票代码到剪贴板`)
  } catch {
    // 降级方案
    const ta = document.createElement('textarea')
    ta.value = codes
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    ElMessage.success(`已复制 ${filtered.length} 只股票代码到剪贴板`)
  }
}
</script>

<template>
  <el-card>
    <template #header>
      <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px">
        <span style="font-weight:600">
          选股结果 — {{ result.trade_date }}
          <el-tag size="small" style="margin-left:8px">共 {{ tableData.length }} 只</el-tag>
        </span>
        <!-- 复制工具栏 -->
        <div style="display:flex; align-items:center; gap:8px">
          <span style="font-size:13px; color:#666">复制代码：</span>
          <el-select v-model="copyMinMatch" size="small" style="width:130px">
            <el-option label="全部结果" value="all" />
            <el-option
              v-for="n in result.details?.[0]?.total_rules ?? 0"
              :key="n"
              :label="`匹配≥${n}条 (${result.details?.filter(d => d.matched_rules >= n).length ?? 0}只)`"
              :value="n"
            />
          </el-select>
          <el-button size="small" type="primary" :icon="'CopyDocument'" @click="copyToClipboard">
            复制 {{ copyCount }} 只
          </el-button>
        </div>
      </div>
    </template>

    <el-table
      :data="tableData"
      stripe
      :max-height="680"
      :default-sort="{ prop: 'matched_rules', order: 'descending' }"
      style="width:100%"
    >
      <el-table-column prop="ts_code" label="代码" min-width="100" fixed />
      <el-table-column prop="stock_name" label="名称" min-width="90" fixed />

      <!-- 匹配 -->
      <el-table-column label="匹配" min-width="90" fixed>
        <template #default="{ row }">
          <el-popover v-if="scheme?.rules?.length" placement="right" :width="350" trigger="hover">
            <template #reference>
              <el-tag :type="matchTagType(row)" size="small" style="cursor:pointer">{{ matchLabel(row) }}</el-tag>
            </template>
            <div style="font-size:13px">
              <div
                v-for="item in ruleRows(row)" :key="item.rule.id"
                style="display:flex; align-items:center; justify-content:space-between; padding:4px 0; border-bottom:1px solid #f0f0f0"
                :style="item.passed === false ? 'color:#f56c6c' : item.passed === true ? 'color:#67c23a' : ''"
              >
                <span style="flex:1; margin-right:8px; vertical-align:middle">
                  <el-icon v-if="item.passed === true" style="vertical-align:middle; margin-right:3px"><Select /></el-icon>
                  <el-icon v-else-if="item.passed === false" style="vertical-align:middle; margin-right:3px"><Close /></el-icon>
                  {{ item.rule.name }}
                </span>
                <span style="color:#606266; font-family:monospace; min-width:64px; text-align:right">
                  {{ formatMetricValue(item.rule, row) }}
                </span>
              </div>
            </div>
          </el-popover>
          <el-tag v-else :type="matchTagType(row)" size="small">{{ matchLabel(row) }}</el-tag>
        </template>
      </el-table-column>

      <!-- 选股日行情 -->
      <el-table-column prop="close" label="收盘价" min-width="90" sortable>
        <template #default="{ row }">{{ row.close?.toFixed(2) ?? '-' }}</template>
      </el-table-column>
      <el-table-column prop="pct_chg" label="当日涨幅" min-width="95" sortable>
        <template #default="{ row }">
          <span :style="pctColor(row.pct_chg)">{{ row.pct_chg != null ? (row.pct_chg > 0 ? '+' : '') + row.pct_chg.toFixed(2) + '%' : '-' }}</span>
        </template>
      </el-table-column>

      <!-- T+1 / T+2 / T+3 后续表现 -->
      <el-table-column v-if="forward" :label="fwdHeader('t1')" min-width="130" sortable
        :sort-method="(a: StockResult, b: StockResult) => (fwdDay(a,'t1')?.pct_vs_t0 ?? -999) - (fwdDay(b,'t1')?.pct_vs_t0 ?? -999)">
        <template #default="{ row }">
          <span :style="fwdStyle(row, 't1')">{{ fwdLabel(row, 't1') }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="forward && (forward.forward_dates?.length ?? 0) >= 2" :label="fwdHeader('t2')" min-width="130" sortable
        :sort-method="(a: StockResult, b: StockResult) => (fwdDay(a,'t2')?.pct_vs_t0 ?? -999) - (fwdDay(b,'t2')?.pct_vs_t0 ?? -999)">
        <template #default="{ row }">
          <span :style="fwdStyle(row, 't2')">{{ fwdLabel(row, 't2') }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="forward && (forward.forward_dates?.length ?? 0) >= 3" :label="fwdHeader('t3')" min-width="130" sortable
        :sort-method="(a: StockResult, b: StockResult) => (fwdDay(a,'t3')?.pct_vs_t0 ?? -999) - (fwdDay(b,'t3')?.pct_vs_t0 ?? -999)">
        <template #default="{ row }">
          <span :style="fwdStyle(row, 't3')">{{ fwdLabel(row, 't3') }}</span>
        </template>
      </el-table-column>

      <!-- 其他指标 -->
      <el-table-column prop="turnover_rate" label="换手率%" min-width="90" sortable>
        <template #default="{ row }">{{ row.turnover_rate?.toFixed(2) ?? '-' }}</template>
      </el-table-column>
      <el-table-column prop="volume_ratio" label="量比" min-width="80" sortable>
        <template #default="{ row }">{{ row.volume_ratio?.toFixed(2) ?? '-' }}</template>
      </el-table-column>
      <el-table-column prop="circ_mv" label="流通市值(亿)" min-width="115" sortable>
        <template #default="{ row }">{{ row.circ_mv ? (row.circ_mv / 10000).toFixed(2) : '-' }}</template>
      </el-table-column>
      <el-table-column prop="vol" label="成交量(手)" min-width="115" sortable>
        <template #default="{ row }">{{ row.vol?.toFixed(0) ?? '-' }}</template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
