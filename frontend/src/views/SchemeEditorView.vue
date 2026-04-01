<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSchemeStore } from '@/stores/scheme'
import { schemesApi, templatesApi, type Rule, type RuleTemplate } from '@/api'
import { ElMessage } from 'element-plus'
import draggable from 'vuedraggable'

const route = useRoute()
const router = useRouter()
const schemeStore = useSchemeStore()
const schemeId = Number(route.params.id)

const scheme = ref<any>(null)
const rules = ref<Rule[]>([])
const templates = ref<RuleTemplate[]>([])
const templatesByCategory = computed(() => {
  const map: Record<string, RuleTemplate[]> = {}
  for (const t of templates.value) {
    if (!map[t.category]) map[t.category] = [] as RuleTemplate[]
    map[t.category]!.push(t)
  }
  return map
})

const CATEGORIES: Record<string, string> = {
  trend: '趋势/价格',
  volume: '量能',
  valuation: '估值',
  flow: '资金流向',
  technical: '技术指标',
  filter: '过滤条件',
  historical: '历史统计'
}

const editingScheme = ref({ name: '', description: '', match_mode: 'all', min_match: null as number | null })
const showTemplates = ref(false)
const editRuleDialog = ref(false)
const editingRule = ref<Partial<Rule>>({})

onMounted(async () => {
  const [schemeRes, tmplRes] = await Promise.all([
    schemesApi.get(schemeId),
    templatesApi.list()
  ])
  scheme.value = schemeRes.data
  rules.value = [...(schemeRes.data.rules || [])].sort((a, b) => a.sort_order - b.sort_order)
  templates.value = tmplRes.data
  editingScheme.value = {
    name: scheme.value.name,
    description: scheme.value.description || '',
    match_mode: scheme.value.match_mode,
    min_match: scheme.value.min_match
  }
})

async function saveScheme() {
  try {
    await schemeStore.updateScheme(schemeId, editingScheme.value)
    ElMessage.success('方案已保存')
  } catch {
    ElMessage.error('保存失败')
  }
}

async function addFromTemplate(tmpl: RuleTemplate) {
  try {
    const ruleData: Partial<Rule> = {
      name: tmpl.name,
      category: tmpl.category,
      data_source: tmpl.data_source,
      metric: tmpl.metric,
      operator: tmpl.operator,
      value: tmpl.default_value || {},
      lookback_days: tmpl.lookback_days,
      params: tmpl.params,
      sort_order: rules.value.length,
      template_id: tmpl.id,
      enabled: true
    }
    const res = await schemesApi.addRule(schemeId, ruleData)
    rules.value.push(res.data)
    ElMessage.success(`已添加规则: ${tmpl.name}`)
  } catch {
    ElMessage.error('添加失败')
  }
}

async function deleteRule(rule: Rule) {
  try {
    await schemesApi.deleteRule(schemeId, rule.id)
    rules.value = rules.value.filter(r => r.id !== rule.id)
  } catch {
    ElMessage.error('删除失败')
  }
}

async function toggleRule(rule: Rule) {
  try {
    const updated = await schemesApi.updateRule(schemeId, rule.id, { ...rule, enabled: !rule.enabled })
    const idx = rules.value.findIndex(r => r.id === rule.id)
    if (idx >= 0) rules.value[idx] = updated.data
  } catch {
    ElMessage.error('更新失败')
  }
}

async function onDragEnd() {
  const ruleIds = rules.value.map(r => r.id)
  try {
    await schemesApi.reorderRules(schemeId, ruleIds)
  } catch {
    ElMessage.warning('排序保存失败')
  }
}

function openEditRule(rule: Rule) {
  editingRule.value = { ...rule }
  editRuleDialog.value = true
}

async function saveRule() {
  if (!editingRule.value.id) return
  try {
    const updated = await schemesApi.updateRule(schemeId, editingRule.value.id, editingRule.value as Rule)
    const idx = rules.value.findIndex(r => r.id === editingRule.value.id)
    if (idx >= 0) rules.value[idx] = updated.data
    editRuleDialog.value = false
    ElMessage.success('规则已更新')
  } catch {
    ElMessage.error('更新失败')
  }
}

function operatorLabel(op: string) {
  const map: Record<string, string> = {
    gt: '>', gte: '≥', lt: '<', lte: '≤', eq: '=', between: '区间'
  }
  return map[op] || op
}

function valueLabel(rule: Rule) {
  if (!rule.value) return '-'
  const v = rule.value
  if (rule.operator === 'between') return `[${v.min}, ${v.max}]`
  if ('v' in v) return String(v.v)
  return JSON.stringify(v)
}

const categoryColor: Record<string, string> = {
  trend: '', volume: 'success', valuation: 'warning', flow: 'danger',
  technical: 'info', filter: '', historical: 'success'
}
</script>

