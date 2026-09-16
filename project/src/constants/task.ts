/**
 * 任务相关常量
 */

/** 任务状态枚举 */
export enum TaskStatus {
  /** 待处理 */
  PENDING = 'pending',
  /** 进行中 */
  IN_PROGRESS = 'in_progress',
  /** 已完成 */
  COMPLETED = 'completed',
  /** 已过期 */
  EXPIRED = 'expired',
}

/** 任务状态标签映射 */
export const TaskStatusLabel: Record<TaskStatus, string> = {
  [TaskStatus.PENDING]: '待处理',
  [TaskStatus.IN_PROGRESS]: '进行中',
  [TaskStatus.COMPLETED]: '已完成',
  [TaskStatus.EXPIRED]: '已过期',
};

/** 任务类型标签 */
export const TaskTypeLabel: Record<string, string> = {
  mandatory: '必做',
  suggested: '建议',
  guide: '引导',
};

/** 阶段按钮文案 */
export const StageButtonText: Record<string, string> = {
  onboarding: '我已了解',
  setup: '我已准备',
  application: '我已申请',
  review: '我已通过',
  opening: '我已开店',
};

/** 阶段标题 */
export const StageTitle: Record<string, string> = {
  onboarding: '模式选择与认知',
  setup: '资质材料准备',
  application: '申请入驻',
  review: '审核跟进',
  opening: '开店设置',
};
