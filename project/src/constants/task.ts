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

/**
 * 任务行为类型（唯一真源 = 后端 `second_level_task.actionType`；`none` 置首）
 * @description 后端投影 `GET /api/task/stages` 每个任务带出 `actionType`/`actionParam`；
 *              前端**只按该值分发行为**，禁止再按 `taskId` 字面量判断（方案：dev-docs/任务单/action-type-design.md）。
 */
export const TASK_ACTION_TYPES = [
  'none',
  'advisor_qr',
  'category_picker',
  'fee_picker',
  'trademark_lookup',
  'title_optimize',
  'image_optimize',
  'advisor_entry',
  'data_form',
  'data_upload',
] as const;

/** 任务行为类型（由上表派生的联合类型，供分发处做穷尽判断） */
export type TaskActionType = (typeof TASK_ACTION_TYPES)[number];

/**
 * 归一化后端 actionType：缺失/空串/未知值 ⇒ 一律按 `none`（不白屏、按钮不失效）
 * @param raw 后端返回值（可能为 null/undefined/未知字符串）
 * @description 未知值只留一条 `console.warn` 级埋点便于排查，**不新增用户可见文案**。
 */
export const resolveTaskActionType = (raw?: string | null): TaskActionType => {
  const value = String(raw ?? '').trim();
  if ((TASK_ACTION_TYPES as readonly string[]).includes(value)) return value as TaskActionType;
  if (value) console.warn('[task] 未知 actionType，已按 none 处理：' + value);
  return 'none';
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
