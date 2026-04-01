<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSchemeStore } from '@/stores/scheme'
import { schemesApi } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Scheme } from '@/api'

const router = useRouter()
const schemeStore = useSchemeStore()

onMounted(() => schemeStore.fetchSchemes())

async function editScheme(id: number) {
  router.push(`/schemes/${id}/edit`)
}

async function copyScheme(scheme: Scheme) {
  try {
    const newScheme = await schemeStore.copyScheme(scheme.id)
    ElMessage.success(`已复制为: ${newScheme.name}`)
  } catch {
    ElMessage.error('复制失败')
  }
}

async function deleteScheme(scheme: Scheme) {
  try {
    await ElMessageBox.confirm(`确认删除方案「${scheme.name}」？`, '删除确认', { type: 'warning' })
    await schemeStore.deleteScheme(scheme.id)
    ElMessage.success('已删除')
  } catch {
    // cancelled
  }
}

async function createNew() {
  try {
    const scheme = await schemeStore.createScheme({
      name: '新建方案',
      description: '',
      match_mode: 'all'
    })
    router.push(`/schemes/${scheme.id}/edit`)
  } catch {
    ElMessage.error('创建失败')
  }
}

async function saveSchedule(scheme: Scheme) {
  try {
    await schemesApi.update(scheme.id, {
      name: scheme.name,
      description: scheme.description,
      match_mode: scheme.match_mode,
      min_match: scheme.min_match,
      schedule_enabled: scheme.schedule_enabled,
      schedule_time: scheme.schedule_time,
    })
    ElMessage.success('定时设置已保存')
  } catch {
    ElMessage.error('保存失败')
  }
}

function onSwitchChange(scheme: Scheme) {
  if (!scheme.schedule_enabled) {
    saveSchedule(scheme)
  } else if (scheme.schedule_time) {
    saveSchedule(scheme)
  }
}

function getHour(scheme: Scheme): string {
  return scheme.schedule_time?.split(':')[0] ?? ''
}
function getMinute(scheme: Scheme): string {
  return scheme.schedule_time?.split(':')[1] ?? ''
}
function setHour(scheme: Scheme, h: string) {
  const m = getMinute(scheme) || '00'
  scheme.schedule_time = h ? `${h}:${m}` : null
  if (scheme.schedule_enabled && scheme.schedule_time) saveSchedule(scheme)
}
function setMinute(scheme: Scheme, m: string) {
  const h = getHour(scheme)
  if (!h) return
  scheme.schedule_time = `${h}:${m}`
  if (scheme.schedule_enabled) saveSchedule(scheme)
}

const HOURS = Array.from({length: 24}, (_, i) => String(i).padStart(2, '0'))
const MINUTES = ['00', '05', '10', '15', '20', '25', '30', '35', '40', '45', '50', '55']
</script>

<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>选股方案管理</span>
          <el-button type="primary" :icon="'Plus'" @click="createNew">新建方案</el-button>
        </div>
      </template>

      <el-table :data="schemeStore.schemes" stripe>
        <el-table-column prop="name" label="方案名称" min-width="160">
          <template #default="{ row }">
            {{ row.name }}
            <el-tag v-if="row.is_builtin" type="info" size="small" style="margin-left: 6px">内置</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="匹配模式" width="130">
          <template #default="{ row }">
            <el-tag :type="row.match_mode === 'all' ? 'primary' : 'warning'" size="small">
              {{ row.match_mode === 'all' ? '全部匹配' : `部分匹配 ≥${row.min_match}` }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rule_count" label="规则数" width="80" />
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">{{ row.updated_at?.slice(0, 16).replace('T', ' ') }}</template>
        </el-table-column>
        <el-table-column label="自动运行" width="90" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.schedule_enabled"
              size="small"
              @change="onSwitchChange(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="触发时间" width="150">
          <template #default="{ row }">
            <div style="display:flex; align-items:center; gap:4px">
              <el-select
                :model-value="getHour(row)"
                size="small"
                style="width:62px"
                placeholder="时"
                :disabled="!row.schedule_enabled"
                @update:model-value="(v: string) => setHour(row, v)"
              >
                <el-option v-for="h in HOURS" :key="h" :label="h" :value="h" />
              </el-select>
              <span style="color:#999">:</span>
              <el-select
                :model-value="getMinute(row)"
                size="small"
                style="width:62px"
                placeholder="分"
                :disabled="!row.schedule_enabled || !getHour(row)"
                @update:model-value="(v: string) => setMinute(row, v)"
              >
                <el-option v-for="m in MINUTES" :key="m" :label="m" :value="m" />
              </el-select>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editScheme(row.id)">编辑</el-button>
            <el-button size="small" @click="copyScheme(row)">复制</el-button>
            <el-button
              size="small"
              type="danger"
              :disabled="row.is_builtin"
              @click="deleteScheme(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
