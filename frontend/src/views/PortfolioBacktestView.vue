<script setup lang="ts">
import { ref, computed, onUnmounted, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent, GridComponent, MarkLineComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import { useSchemeStore } from '@/stores/scheme'
import { portfolioBacktestApi, schemesApi } from '@/api'
import type { PortfolioBacktestResult, Rule } from '@/api'
import { ElMessage } from 'element-plus'

use([CanvasRenderer, LineChart, TooltipComponent, GridComponent, MarkLineComponent])

const schemeStore = useSchemeStore()
schemeStore.fetchSchemes()

const form = ref({ schemeId: null as number | null, dateRange: [] as string[], holdDays: 1 })

// Scheme rules for checkbox filter
const schemeRules = ref<Rule[]>([])
const checkedRuleIds = ref<number[]>([])

watch(() => form.value.schemeId, async (id) => {
  schemeRules.value = []
  checkedRuleIds.value = []
  if (!id) return
  try {
    const r = await schemesApi.get(id)
    const rules = (r.data.rules ?? []).filter(ru => ru.enabled)
    schemeRules.value = rules
    checkedRuleIds.value = rules.map(ru => ru.id)
  } catch { /* ignore */ }
})

function toggleAllRules() {
  checkedRuleIds.value = checkedRuleIds.value.length === schemeRules.value.length
    ? []
    : schemeRules.value.map(r => r.id)
}

// Progress state
const taskId = ref<string | null>(null)
const running = ref(false)
const progress = ref({ pct: 0, message: '', current: 0, total: 0 })

// Result
const result = ref<PortfolioBacktestResult | null>(null)
const expandedBatches = ref<Set<string>>(new Set())

let pollTimer: ReturnType<typeof setInterval> | null = null

function stopPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

onUnmounted(stopPoll)

async function run() {
  if (!form.value.schemeId || form.value.dateRange.length < 2) {
    ElMessage.warning('请选择方案和时间段')
    return
  }
  result.value = null
  expandedBatches.value.clear()
  running.value = true
  progress.value = { pct: 0, message: '提交中...', current: 0, total: 0 }

  try {
    const allChecked = checkedRuleIds.value.length === schemeRules.value.length
    const r = await portfolioBacktestApi.start({
      scheme_id: form.value.schemeId!,
      start_date: form.value.dateRange[0]!,
      end_date: form.value.dateRange[1]!,
      hold_days: form.value.holdDays,
      enabled_rule_ids: allChecked ? undefined : checkedRuleIds.value,
    })
    taskId.value = r.data.task_id
    // Start polling
    pollTimer = setInterval(poll, 1500)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
    running.value = false
  }
}

async function poll() {
  if (!taskId.value) return
  try {
    const r = await portfolioBacktestApi.progress(taskId.value)
    const p = r.data
    progress.value = { pct: p.pct, message: p.message, current: p.current, total: p.total }

    if (p.status === 'done') {
      stopPoll()
      running.value = false
      result.value = p.result!
    } else if (p.status === 'error') {
      stopPoll()
      running.value = false
      ElMessage.error(p.error || '回测出错')
    }
  } catch {
    // ignore transient network errors during polling
  }
}

function retColor(v: number | null | undefined) {
  if (v == null) return ''
  return v > 0 ? 'color:#f56c6c;font-weight:600' : v < 0 ? 'color:#67c23a;font-weight:600' : 'color:#909399'
}

function retTag(v: number | null | undefined) {
  if (v == null) return '-'
  return (v > 0 ? '+' : '') + v.toFixed(2) + '%'
}

function toggleBatch(d: string) {
  expandedBatches.value.has(d) ? expandedBatches.value.delete(d) : expandedBatches.value.add(d)
}

const chartOption = computed(() => {
  if (!result.value) return {}
  const curve = result.value.equity_curve
  const dates = curve.map(p => p.date === 'start' ? '起始' : p.date)
  const values = curve.map(p => p.value)
  const up = (result.value.summary.cumulative_return ?? 0) >= 0
  const lc = up ? '#f56c6c' : '#67c23a'
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => {
        const p = params[0]
        const s = p.value >= 0 ? '+' : ''
        return `${p.name}<br/>累计收益 <b style="color:${lc}">${s}${Number(p.value).toFixed(2)}%</b>`
      },
    },
    grid: { left: 64, right: 16, top: 16, bottom: 40 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11, rotate: dates.length > 25 ? 30 : 0 } },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: (v: number) => v.toFixed(1) + '%' },
      splitLine: { lineStyle: { type: 'dashed', color: '#eee' } },
    },
    series: [{
      type: 'line', data: values, smooth: true,
      lineStyle: { color: lc, width: 2 },
      itemStyle: { color: lc },
      areaStyle: { color: lc, opacity: 0.07 },
      markLine: {
        silent: true, symbol: 'none',
        lineStyle: { color: '#bbb', type: 'dashed' },
        data: [{ yAxis: 0 }], label: { show: false },
      },
    }],
  }
})
</script>

