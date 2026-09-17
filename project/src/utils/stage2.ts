/**
 * 阶段二纯函数工具
 * @description 无 uni 依赖的纯函数：阶段过滤 / 进度计算 / 解锁判定 / 表单校验，
 *              对齐《阶段隔离规则与阶段二任务清单》§1.2 / §2 / §3。
 *              仅统计 status=1（启用）任务，default_completed=1 按已完成计入。
 */
import { PHASE1_STAGE_IDS, PHASE2_STAGE_IDS } from '../constants/stage2';
import { resolveTaskActionType, type TaskActionType } from '../constants/task';

/** 最小结构类型（与 types/task.ts 兼容） */
export interface StageTaskLike {
  taskId?: string;
  status?: number;
  defaultCompleted?: number;
  completionStatus?: string;
}

export interface StageGroupLike {
  taskId?: string;
  status?: number;
  secondLevelTasks?: StageTaskLike[];
}

export interface StageLike {
  stageId?: string;
  sortOrder?: number;
  locked?: boolean;
  firstLevelTasks?: StageGroupLike[];
}

/** 任务是否启用（status=1） */
export function isTaskEnabled(task: StageTaskLike): boolean {
  return task.status !== 0;
}

/** 任务是否已完成（completed 或 default_completed=1） */
export function isTaskCompleted(task: StageTaskLike): boolean {
  return task.completionStatus === 'completed' || task.defaultCompleted === 1;
}

/**
 * 「完成本组」toggle 判定
 * @description 存在未完成的启用任务 → true（全部完成）；
 *              全部启用任务已完成（含 default_completed=1）→ false（全部取消）；
 *              仅统计 status=1 任务，无启用任务返回 false（调用方应跳过空组）。
 */
export function shouldCompleteGroup(tasks: StageTaskLike[]): boolean {
  const enabled = tasks.filter(isTaskEnabled);
  if (enabled.length === 0) return false;
  return !enabled.every(isTaskCompleted);
}

/** 过滤阶段二 stage，并按 sortOrder 排序 */
export function filterStage2Stages(stages: StageLike[]): StageLike[] {
  return stages
    .filter((s) => (PHASE2_STAGE_IDS as readonly string[]).includes(s.stageId || ''))
    .sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0));
}

/** 过滤阶段一 stage */
export function filterStage1Stages(stages: StageLike[]): StageLike[] {
  return stages.filter((s) => (PHASE1_STAGE_IDS as readonly string[]).includes(s.stageId || ''));
}

/** 阶段进度：只统计启用任务，completed/default_completed 计入完成 */
export function computeStageProgress(stages: StageLike[]): { total: number; completed: number; percent: number } {
  let total = 0;
  let completed = 0;
  for (const stage of stages) {
    for (const group of stage.firstLevelTasks || []) {
      for (const task of group.secondLevelTasks || []) {
        if (!isTaskEnabled(task)) continue;
        total++;
        if (isTaskCompleted(task)) completed++;
      }
    }
  }
  return {
    total,
    completed,
    percent: total > 0 ? Math.round((completed / total) * 100) : 0,
  };
}

/**
 * 阶段一完成判定（§3.1/§3.2）
 * @description 阶段一启用任务全部完成（含 default_completed=1）才算完成；
 *              阶段一无启用任务视为异常配置，按未解锁处理。
 */
export function isStage1Complete(stages: StageLike[]): boolean {
  const stage1Stages = filterStage1Stages(stages);
  if (stage1Stages.length === 0) return false;
  return stage1Stages.every((stage) =>
    (stage.firstLevelTasks || []).every((group) =>
      (group.secondLevelTasks || []).every((task) => !isTaskEnabled(task) || isTaskCompleted(task)),
    ),
  );
}

/**
 * 阶段二解锁判定（以 GET /api/task/stages 返回的 locked 字段为准）
 * @description 无阶段二 stage 或全部 locked → 未解锁；任一未锁定即视为已解锁。
 */
export function isStage2Unlocked(stages: StageLike[]): boolean {
  const stage2Stages = filterStage2Stages(stages);
  if (stage2Stages.length === 0) return false;
  return stage2Stages.some((s) => s.locked !== true);
}

/** data_form 的 actionParam 取值（表单 key，与后端 DTO/schema 对齐） */
const DATA_FORM_KEYS = ['star', 'product-count', 'health-score'] as const;
/** data_upload 的 actionParam 取值（上传类型） */
const DATA_UPLOAD_TYPES = ['trade', 'traffic', 'product'] as const;

