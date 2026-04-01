<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { CandlestickChart, BarChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent,
  DataZoomComponent, MarkPointComponent, MarkLineComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { ElMessage } from 'element-plus'
import { useSchemeStore } from '@/stores/scheme'
import { backtestApi } from '@/api'
import type { BacktestResult, BacktestSchemeResult, BacktestPricePoint } from '@/api'

use([
  CanvasRenderer,
  CandlestickChart, BarChart,
  GridComponent, TooltipComponent, LegendComponent,
  DataZoomComponent, MarkPointComponent, MarkLineComponent,
])

const schemeStore = useSchemeStore()

const tsCode = ref('')
const dateRange = ref<[string, string]>(['', ''])
const selectedSchemeIds = ref<number[]>([])
const loading = ref(false)
const result = ref<BacktestResult | null>(null)
const activeSchemeIdx = ref(0)

onMounted(async () => {
  await schemeStore.fetchSchemes()
  if (schemeStore.schemes.length > 0) {
    selectedSchemeIds.value = [schemeStore.schemes[0]!.id]
  }
  // Default date range: last 3 months
  const end = new Date()
  const start = new Date()
  start.setMonth(start.getMonth() - 3)
  dateRange.value = [
    start.toISOString().slice(0, 10),
    end.toISOString().slice(0, 10),
  ]
})

async function runBacktest() {
  if (!tsCode.value.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }
  if (!dateRange.value[0] || !dateRange.value[1]) {
    ElMessage.warning('请选择日期范围')
    return
  }
  if (!selectedSchemeIds.value.length) {
    ElMessage.warning('请选择至少一个方案')
    return
  }
  loading.value = true
  try {
    const res = await backtestApi.run({
      ts_code: tsCode.value.trim(),
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
      scheme_ids: selectedSchemeIds.value,
    })
    result.value = res.data
    activeSchemeIdx.value = 0
    ElMessage.success('回测完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '回测失败')
  } finally {
    loading.value = false
  }
}

const activeScheme = computed<BacktestSchemeResult | null>(() =>
  result.value?.schemes[activeSchemeIdx.value] ?? null
)

// Scheme colors for match markers
const SCHEME_COLORS = ['#409eff', '#ff9900', '#67c23a', '#f56c6c', '#909399']

// Build ECharts candlestick option
const chartOption = computed(() => {
  if (!result.value?.price_series?.length) return {}

  const prices = result.value.price_series
  const dates = prices.map((p: BacktestPricePoint) => p.date)
  // ECharts candlestick: [open, close, low, high]
  const candleData = prices.map((p: BacktestPricePoint) => [p.open, p.close, p.low, p.high])
  const volumes = prices.map((p: BacktestPricePoint) => p.vol ?? 0)

  // Build markPoint data for each scheme — one arrow per matched day, offset by scheme index
  const schemeMarkPoints = (result.value.schemes ?? []).map((scheme: BacktestSchemeResult, si: number) => {
    const matchedDates = new Set(scheme.daily.filter(d => d.is_matched).map(d => d.date))
    const color = SCHEME_COLORS[si % SCHEME_COLORS.length]
    const markData = prices
      .filter((p: BacktestPricePoint) => matchedDates.has(p.date))
      .map((p: BacktestPricePoint) => ({
        name: scheme.scheme_name,
        coord: [p.date, p.low],
        symbolOffset: [si * 10 - (result.value!.schemes.length - 1) * 5, 8 + si * 14],
        itemStyle: { color },
        label: { show: false },
      }))
    return { name: scheme.scheme_name, color, markData }
  })

  return {
    animation: false,
    backgroundColor: '#fff',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any[]) => {
        const p = params[0]
        if (!p) return ''
        const date = p.name
        const [o, c, l, h] = p.value as [number, number, number, number]
        const pct = prices.find((x: BacktestPricePoint) => x.date === date)?.pct_chg ?? 0
        const color = c >= o ? '#f56c6c' : '#67c23a'
        let html = `<b>${date}</b><br/>
          开: ${o?.toFixed(2)}  高: ${h?.toFixed(2)}<br/>
          低: ${l?.toFixed(2)}  收: <span style="color:${color}">${c?.toFixed(2)}</span>
          <span style="color:${color}"> (${pct >= 0 ? '+' : ''}${pct?.toFixed(2)}%)</span>`
        // Show scheme match status for this date
        for (const s of result.value?.schemes ?? []) {
          const day = s.daily.find(d => d.date === date)
          if (day) {
            html += `<br/><span style="color:${day.is_matched ? '#409eff' : '#999'}">${s.scheme_name}: ${day.matched}/${s.total_rules}</span>`
          }
        }
        return html
      }
    },
    legend: {
      top: 4,
      data: [
        { name: 'K线', itemStyle: { color: '#f56c6c' } },
        ...schemeMarkPoints.map(s => ({ name: s.name, itemStyle: { color: s.color } })),
      ],
    },
    grid: [
      { left: 60, right: 20, top: 40, bottom: 80 },
      { left: 60, right: 20, height: 50, bottom: 25 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false }, axisLine: { onZero: false } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { fontSize: 10 } },
    ],
    yAxis: [
      { type: 'value', scale: true, gridIndex: 0, splitLine: { lineStyle: { color: '#f5f5f5' } } },
      { type: 'value', gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1] },
      { type: 'slider', xAxisIndex: [0, 1], bottom: 0, height: 18 },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: candleData,
        itemStyle: {
          color: '#f56c6c',
          color0: '#67c23a',
          borderColor: '#f56c6c',
          borderColor0: '#67c23a',
        },
        markPoint: {
          symbol: 'triangle',
          symbolSize: 10,
          data: schemeMarkPoints.flatMap(s =>
            s.markData.map(m => ({ ...m, itemStyle: { color: s.color } }))
          ),
        },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: { color: '#c8c8c8' },
      },
    ],
  }
})