<template>
  <div style="max-width:1400px; margin:0 auto">
    <!-- 查询表单 -->
    <el-card style="margin-bottom:16px">
      <template #header><span style="font-weight:600">方案组合回测</span></template>
      <el-form :model="form" inline label-width="80px">
        <el-form-item label="选股方案">
          <el-select v-model="form.schemeId" placeholder="选择方案" style="width:220px">
            <el-option
              v-for="s in schemeStore.schemes" :key="s.id"
              :label="s.name + (s.is_builtin ? ' [内置]' : '')" :value="s.id"
            />
          </el-select>
        </el-form-item>
        <!-- Rule checkboxes — shown after a scheme is selected -->
        <div v-if="schemeRules.length > 0" style="width:100%; margin:0 0 12px 80px; display:flex; align-items:flex-start; gap:10px; flex-wrap:wrap">
          <span style="font-size:13px; color:#606266; white-space:nowrap; padding-top:2px; flex-shrink:0">筛选规则：</span>
          <el-checkbox-group v-model="checkedRuleIds" size="small" style="display:flex; flex-wrap:wrap; gap:6px">
            <el-checkbox
              v-for="r in schemeRules" :key="r.id" :value="r.id"
              style="margin-right:0; height:auto"
            >{{ r.name }}</el-checkbox>
          </el-checkbox-group>
          <el-button link size="small" style="flex-shrink:0; padding-top:2px" @click="toggleAllRules">
            {{ checkedRuleIds.length === schemeRules.length ? '全不选' : '全选' }}
          </el-button>
        </div>

        <el-form-item label="回测时段">
          <el-date-picker
            v-model="form.dateRange" type="daterange"
            format="YYYY-MM-DD" value-format="YYYY-MM-DD"
            range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期"
            style="width:260px"
          />
        </el-form-item>
        <el-form-item label="持有天数">
          <el-radio-group v-model="form.holdDays">
            <el-radio :value="1">持有1日</el-radio>
            <el-radio :value="2">持有2日</el-radio>
            <el-radio :value="3">持有3日</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="running" @click="run">
            {{ running ? '回测中...' : '开始回测' }}
          </el-button>
        </el-form-item>
      </el-form>
      <div style="font-size:12px; color:#999; margin-top:4px">
        以筛选日收盘价等权买入全部完全匹配股票，N个交易日后以收盘价卖出。
        交易成本：买入0.025% + 卖出0.127%（含印花税0.1%），合计0.152%/笔。
      </div>
    </el-card>

    <!-- 进度条 -->
    <el-card v-if="running" style="margin-bottom:16px">
      <div style="padding:8px 0">
        <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:13px; color:#606266">
          <span>{{ progress.message }}</span>
          <span v-if="progress.total > 0">{{ progress.current }} / {{ progress.total }} 日</span>
        </div>
        <el-progress
          :percentage="progress.pct"
          :stroke-width="10"
          :format="(p: number) => p + '%'"
          status="striped"
          striped
          striped-flow
          :duration="10"
        />
      </div>
    </el-card>

    <template v-if="result">
      <!-- 汇总指标 -->
      <el-card style="margin-bottom:16px">
        <template #header>
          <span style="font-weight:600">
            回测结果 — {{ result.scheme_name }}
            &nbsp;<el-tag size="small" type="info">持有{{ result.hold_days }}日</el-tag>
            &nbsp;<el-tag size="small" type="success">
              {{ result.start_date }} 至 {{ result.end_date }}，共{{ result.summary.total_batches }}批
            </el-tag>
          </span>
        </template>
        <el-row :gutter="20">
          <el-col :span="4">
            <div style="text-align:center">
              <div style="font-size:12px; color:#888; margin-bottom:4px">区间总收益</div>
              <div style="font-size:28px; font-weight:700" :style="retColor(result.summary.cumulative_return)">
                {{ retTag(result.summary.cumulative_return) }}
              </div>
            </div>
          </el-col>
          <el-col :span="4">
            <div style="text-align:center">
              <div style="font-size:12px; color:#888; margin-bottom:4px">年化收益</div>
              <div style="font-size:28px; font-weight:700" :style="retColor(result.summary.annualized_return)">
                {{ retTag(result.summary.annualized_return) }}
              </div>
            </div>
          </el-col>
          <el-col :span="4">
            <div style="text-align:center">
              <div style="font-size:12px; color:#888; margin-bottom:4px">日胜率</div>
              <div style="font-size:28px; font-weight:700; color:#409eff">
                {{ result.summary.win_rate.toFixed(1) }}%
              </div>
            </div>
          </el-col>
          <el-col :span="4">
            <div style="text-align:center">
              <div style="font-size:12px; color:#888; margin-bottom:4px">均均收益/批</div>
              <div style="font-size:28px; font-weight:700" :style="retColor(result.summary.avg_batch_return)">
                {{ retTag(result.summary.avg_batch_return) }}
              </div>
            </div>
          </el-col>
          <el-col :span="4">
            <div style="text-align:center">
              <div style="font-size:12px; color:#888; margin-bottom:4px">最大回撤</div>
              <div style="font-size:28px; font-weight:700; color:#67c23a">
                {{ result.summary.max_drawdown.toFixed(2) }}%
              </div>
            </div>
          </el-col>
          <el-col :span="4">
            <div style="text-align:center">
              <div style="font-size:12px; color:#888; margin-bottom:4px">均均持仓数/批</div>
              <div style="font-size:28px; font-weight:700; color:#606266">
                {{ result.summary.avg_stocks_per_batch }}
              </div>
              <div style="font-size:11px; color:#bbb">共{{ result.summary.total_trades }}笔</div>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 净值曲线 -->
      <el-card v-if="result.equity_curve.length > 1" style="margin-bottom:16px">
        <template #header><span style="font-weight:600">累计收益曲线</span></template>
        <VChart :option="chartOption" style="height:280px" autoresize />
      </el-card>

      <!-- 逐批明细 -->
      <el-card>
        <template #header><span style="font-weight:600">逐批交易明细</span></template>
        <el-table :data="result.batches" size="small" stripe>
          <el-table-column label="买入日" prop="buy_date" width="100" />
          <el-table-column label="卖出日" width="100">
            <template #default="{ row }">{{ row.sell_date ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="股数" width="60" align="center">
            <template #default="{ row }">
              {{ row.valid_count }}<span v-if="row.valid_count < row.stock_count" style="color:#bbb;font-size:11px">/{{ row.stock_count }}</span>
            </template>
          </el-table-column>
          <el-table-column label="批次净收益" width="110" align="right">
            <template #default="{ row }">
              <span :style="retColor(row.avg_net_return)">{{ retTag(row.avg_net_return) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="展开" width="70" align="center">
            <template #default="{ row }">
              <el-button link size="small" @click="toggleBatch(row.buy_date)">
                {{ expandedBatches.has(row.buy_date) ? '收起' : '详情' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <template v-for="batch in result.batches" :key="batch.buy_date">
          <el-collapse-transition>
            <div v-if="expandedBatches.has(batch.buy_date)"
              style="margin:4px 0 10px; padding:8px 12px; background:#fafafa; border:1px solid #eee; border-radius:4px">
              <el-table :data="batch.stocks" size="small">
                <el-table-column label="代码" prop="ts_code" width="100" />
                <el-table-column label="名称" width="90">
                  <template #default="{ row }">{{ row.stock_name ?? '-' }}</template>
                </el-table-column>
                <el-table-column label="买入价" align="right" width="80">
                  <template #default="{ row }">{{ row.buy_price?.toFixed(2) ?? '-' }}</template>
                </el-table-column>
                <el-table-column label="卖出价" align="right" width="80">
                  <template #default="{ row }">{{ row.sell_price?.toFixed(2) ?? '-' }}</template>
                </el-table-column>
                <el-table-column label="原始收益" align="right" width="100">
                  <template #default="{ row }">
                    <span :style="retColor(row.raw_return)">{{ retTag(row.raw_return) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="净收益（扣成本）" align="right">
                  <template #default="{ row }">
                    <span :style="retColor(row.net_return)">{{ retTag(row.net_return) }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-collapse-transition>
        </template>
      </el-card>
    </template>
  </div>
</template>