/**
 * 任务行为类型判定（阶段二 + 数据分析专区共用，#FE-29）
 * @description 唯一依据 = 后端 actionType 投影字段；缺失/空/未知值由 resolveTaskActionType 归一为 none
 *              （不白屏、按钮不失效）。禁止再按 taskId 字面量判断行为。
 */
export function hasTaskActionType(
  task: { actionType?: string | null } | null | undefined,
  type: TaskActionType,
): boolean {
  return resolveTaskActionType(task?.actionType) === type;
}

/**
 * 读取 data_form 的表单 key（actionParam 是不透明标识）
 * @returns 合法取值返回该值；缺失/非法返回 undefined（调用方据此不渲染表单，不臆测默认值）
 */
export function resolveDataFormKey(task: { actionParam?: string | null } | null | undefined): string | undefined {
  const raw = String(task?.actionParam ?? '').trim();
  return (DATA_FORM_KEYS as readonly string[]).includes(raw) ? raw : undefined;
}

/**
 * 读取 data_upload 的上传类型（actionParam 是不透明标识）
 * @returns 合法取值返回该值；缺失/非法返回 undefined（绝不兜底到 trade，避免把文件写进错误的表）
 */
export function resolveDataUploadType(
  task: { actionParam?: string | null } | null | undefined,
): 'trade' | 'traffic' | 'product' | undefined {
  const raw = String(task?.actionParam ?? '').trim();
  return (DATA_UPLOAD_TYPES as readonly string[]).includes(raw) ? (raw as 'trade' | 'traffic' | 'product') : undefined;
}

/** 本地时区今天的日期字符串（YYYY-MM-DD），用于表单 dataDate 默认值 */
export function todayDateString(): string {
  const d = new Date();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${month}-${day}`;
}

/** 表单校验通用：数值范围 + 整数约束，返回 { field: message } */
function validateNumberField(
  errors: Record<string, string>,
  key: string,
  value: unknown,
  field: { label: string; required?: boolean; min?: number; max?: number; integer?: boolean },
): void {
  const raw = value as string | number | undefined;
  if (raw === undefined || raw === null || raw === '') {
    if (field.required) errors[key] = `请填写${field.label}`;
    return;
  }
  const num = typeof raw === 'number' ? raw : Number(raw);
  if (Number.isNaN(num)) {
    errors[key] = `${field.label}需为数字`;
    return;
  }
  if (field.integer && !Number.isInteger(num)) {
    errors[key] = `${field.label}需为整数`;
    return;
  }
  if (field.min !== undefined && num < field.min) errors[key] = `${field.label}不能小于 ${field.min}`;
  if (field.max !== undefined && num > field.max) errors[key] = `${field.label}不能大于 ${field.max}`;
}

/** 校验店铺星级表单（T2.5.1） */
export function validateShopStar(values: Record<string, unknown>): Record<string, string> {
  const errors: Record<string, string> = {};
  validateNumberField(errors, 'shopStar', values.shopStar, { label: '店铺星级', required: true, min: 1, max: 5 });
  for (const key of ['serviceScore', 'logisticsScore', 'afterSaleScore', 'productScore']) {
    validateNumberField(errors, key, values[key], { label: '因子得分', min: 0, max: 10 });
  }
  return errors;
}

/** 校验商品数量表单（T2.5.5） */
export function validateProductCount(values: Record<string, unknown>): Record<string, string> {
  const errors: Record<string, string> = {};
  validateNumberField(errors, 'totalCount', values.totalCount, { label: '全部商品数量', required: true, min: 0, integer: true });
  for (const key of ['onSaleCount', 'offSaleCount', 'auditCount']) {
    validateNumberField(errors, key, values[key], { label: '商品数量', min: 0, integer: true });
  }
  return errors;
}

/** 校验商品信息健康分表单（T2.5.6）
 *  #F-29：5 个字段全部非必填（留空合法，提交时由 emptyAsZero 以 0 发送）；填了仍按范围校验 */
export function validateHealthScore(values: Record<string, unknown>): Record<string, string> {
  const errors: Record<string, string> = {};
  validateNumberField(errors, 'avgScore', values.avgScore, { label: '店铺平均信息分', min: 0, max: 100 });
  for (const key of ['scoreGte90Count', 'score78_90Count', 'score60_77Count', 'scoreLt60Count']) {
    validateNumberField(errors, key, values[key], { label: '分段商品数量', min: 0, integer: true });
  }
  return errors;
}
