import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { TaskStatus } from '@/constants/task';
import type { StageInfo, SecondLevelTask, TaskProgress } from '@/types/task';
import request from '@/api/request';
import { PHASE2_STAGE_IDS, DATA_CENTER_STAGE_ID } from '@/constants/stage2';
import {
  filterStage2Stages,
  filterStage1Stages,
  computeStageProgress,
  isStage1Complete,
  isStage2Unlocked,
  isTaskEnabled,
  shouldCompleteGroup,
} from '@/utils/stage2';

/** localStorage 缓存 key（与阶段一 task_progress_cache 隔离，见 R2 §4.4） */
const STAGE2_PROGRESS_CACHE_KEY = 'stage2_progress_cache';

/**
 * 阶段二（开店搭建）状态管理
 * @description 结构与阶段一 store/modules/task.ts 完全对齐：
 *              fetchStages / restoreProgress / progress / toggleTask / completeStage；
 *              数据同源 GET /api/task/stages，进度同 POST /api/task/progress。
 */
export const useStage2Store = defineStore('stage2', () => {
  /** 后端返回的全部阶段（含阶段一，用于解锁判定） */
  const stages = ref<StageInfo[]>([]);
  /** 加载状态 */
  const loading = ref(false);
  /** 阶段二解锁状态（GET /api/task/progress 的 stage2_unlocked，后端为事实源） */
  const unlocked = ref(false);
  /** 本次会话中「完成 → 未完成」待同步 pending 的任务 id（完成时移出） */
  const pendingSyncTaskIds = new Set<string>();

  /** 阶段二 stage 列表（brand/listing/optimize/activity，不含 shopdata） */
  const stage2Stages = computed<StageInfo[]>(() => filterStage2Stages(stages.value));
  /** 数据分析专区 stage 列表（stageId === shopdata，原 T2.5 店铺数据上传，独立记录） */
  const dataCenterStages = computed<StageInfo[]>(() =>
    stages.value.filter((s) => s.stageId === DATA_CENTER_STAGE_ID),
  );
  /** 阶段一 stage 列表（onboarding/application/review/opening） */
  const stage1Stages = computed<StageInfo[]>(() => filterStage1Stages(stages.value));
  /** 阶段一完成判定（派生口径，供阶段一入口接线使用） */
  const stage1Complete = computed<boolean>(() => isStage1Complete(stages.value));
  /** 阶段二进度（仅统计启用任务，27 个；shopdata 不计入） */
  const progress = computed<TaskProgress>(() => computeStageProgress(stage2Stages.value));
  /** 数据分析专区上传进度（T2.5.1~T2.5.6，独立统计） */
  const dataCenterProgress = computed<TaskProgress>(() => computeStageProgress(dataCenterStages.value));
  /** 数据分析专区解锁状态（GET /api/task/progress 的 data_center_unlocked，后端为事实源；接口未就绪默认 false） */
  const dataCenterUnlocked = ref(false);
  /** 阶段二 + 数据分析专区 stage 列表（统一的任务查找/保存/恢复范围） */
  const scopedStages = computed<StageInfo[]>(() =>
    stages.value.filter(
      (s) =>
        (PHASE2_STAGE_IDS as readonly string[]).includes(s.stageId || '') ||
        s.stageId === DATA_CENTER_STAGE_ID,
    ),
  );
  /** 阶段二 + 数据分析专区任务 id 集合（进度缓存隔离用，避免混入阶段一） */
  const stage2TaskIds = computed<Set<string>>(() => {
    const set = new Set<string>();
    for (const stage of scopedStages.value) {
      for (const flt of stage.firstLevelTasks || []) {
        for (const task of flt.secondLevelTasks || []) {
          set.add(task.taskId);
        }
      }
    }
    return set;
  });

  /** 从后端获取阶段数据（GET /api/task/stages） */
  async function fetchStages() {
    loading.value = true;
    try {
      const res = await request.get<StageInfo[]>('/api/task/stages');
      stages.value = res.data || [];
      unlocked.value = isStage2Unlocked(stages.value);
    } catch (error) {
      console.error('获取阶段二任务数据失败:', error);
      stages.value = [];
    } finally {
      loading.value = false;
    }
  }

  /** 在阶段二 + 数据分析专区任务中查找并更新任务，返回是否找到 */
  function updateTask(taskId: string, updater: (task: SecondLevelTask) => void): boolean {
    for (const stage of scopedStages.value) {
      for (const flt of stage.firstLevelTasks || []) {
        const task = flt.secondLevelTasks?.find((t) => t.taskId === taskId || t.id === taskId);
        if (task) {
          updater(task);
          return true;
        }
      }
    }
    return false;
  }

  /** 切换二级任务完成状态 */
  function toggleTask(taskId: string) {
    updateTask(taskId, (task) => {
      const next = task.completionStatus === TaskStatus.COMPLETED ? TaskStatus.PENDING : TaskStatus.COMPLETED;
      if (next === TaskStatus.PENDING) {
        pendingSyncTaskIds.add(task.taskId);
      } else {
        pendingSyncTaskIds.delete(task.taskId);
      }
      task.completionStatus = next;
    });
    saveProgress();
  }

  /** 标记任务完成（表单/上传/搜索成功回调，不切换回待办） */
  function markTaskCompleted(taskId: string) {
    updateTask(taskId, (task) => {
      pendingSyncTaskIds.delete(task.taskId);
      task.completionStatus = TaskStatus.COMPLETED;
    });
    saveProgress();
  }

  /**
   * 「完成本组」toggle（T2.x 下全部启用二级任务）：
   * 存在未完成 → 全部完成；全部完成 → 再次点击全部取消；保持进度同步。
   */
  function completeStage(stageId: string) {
    const stage = stage2Stages.value.find((s) => s.id === stageId || s.stageId === stageId);
    if (!stage) return;
    const tasks = (stage.firstLevelTasks || []).flatMap((flt) => flt.secondLevelTasks || []).filter(isTaskEnabled);
    if (tasks.length === 0) return;
    const markCompleted = shouldCompleteGroup(tasks);
    for (const task of tasks) {
      if (markCompleted) {
        pendingSyncTaskIds.delete(task.taskId);
        task.completionStatus = TaskStatus.COMPLETED;
      } else {
        pendingSyncTaskIds.add(task.taskId);
        task.completionStatus = TaskStatus.PENDING;
      }
    }
    saveProgress();
  }

  /**
   * 保存进度：已完成任务 POST status:'completed'；
   * 「完成 → 未完成」任务补发 status:'pending'（同阶段一口径）；
   * localStorage 仅缓存已完成 id（stage2_progress_cache 隔离）。
   * 统计范围为阶段二 + 数据分析专区任务（shopdata 独立记录，与阶段二分离）。
   */
  function saveProgress() {
    const completedTaskIds: string[] = [];
    for (const stage of scopedStages.value) {
      for (const flt of stage.firstLevelTasks || []) {
        for (const task of flt.secondLevelTasks || []) {
          if (task.completionStatus === TaskStatus.COMPLETED) {
            completedTaskIds.push(task.taskId);
          }
        }
      }
    }

    uni.setStorageSync(STAGE2_PROGRESS_CACHE_KEY, JSON.stringify(completedTaskIds));

    // 同步进度并消费后端返回的解锁状态（data_center_unlocked 为后端事实源）
    // 商品发布（listing）全部完成后，此处即时刷新数据专区解锁态，无需刷新页面
    const syncTask = (taskId: string, status: 'completed' | 'pending') => {
      request
        .post<{ success: boolean; stage2_unlocked: boolean; data_center_unlocked?: boolean }>(
          '/api/task/progress',
          { taskId, status },
        )
        .then((res) => {
          if (res.data && typeof res.data.data_center_unlocked === 'boolean') {
            dataCenterUnlocked.value = res.data.data_center_unlocked;
          }
        })
        .catch((e) => console.warn('阶段二进度同步失败', e));
    };

    for (const taskId of completedTaskIds) {
      syncTask(taskId, 'completed');
    }
    for (const taskId of pendingSyncTaskIds) {
      syncTask(taskId, 'pending');
    }
  }

  /** 将已完成任务集合标记到阶段二 + 数据分析专区任务上 */
  function applyCompleted(completedTasks: string[]) {
    const set = new Set(completedTasks);
    for (const stage of scopedStages.value) {
      for (const flt of stage.firstLevelTasks || []) {
        for (const task of flt.secondLevelTasks || []) {
          if (set.has(task.taskId)) {
            task.completionStatus = TaskStatus.COMPLETED;
          }
        }
      }
    }
  }

  /** 恢复进度：后端优先（completedTasks + stage2_unlocked + data_center_unlocked），localStorage 兜底 */
  async function restoreProgress() {
    try {
      const res = await request.get<{
        completedTasks: string[];
        stage2_unlocked: boolean;
        data_center_unlocked?: boolean;
      }>('/api/task/progress');
      const completedTasks = res.data?.completedTasks || [];
      unlocked.value = !!res.data?.stage2_unlocked;
      // 数据分析专区解锁判定（后端依据 T2.2 listing 全部完成计算；接口未就绪时保持默认 false）
      dataCenterUnlocked.value = !!res.data?.data_center_unlocked;
      applyCompleted(completedTasks);
      // BUG-012：缓存仅写入阶段二任务 id，避免阶段一 T1.x 混入
      uni.setStorageSync(
        STAGE2_PROGRESS_CACHE_KEY,
        JSON.stringify(completedTasks.filter((id) => stage2TaskIds.value.has(id))),
      );
    } catch (e) {
      console.error('从后端恢复阶段二进度失败，尝试从缓存恢复', e);
      try {
        const raw = uni.getStorageSync(STAGE2_PROGRESS_CACHE_KEY);
        if (!raw) return;
        applyCompleted(JSON.parse(raw));
      } catch (cacheErr) {
        console.error('从缓存恢复阶段二进度也失败', cacheErr);
      }
    }
  }

  return {
    stages,
    loading,
    unlocked,
    dataCenterUnlocked,
    stage2Stages,
    dataCenterStages,
    dataCenterProgress,
    stage1Stages,
    stage1Complete,
    progress,
    fetchStages,
    restoreProgress,
    toggleTask,
    markTaskCompleted,
    completeStage,
    saveProgress,
  };
});