<template>
  <div>
    <el-row :gutter="16">
      <!-- Left: Scheme settings + rules -->
      <el-col :span="showTemplates ? 16 : 24">
        <!-- Scheme settings -->
        <el-card style="margin-bottom: 16px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>方案设置</span>
              <div>
                <el-button @click="showTemplates = !showTemplates" :icon="'Grid'">
                  {{ showTemplates ? '隐藏模板库' : '添加规则' }}
                </el-button>
                <el-button type="primary" @click="saveScheme">保存方案</el-button>
                <el-button @click="router.push('/schemes')">返回列表</el-button>
              </div>
            </div>
          </template>

          <el-form :model="editingScheme" inline label-width="100px">
            <el-form-item label="方案名称">
              <el-input v-model="editingScheme.name" style="width: 200px" />
            </el-form-item>
            <el-form-item label="匹配模式">
              <el-select v-model="editingScheme.match_mode" style="width: 120px">
                <el-option value="all" label="全部匹配" />
                <el-option value="partial" label="部分匹配" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="editingScheme.match_mode === 'partial'" label="最少匹配">
              <el-input-number v-model="editingScheme.min_match" :min="1" :max="rules.length" style="width: 120px" />
            </el-form-item>
          </el-form>
          <el-form-item label="描述" label-width="100px">
            <el-input v-model="editingScheme.description" type="textarea" :rows="2" style="width: 100%" />
          </el-form-item>
        </el-card>

        <!-- Rules list (draggable) -->
        <el-card>
          <template #header>
            <span>规则列表 ({{ rules.length }} 条，可拖拽排序)</span>
          </template>

          <draggable
            v-model="rules"
            item-key="id"
            handle=".drag-handle"
            @end="onDragEnd"
          >
            <template #item="{ element: rule }">
              <div
                class="rule-item"
                :class="{ 'rule-disabled': !rule.enabled }"
              >
                <el-icon class="drag-handle" style="cursor: grab; margin-right: 8px; color: #999"><Menu /></el-icon>
                <el-tag :type="categoryColor[rule.category] || ''" size="small" style="margin-right: 8px; min-width: 70px; text-align: center">
                  {{ CATEGORIES[rule.category] || rule.category }}
                </el-tag>
                <span style="flex: 1; font-weight: 500">{{ rule.name }}</span>
                <span style="color: #666; margin-right: 16px; font-size: 13px">
                  {{ rule.metric }} {{ operatorLabel(rule.operator) }} {{ valueLabel(rule) }}
                </span>
                <el-switch
                  :model-value="rule.enabled"
                  @change="toggleRule(rule)"
                  size="small"
                  style="margin-right: 8px"
                />
                <el-button size="small" @click="openEditRule(rule)">编辑</el-button>
                <el-button size="small" type="danger" @click="deleteRule(rule)">删除</el-button>
              </div>
            </template>
          </draggable>

          <div v-if="rules.length === 0" style="text-align: center; color: #999; padding: 40px">
            暂无规则，点击「添加规则」从模板库选择
          </div>
        </el-card>
      </el-col>

      <!-- Right: Template library -->
      <el-col v-if="showTemplates" :span="8">
        <el-card>
          <template #header>模板规则库</template>
          <el-collapse>
            <el-collapse-item
              v-for="(cat, catKey) in CATEGORIES"
              :key="catKey"
              :title="`${cat} (${(templatesByCategory[catKey] || []).length})`"
              :name="catKey"
            >
              <div
                v-for="tmpl in templatesByCategory[catKey] || []"
                :key="tmpl.id"
                class="template-item"
                @click="addFromTemplate(tmpl)"
              >
                <div style="font-weight: 500; font-size: 13px">{{ tmpl.name }}</div>
                <div v-if="tmpl.description" style="color: #999; font-size: 12px">{{ tmpl.description }}</div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-card>
      </el-col>
    </el-row>

    <!-- Edit rule dialog -->
    <el-dialog v-model="editRuleDialog" title="编辑规则" width="500px">
      <el-form v-if="editingRule" label-width="100px">
        <el-form-item label="规则名称">
          <el-input v-model="editingRule.name" />
        </el-form-item>
        <el-form-item label="操作符">
          <el-select v-model="editingRule.operator">
            <el-option value="gt" label="> 大于" />
            <el-option value="gte" label="≥ 大于等于" />
            <el-option value="lt" label="< 小于" />
            <el-option value="lte" label="≤ 小于等于" />
            <el-option value="eq" label="= 等于" />
            <el-option value="between" label="区间 [min, max]" />
          </el-select>
        </el-form-item>
        <el-form-item label="参数值 (JSON)">
          <el-input
            :model-value="JSON.stringify(editingRule.value)"
            @update:model-value="(v: string) => { try { editingRule.value = JSON.parse(v) } catch {} }"
            placeholder='{"v": 3} 或 {"min": 3, "max": 5}'
          />
        </el-form-item>
        <el-form-item label="回溯天数">
          <el-input-number v-model="editingRule.lookback_days" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editRuleDialog = false">取消</el-button>
        <el-button type="primary" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.rule-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid #eee;
  border-radius: 6px;
  margin-bottom: 8px;
  background: #fff;
}
.rule-disabled {
  opacity: 0.5;
}
.template-item {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.2s;
}
.template-item:hover {
  background: #f0f7ff;
}
</style>