// Rule matrix for active scheme
const matrixDates = computed(() =>
  activeScheme.value?.daily ?? []
)
const matrixRules = computed(() =>
  activeScheme.value?.rules ?? []
)

function cellStyle(dayResult: any, ruleId: number) {
  const rr = dayResult.rule_results?.[String(ruleId)]
  if (!rr) return {}
  return {
    background: rr.passed ? 'rgba(103,194,58,0.15)' : 'rgba(245,108,108,0.12)',
    color: rr.passed ? '#52c41a' : '#f56c6c',
  }
}

function cellText(dayResult: any, ruleId: number) {
  const rr = dayResult.rule_results?.[String(ruleId)]
  if (!rr) return '-'
  return rr.display || (rr.passed ? '✓' : '✗')
}
</script>

<template>
  <div>
    <!-- Query form -->
    <el-card style="margin-bottom: 16px">
      <el-form inline>
        <el-form-item label="股票代码">
          <el-input
            v-model="tsCode"
            placeholder="如 000049.SZ"
            style="width: 160px"
            @keyup.enter="runBacktest"
          />
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item label="选股方案">
          <el-select
            v-model="selectedSchemeIds"
            multiple
            placeholder="选择方案"
            style="width: 300px"
            collapse-tags
            collapse-tags-tooltip
          >
            <el-option
              v-for="s in schemeStore.schemes"
              :key="s.id"
              :label="s.name + (s.is_builtin ? ' [内置]' : '')"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="loading"
            @click="runBacktest"
          >
            {{ loading ? '回测中...' : '开始回测' }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <template v-if="result">
      <!-- Stock header -->
      <div style="margin-bottom: 12px; font-size: 16px; font-weight: 600">
        {{ result.ts_code }} {{ result.stock_name }}
      </div>

      <!-- Stats summary cards -->
      <el-row :gutter="12" style="margin-bottom: 16px">
        <el-col
          v-for="(s, idx) in result.schemes"
          :key="s.scheme_id"
          :span="Math.floor(24 / result.schemes.length)"
        >
          <el-card
            shadow="hover"
            :class="{ 'active-scheme-card': activeSchemeIdx === idx }"
            style="cursor: pointer"
            @click="activeSchemeIdx = idx"
          >
            <div style="font-weight: 600; margin-bottom: 6px">{{ s.scheme_name }}</div>
            <el-descriptions :column="3" size="small">
              <el-descriptions-item label="回测天数">{{ s.stats.total_days }}</el-descriptions-item>
              <el-descriptions-item label="命中天数">
                <span style="color: #409eff; font-weight: 600">{{ s.stats.matched_days }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="命中率">
                <span style="color: #409eff; font-weight: 600">{{ s.stats.match_rate }}%</span>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
      </el-row>

      <!-- K-line chart with match markers -->
      <el-card style="margin-bottom: 16px">
        <template #header>
          <span>K线走势 + 方案命中标记（圆点）</span>
        </template>
        <v-chart :option="chartOption" style="height: 420px" autoresize />
      </el-card>

      <!-- Rule-by-rule matrix for active scheme -->
      <el-card v-if="activeScheme">
        <template #header>
          <span>
            规则明细矩阵 —
            <el-tag size="small" type="primary">{{ activeScheme.scheme_name }}</el-tag>
            <span style="margin-left: 8px; font-size: 13px; color: #666">
              绿色=通过 红色=未通过，高亮行=命中日期
            </span>
          </span>
        </template>
        <div style="overflow-x: auto">
          <table style="border-collapse: collapse; font-size: 12px; min-width: 100%">
            <thead>
              <tr style="background: #fafafa; position: sticky; top: 0; z-index: 1">
                <th style="padding: 6px 10px; border: 1px solid #e0e0e0; white-space: nowrap; min-width: 90px">日期</th>
                <th style="padding: 6px 10px; border: 1px solid #e0e0e0; white-space: nowrap; min-width: 70px">命中</th>
                <th
                  v-for="rule in matrixRules"
                  :key="rule.id"
                  style="padding: 6px 8px; border: 1px solid #e0e0e0; white-space: nowrap; min-width: 100px; text-align: center"
                >
                  {{ rule.name }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="day in matrixDates"
                :key="day.date"
                :style="day.is_matched ? 'background: rgba(64,158,255,0.08); font-weight: 600' : ''"
              >
                <td style="padding: 4px 10px; border: 1px solid #e8e8e8; white-space: nowrap">
                  {{ day.date }}
                </td>
                <td style="padding: 4px 8px; border: 1px solid #e8e8e8; text-align: center">
                  <el-tag
                    :type="day.is_matched ? 'success' : 'info'"
                    size="small"
                  >
                    {{ day.matched }}/{{ activeScheme.total_rules }}
                  </el-tag>
                </td>
                <td
                  v-for="rule in matrixRules"
                  :key="rule.id"
                  :style="cellStyle(day, rule.id)"
                  style="padding: 4px 8px; border: 1px solid #e8e8e8; text-align: center; font-family: monospace"
                >
                  {{ cellText(day, rule.id) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.active-scheme-card {
  border: 2px solid #409eff;
}
</style>
