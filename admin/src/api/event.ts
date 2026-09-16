import request from './request'

export interface EventStatsData {
  date_range: { start_date: string; end_date: string }
  summary: {
    pv: number
    uv: number
    task_complete_count: number
    task_complete_rate: number
  }
  trend: { date: string; pv: number; uv: number }[]
  page_distribution: { page_name: string; pv: number; uv: number }[]
  task_stats: { task_key: string; complete_count: number; expand_count: number }[]
}

export interface EventStatsQuery {
  start_date: string
  end_date: string
  group_by?: 'day' | 'week'
}

// 埋点统计（管理端；PV/UV/任务完成率/趋势/页面分布/任务维度）
export const getEventStats = (params: EventStatsQuery) => {
  return request.get<EventStatsData>('/event/stats', { params })
}
