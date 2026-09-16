<template>
  <div class="data-stats-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>使用数据统计</span>
          <div class="header-right">
            <el-radio-group v-model="quickRange" @change="applyQuickRange">
              <el-radio-button label="7">近 7 天</el-radio-button>
              <el-radio-button label="30">近 30 天</el-radio-button>
              <el-radio-button label="90">近 90 天</el-radio-button>
            </el-radio-group>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              :clearable="false"
              style="width: 260px"
            />
            <el-button type="primary" :loading="loading" @click="fetchStats">
              <el-icon><Search /></el-icon>
              查询
            </el-button>
          </div>
        </div>
      </template>

      <!-- 关键数字卡片（工作台布局：顶端数字卡） -->
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-label">PV（访问量）</div>
            <div class="stat-value font-number">{{ stats.summary?.pv ?? 0 }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-label">UV（访客数）</div>
            <div class="stat-value font-number" style="color: #18C989">{{ stats.summary?.uv ?? 0 }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-label">任务完成次数</div>
            <div class="stat-value font-number" style="color: #FFA914">{{ stats.summary?.task_complete_count ?? 0 }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-card">
            <div class="stat-label">任务完成率</div>
            <div class="stat-value font-number" style="color: #52C41A">{{ (stats.summary?.task_complete_rate ?? 0).toFixed(2) }}%</div>
          </div>
        </el-col>
      </el-row>

      <!-- 趋势 + 页面分布 -->
      <el-row :gutter="16" class="chart-row">
        <el-col :span="14">
          <el-card shadow="never">
            <template #header><span>访问趋势（按日）</span></template>
            <el-table :data="stats.trend || []" size="small" max-height="360" stripe>
              <el-table-column prop="date" label="日期" min-width="110" />
              <el-table-column prop="pv" label="PV" width="100" />
              <el-table-column prop="uv" label="UV" width="100" />
              <el-table-column label="PV 走势" min-width="180">
                <template #default="{ row }">
                  <div class="bar-track">
                    <div class="bar-fill" :style="{ width: barPercent(row.pv) + '%' }"></div>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card shadow="never">
            <template #header><span>页面分布</span></template>
            <el-table :data="stats.page_distribution || []" size="small" max-height="360" stripe>
              <el-table-column prop="page_name" label="页面" min-width="110" show-overflow-tooltip />
              <el-table-column prop="pv" label="PV" width="90" />
              <el-table-column label="占比" min-width="120">
                <template #default="{ row }">
                  <el-progress
                    :percentage="distPercent(row.pv)"
                    :stroke-width="8"
                    :show-text="false"
                    color="#2C8FF5"
                  />
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { getEventStats } from '@/api/event'
import type { EventStatsData } from '@/api/event'

const loading = ref(false)
const quickRange = ref('7')
const dateRange = ref<[string, string] | null>(null)
const stats = ref<EventStatsData>({
  date_range: { start_date: '', end_date: '' },
  summary: { pv: 0, uv: 0, task_complete_count: 0, task_complete_rate: 0 },
  trend: [],
  page_distribution: [],
  task_stats: [],
})

const formatDate = (d: Date) => {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const applyQuickRange = () => {
  const days = Number(quickRange.value)
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - (days - 1))
  dateRange.value = [formatDate(start), formatDate(end)]
}

const fetchStats = async () => {
  if (!dateRange.value) return
  loading.value = true
  try {
    const res = await getEventStats({
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
      group_by: 'day',
    })
    stats.value = res.data
  } catch (error) {
    console.error('获取统计数据失败', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  applyQuickRange()
  fetchStats()
})

// 趋势柱状占比（相对最大 pv）
const maxTrendPv = () => {
  const rows = stats.value.trend || []
  let max = 0
  for (const r of rows) max = Math.max(max, Number(r.pv) || 0)
  return max
}

const barPercent = (pv: number | string) => {
  const max = maxTrendPv()
  const v = Number(pv) || 0
  return max > 0 ? Math.max(2, Math.round((v / max) * 100)) : 0
}

// 页面分布占比（相对总 pv）
const distPercent = (pv: number | string) => {
  const rows = stats.value.page_distribution || []
  let total = 0
  for (const r of rows) total += Number(r.pv) || 0
  const v = Number(pv) || 0
  return total > 0 ? Math.round((v / total) * 100) : 0
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.header-right {
  display: flex;
  gap: 16px;
  align-items: center;
}

.stat-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(42, 54, 77, 0.06);
  border: 1px solid var(--el-border-color-light);
  margin-bottom: 16px;
}

.stat-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: var(--el-color-primary);
  line-height: 1.2;
}

.chart-row {
  margin-top: 16px;
}

.bar-track {
  height: 12px;
  background-color: #f0f2f5;
  border-radius: 6px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 6px;
  background: linear-gradient(90deg, #2C8FF5, #79C0FF);
}
</style>
