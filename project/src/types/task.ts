import { TaskStatus } from '@/constants/task';
import type { TaskActionType } from '@/constants/task';
export type { TaskStatus };
export type { TaskActionType };

/** 任务类型 */
export type TaskType = 'mandatory' | 'suggested' | 'guide' | 'form' | 'upload' | 'jump';

/** 完成方式 */
export type CompletionType = 'system_check' | 'manual_submit' | 'click_read' | 'form_submit' | 'file_upload';

/** 任务阶段 */
export type TaskStage =
  | 'onboarding'
  | 'setup'
  | 'application'
  | 'review'
  | 'opening'
  | 'brand'
  | 'listing'
  | 'optimize'
  | 'activity'
  | 'shopdata'
  | 'shop_setup';

/** 支线任务项 */
export interface BranchTaskItem {
  id: string;
  name: string;
  hint: string;
  checked: boolean;
}

/** 支线任务组 */
export interface BranchTaskGroup {
  id: string;
  title: string;
  tasks: BranchTaskItem[];
}

/** 二级任务信息 (原 TaskInfo) */
export interface SecondLevelTask {
  id: string;
  taskId: string;
  firstLevelTaskId: string;
  stageId: string;
  title: string;
  description: string;
  detail?: string;
  type: TaskType;
  completionType: CompletionType;
  actionText?: string;
  actionUrl?: string;
  /**
   * 任务行为类型（后端 actionType 投影；取值见 constants/task.ts 的 TASK_ACTION_TYPES）
   * @description 前端行为分发的唯一依据；缺失/未知值按 `none` 处理（见 resolveTaskActionType）
   */
  actionType?: string;
  /** 行为参数（当前仅 `data_form` / `data_upload` 使用，如 star / trade / traffic / product） */
  actionParam?: string | null;
  tag?: string;
  defaultCompleted: number;
  status: number;
  sortOrder: number;
  /** 前端使用：任务完成状态 */
  completionStatus?: TaskStatus;
}

/** 一级任务信息 */
export interface FirstLevelTask {
  id: string;
  taskId: string;
  stageId: string;
  title: string;
  description: string;
  buttonText?: string;
  status: number;
  sortOrder: number;
  secondLevelTasks: SecondLevelTask[];
  /** 前端使用：支线任务 */
  branches?: BranchTaskGroup[];
}

/** 阶段信息 */
export interface StageInfo {
  id: string;
  stageId: string;
  stageNum: number;
  title: string;
  description?: string;
  status: number;
  sortOrder: number;
  /** 所属大阶段（1=阶段一 / 2=阶段二），后端 GET /api/task/stages 返回 */
  phase?: number;
  /** 阶段二未解锁时为 true（阶段一未完成，后端不返回任务数据） */
  locked?: boolean;
  /** 锁定提示文案 */
  unlockHint?: string;
  firstLevelTasks: FirstLevelTask[];
}

/** 任务进度 */
export interface TaskProgress {
  total: number;
  completed: number;
  percent: number;
}

/** 类目信息 */
export interface CategoryInfo {
  name: string;
  children: string[];
}

/** 资费三级类目 */
export interface FeeSubCategory {
  name: string;
  rate: string;
  deposit1: string;
  deposit2: string;
  deposit3: string;
  deposit4: string;
}

/** 资费信息 */
export interface FeeInfo {
  name: string;
  items: FeeSubCategory[];
}
