import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { TaskStatus } from '@/constants/task';
import type { StageInfo, FirstLevelTask, SecondLevelTask, TaskProgress } from '@/types/task';
import request from '@/api/request';
import { filterStage1Stages, isStage1Complete, computeStageProgress, isTaskEnabled, isTaskCompleted } from '@/utils/stage2';
import { PHASE2_STAGE_IDS, DATA_CENTER_STAGE_ID } from '@/constants/stage2';

export const useTaskStore = defineStore('task', () => {
  /** 最近一次保存/恢复的已完成任务 ID（用于检测「完成 → 未完成」并补发 pending） */
  let lastCompletedTaskIds: string[] = [];

  /** 阶段列表（从后端获取） */
  const stages = ref<StageInfo[]>([]);
  /** 加载状态 */
  const loading = ref(false);
  /** 后端解锁标记（GET /api/task/progress 的 stage2_unlocked，运营一键解锁场景） */
  const backendUnlocked = ref(false);
  /** 数据专区解锁标记（GET /api/task/progress 的 data_center_unlocked，后端为事实源；saveProgress 按此过滤 shopdata 任务） */
  const dataCenterUnlocked = ref(false);
  /** 进度恢复失败标记（后端失败且本地缓存为空时置 true，供页面展示轻量提示；恢复成功清除） */
  const progressRestoreFailed = ref(false);
  /** 本地已完成但后端未确认的任务 ID（落库失败/服务不可用时的乐观完成；非空时页面展示「未同步」提示） */
  const unsyncedCompletedTaskIds = ref<string[]>([]);
  /** 本地已取消完成但后端未确认的任务 ID（pending 落库失败；后端仍为完成态，非空时页面如实提示「取消未同步」） */
  const unsyncedPendingTaskIds = ref<string[]>([]);

  /** 阶段一（入驻准备）stage 列表（onboarding/application/review/opening） */
  const stage1Stages = computed<StageInfo[]>(() => filterStage1Stages(stages.value) as StageInfo[]);

  /** 阶段一完成判定（启用任务全部 completed，供阶段二入口解锁） */
  const stage1Complete = computed<boolean>(() => isStage1Complete(stages.value));

  /** 阶段二解锁判定：任务完成 或 后端解锁标记（两者满足其一即可进入） */
  const stage2Unlocked = computed<boolean>(() => stage1Complete.value || backendUnlocked.value);

  /** 从后端获取阶段和任务数据 */
  async function fetchStages() {
    loading.value = true;
    try {
      const res = await request.get<StageInfo[]>('/api/task/stages');
      stages.value = res.data || [];
    } catch (error) {
      console.error('获取任务数据失败:', error);
      stages.value = [];
    } finally {
      loading.value = false;
    }
  }

  /** 所有二级任务（展平） */
  const allSecondLevelTasks = computed<SecondLevelTask[]>(() => {
    const tasks: SecondLevelTask[] = [];
    for (const stage of stages.value) {
      for (const flt of stage.firstLevelTasks || []) {
        tasks.push(...(flt.secondLevelTasks || []));
      }
    }
    return tasks;
  });

  /** 进度（仅统计阶段一启用任务，阶段二不计入） */
  const progress = computed<TaskProgress>(() => computeStageProgress(stage1Stages.value));

  /** 切换二级任务完成状态 */
  function toggleTask(taskId: string) {
    for (const stage of stages.value) {
      for (const flt of stage.firstLevelTasks || []) {
        const task = flt.secondLevelTasks?.find(t => t.taskId === taskId || t.id === taskId);
        if (task) {
          task.completionStatus = task.completionStatus === TaskStatus.COMPLETED
            ? TaskStatus.PENDING
            : TaskStatus.COMPLETED;
          saveProgress();
          return;
        }
      }
    }
  }

  /** 完成整个阶段（所有一级任务） */
  function completeStage(stageId: string) {
    const stage = stages.value.find(s => s.id === stageId || s.stageId === stageId);
    if (stage) {
      for (const flt of stage.firstLevelTasks || []) {
        for (const task of flt.secondLevelTasks || []) {
          task.completionStatus = TaskStatus.COMPLETED;
        }
      }
      saveProgress();
      
      // 检查是否所有阶段都已完成
      const allCompleted = stages.value.every(s => 
        (s.firstLevelTasks || []).every(flt => 
          (flt.secondLevelTasks || []).every(t => 
            t.completionStatus === TaskStatus.COMPLETED || t.defaultCompleted === 1
          )
        )
      );
      
      // 只有所有阶段都完成时才发送飞书通知
      if (allCompleted) {
        request.post('/api/feishu/notify/stage-complete', {
          stage_name: '阶段一：入驻准备',
          next_stage_name: undefined,
        }).catch(() => {});
      }
    }
  }

  /**
   * 完成/取消单个一级任务组（T1.x 下全部启用二级任务）
   * @description 存在未完成→全部完成；全部已完成→全部取消；取消时不触发飞书通知。
   */
  function completeGroup(group: FirstLevelTask) {
    const tasks = (group.secondLevelTasks || []).filter(isTaskEnabled);
    const allCompletedBefore = tasks.length > 0 && tasks.every(isTaskCompleted);
    const target = allCompletedBefore ? TaskStatus.PENDING : TaskStatus.COMPLETED;
    for (const task of tasks) {
      task.completionStatus = target;
    }
    saveProgress();

    // 仅「置为完成」且阶段一全部完成后触发飞书通知；取消完成不通知
    if (!allCompletedBefore && stage1Complete.value) {
      request.post('/api/feishu/notify/stage-complete', {
        stage_name: '阶段一：入驻准备',
        next_stage_name: undefined,
      }).catch(() => {});
    }
  }

  /** 切换支线任务勾选 */
  function toggleBranchTask(taskId: string) {
    for (const stage of stages.value) {
      for (const flt of stage.firstLevelTasks || []) {
        if (flt.branches) {
          for (const branch of flt.branches) {
            const task = branch.tasks.find(t => t.id === taskId);
            if (task) {
              task.checked = !task.checked;
              saveProgress();
              return;
            }
          }
        }
      }
    }
  }

  /**
   * 当前按解锁态可写（可 POST completed/pending）的任务 ID 集合
   * @description 阶段一始终可写；阶段二任务（brand/listing/optimize/activity）仅 stage2Unlocked 后可写；
   *              shopdata（数据专区）仅 dataCenterUnlocked 后可写。
   *              与 collectCompletedTaskIds / pending 补发共用，杜绝对未解锁锁定任务补发 POST（403 toast 隐患）。
   */
  function getWritableTaskIds(): Set<string> {
    const ids = new Set<string>();
    for (const stage of stages.value) {
      const stageId = stage.stageId || '';
      const isPhase2 = (PHASE2_STAGE_IDS as readonly string[]).includes(stageId);
      const isDataCenter = stageId === DATA_CENTER_STAGE_ID;
      if (isPhase2 && !stage2Unlocked.value) continue;
      if (isDataCenter && !dataCenterUnlocked.value) continue;
      for (const flt of stage.firstLevelTasks || []) {
        for (const task of flt.secondLevelTasks || []) {
          ids.add(task.taskId);
        }
      }
    }
    return ids;
  }

  /** 收集当前所有已完成二级任务 ID（按解锁态过滤：锁定任务的完成态不收集、不补发） */
  function collectCompletedTaskIds(): string[] {
    const writable = getWritableTaskIds();
    const ids: string[] = [];
    for (const stage of stages.value) {
      for (const flt of stage.firstLevelTasks || []) {
        for (const task of flt.secondLevelTasks || []) {
          if (task.completionStatus === TaskStatus.COMPLETED && writable.has(task.taskId)) {
            ids.push(task.taskId);
          }
        }
      }
    }
    return ids;
  }

  /** 读取本地进度快照（与 saveProgress / restoreProgress 同 key；缓存缺失或损坏时按空快照处理） */
  function readCachedCompletedTaskIds(): Set<string> {
    try {
      const raw = uni.getStorageSync('task_progress_cache');
      if (!raw) return new Set();
      const parsed = JSON.parse(raw);
      return new Set(Array.isArray(parsed) ? (parsed as string[]) : []);
    } catch (e) {
      console.warn('[进度缓存] 解析失败，按空快照处理', e);
      return new Set();
    }
  }

  /** 标记「本地已完成但未落库」的任务（去重），供页面提示进度未同步 */
  function markUnsyncedCompleted(taskId: string) {
    if (!unsyncedCompletedTaskIds.value.includes(taskId)) {
      unsyncedCompletedTaskIds.value = unsyncedCompletedTaskIds.value.concat(taskId);
    }
  }

  /** 后端确认落库后清除未同步标记 */
  function clearUnsyncedCompleted(taskId: string) {
    unsyncedCompletedTaskIds.value = unsyncedCompletedTaskIds.value.filter((id) => id !== taskId);
  }

  /** 标记「本地已取消完成但未落库」的任务（去重），供页面如实提示取消未同步 */
  function markUnsyncedPending(taskId: string) {
    if (!unsyncedPendingTaskIds.value.includes(taskId)) {
      unsyncedPendingTaskIds.value = unsyncedPendingTaskIds.value.concat(taskId);
    }
  }

  /** 后端确认取消落库后清除未同步标记 */
  function clearUnsyncedPending(taskId: string) {
    unsyncedPendingTaskIds.value = unsyncedPendingTaskIds.value.filter((id) => id !== taskId);
  }

  /** 重试未落库的取消项（页面点击重试时调用，即用户主动表达取消意图；成功后清除未同步标记） */
  function retryUnsyncedPending() {
    for (const taskId of unsyncedPendingTaskIds.value.slice()) {
      request.post('/api/task/progress', { taskId, status: 'pending' })
        .then(() => clearUnsyncedPending(taskId))
        .catch((e) => console.warn('[进度补发失败] 标记待办', taskId, e));
    }
  }

  /** 补发未落库的完成项（恢复成功后调用）：仅补发当前解锁态可写任务，成功后清除未同步标记 */
  function syncUnsyncedCompleted(taskIds: string[]) {
    const writable = getWritableTaskIds();
    for (const taskId of taskIds) {
      if (!writable.has(taskId)) continue;
      request.post('/api/task/progress', { taskId, status: 'completed' })
        .then(() => clearUnsyncedCompleted(taskId))
        .catch((e) => console.warn('[进度补发失败] 标记完成', taskId, e));
    }
  }

  /** 保存进度到后端：已完成发 completed；「完成 → 未完成」补发 pending；localStorage 同步 */
  function saveProgress() {
    const completedTaskIds = collectCompletedTaskIds();
    const currentSet = new Set(completedTaskIds);
    // 对比上次状态：本次已不在完成集合的任务补发 pending（仅限当前解锁态可写的任务，避免对锁定任务 POST）
    const writable = getWritableTaskIds();
    const pendingTaskIds = lastCompletedTaskIds.filter((id) => writable.has(id) && !currentSet.has(id));
    // 同步更新本地快照（避免快速连续 toggle 时漏差）
    lastCompletedTaskIds = completedTaskIds.slice();
    
    // 同时保存到 localStorage 作为缓存
    uni.setStorageSync('task_progress_cache', JSON.stringify(completedTaskIds));
    
    // 异步保存到后端（不阻塞UI）
    import('@/api/request')
      .then(({ default: request }) => {
        for (const taskId of completedTaskIds) {
          request.post('/api/task/progress', { taskId, status: 'completed' })
            .then(() => clearUnsyncedCompleted(taskId))
            .catch((e) => {
              console.warn('[进度同步失败] 标记完成', taskId, e);
              markUnsyncedCompleted(taskId);
            });
        }
        for (const taskId of pendingTaskIds) {
          request.post('/api/task/progress', { taskId, status: 'pending' })
            .then(() => clearUnsyncedPending(taskId))
            .catch((e) => {
              console.warn('[进度同步失败] 标记待办', taskId, e);
              markUnsyncedPending(taskId);
            });
        }
      })
      .catch((e) => console.warn('[进度同步] 模块加载失败', e));
  }

  /** 恢复进度 */
  async function restoreProgress() {
    try {
      // 先从后端获取进度
      const res = await request.get<{ completedTasks: string[]; stage2_unlocked?: boolean; data_center_unlocked?: boolean }>('/api/task/progress');
      const completedTasks = res.data?.completedTasks || [];
      backendUnlocked.value = !!res.data?.stage2_unlocked;
      dataCenterUnlocked.value = !!res.data?.data_center_unlocked;
      
      // 更新本地状态：以后端 completedTasks 为基准校正（防静默漂移 #F1-PROGRESS）
      // 后端确认的 → completed；后端无记录但本地快照已完成（落库失败的乐观完成）→ 保留完成态并补发；
      // 仅本地快照同样无记录时才回退 pending（清内存假完成），避免落库失败时静默丢弃用户完成状态
      const completedSet = new Set(completedTasks);
      const localSnapshot = readCachedCompletedTaskIds();
      const unsynced: string[] = [];
      for (const stage of stages.value) {
        for (const flt of stage.firstLevelTasks || []) {
          for (const task of flt.secondLevelTasks || []) {
            if (completedSet.has(task.taskId)) {
              task.completionStatus = TaskStatus.COMPLETED;
            } else if (localSnapshot.has(task.taskId)) {
              // 后端未落库但本地已完成 → 保留用户完成态，记为未同步待补发
              task.completionStatus = TaskStatus.COMPLETED;
              unsynced.push(task.taskId);
            } else if (task.completionStatus === TaskStatus.COMPLETED) {
              // 清本地假完成（defaultCompleted=1 任务由 isTaskCompleted 语义兜底，不受影响）
              task.completionStatus = TaskStatus.PENDING;
            }
          }
        }
      }
      
      // 同时缓存到 localStorage：写入「后端结果 ∪ 未落库的本地完成」，不得覆盖用户的乐观完成
      const mergedCompletedTaskIds = Array.from(new Set([...completedTasks, ...unsynced]));
      uni.setStorageSync('task_progress_cache', JSON.stringify(mergedCompletedTaskIds));
      // 同步本地快照，避免后续保存把已同步的完成态误判为取消
      lastCompletedTaskIds = mergedCompletedTaskIds.slice();
      // 未落库项：暴露结构化未同步状态（页面提示）并补发，后端追上后由 clearUnsyncedCompleted 清除
      unsyncedCompletedTaskIds.value = unsynced;
      syncUnsyncedCompleted(unsynced);
      // 取消方向：后端仍为完成态 → 保留「取消未同步」提示（不改后端权威结果）；后端已无记录 → 取消已落库，清除标记
      unsyncedPendingTaskIds.value = unsyncedPendingTaskIds.value.filter((id) => completedSet.has(id));
      // 后端恢复成功：清除失败标记
      progressRestoreFailed.value = false;
    } catch (e) {
      console.error('从后端恢复进度失败，尝试从缓存恢复', e);
      
      // 如果后端失败，从 localStorage 缓存恢复
      try {
        const raw = uni.getStorageSync('task_progress_cache');
        // 缓存也为空（真正无法恢复）→ 置失败标记，页面展示轻量提示
        if (!raw) {
          progressRestoreFailed.value = true;
          return;
        }
        const completedTasks = JSON.parse(raw);
        lastCompletedTaskIds = completedTasks.slice();
        
        for (const stage of stages.value) {
          for (const flt of stage.firstLevelTasks || []) {
            for (const task of flt.secondLevelTasks || []) {
              if (completedTasks.includes(task.taskId)) {
                task.completionStatus = TaskStatus.COMPLETED;
              }
            }
          }
        }
        // 缓存恢复成功：保持未失败
        progressRestoreFailed.value = false;
      } catch (cacheErr) {
        console.error('从缓存恢复进度也失败', cacheErr);
      }
    }
  }

  return { 
    stages, 
    loading,
    stage1Stages,
    stage1Complete,
    stage2Unlocked,
    dataCenterUnlocked,
    progressRestoreFailed,
    unsyncedCompletedTaskIds,
    unsyncedPendingTaskIds,
    allSecondLevelTasks,
    progress, 
    fetchStages,
    toggleTask, 
    completeStage, 
    completeGroup,
    toggleBranchTask, 
    restoreProgress,
    retryUnsyncedPending 
  };
});


