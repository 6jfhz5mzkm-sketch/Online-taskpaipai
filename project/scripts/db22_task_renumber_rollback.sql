-- ============================================================
-- #DB-22 阶段一任务序号调整 —— 回滚脚本(rollback)
-- 作用: 把 db22_task_renumber_apply.sql 的变更**完全还原**为调整前状态
-- 库名: **不写死**,执行方显式指定(dev = merchant_task)
-- 幂等: 以主键 id 锚定 + 会话守卫 @db22_applied;**=7 执行回滚**;≠7(=6 表示处于调整前原状,新旧 ID 集合有 6 个重名)
--       则全部 SKIP;其它值需人工介入
-- 两阶段改名: 新 ID -> TMPRB22_<新ID> -> 旧 ID
-- 逆向映射: id=51 T1.3.5->T1.5.1(组 T1.3->T1.5, stage application->opening, sort 5->1);id=46 T1.3.6->T1.3.5(6->5);
--           id=47 T1.3.7->T1.3.6(7->6);id=48 T1.3.8->T1.3.7(8->7);id=52 T1.5.1->T1.5.2(1->2);
--           id=53 T1.5.2->T1.5.3(2->3);id=54 T1.5.3->T1.5.4(3->4)
-- ============================================================

-- ① 回滚前备份 SELECT
SELECT id, taskId, firstLevelTaskId, stageId, title, sortOrder FROM second_level_task WHERE id IN (46,47,48,51,52,53,54) ORDER BY id;
SELECT id, merchantId, taskId, status, completedAt FROM merchant_task_progress WHERE taskId IN ('T1.3.5','T1.3.6','T1.3.7','T1.3.8','T1.5.1','T1.5.2','T1.5.3') ORDER BY taskId, id;

-- ② 守卫(7=已应用可回滚;6=未应用则 SKIP)
SET @db22_applied := (SELECT COUNT(*) FROM second_level_task WHERE id IN (46,47,48,51,52,53,54) AND taskId IN ('T1.3.5','T1.3.6','T1.3.7','T1.3.8','T1.5.1','T1.5.2','T1.5.3'));
SELECT @db22_applied AS db22_applied_should_be_7;

-- ③ 阶段1: 新 ID -> 回滚临时前缀
UPDATE second_level_task SET taskId = CONCAT('TMPRB22_', taskId) WHERE @db22_applied = 7 AND id IN (46,47,48,51,52,53,54) AND taskId IN ('T1.3.5','T1.3.6','T1.3.7','T1.3.8','T1.5.1','T1.5.2','T1.5.3');
UPDATE merchant_task_progress SET taskId = CONCAT('TMPRB22_', taskId) WHERE @db22_applied = 7 AND taskId IN ('T1.3.5','T1.3.6','T1.3.7','T1.3.8','T1.5.1','T1.5.2','T1.5.3');

-- ④ 阶段2: 临时名 -> 旧 ID(恢复组/stage/sortOrder)
UPDATE second_level_task SET taskId='T1.5.1', firstLevelTaskId='T1.5', stageId='opening', sortOrder=1 WHERE id=51 AND taskId='TMPRB22_T1.3.5';
UPDATE merchant_task_progress SET taskId='T1.5.1' WHERE taskId='TMPRB22_T1.3.5';
UPDATE second_level_task SET taskId='T1.3.5', sortOrder=5 WHERE id=46 AND taskId='TMPRB22_T1.3.6';
UPDATE merchant_task_progress SET taskId='T1.3.5' WHERE taskId='TMPRB22_T1.3.6';
UPDATE second_level_task SET taskId='T1.3.6', sortOrder=6 WHERE id=47 AND taskId='TMPRB22_T1.3.7';
UPDATE merchant_task_progress SET taskId='T1.3.6' WHERE taskId='TMPRB22_T1.3.7';
UPDATE second_level_task SET taskId='T1.3.7', sortOrder=7 WHERE id=48 AND taskId='TMPRB22_T1.3.8';
UPDATE merchant_task_progress SET taskId='T1.3.7' WHERE taskId='TMPRB22_T1.3.8';
UPDATE second_level_task SET taskId='T1.5.2', sortOrder=2 WHERE id=52 AND taskId='TMPRB22_T1.5.1';
UPDATE merchant_task_progress SET taskId='T1.5.2' WHERE taskId='TMPRB22_T1.5.1';
UPDATE second_level_task SET taskId='T1.5.3', sortOrder=3 WHERE id=53 AND taskId='TMPRB22_T1.5.2';
UPDATE merchant_task_progress SET taskId='T1.5.3' WHERE taskId='TMPRB22_T1.5.2';
UPDATE second_level_task SET taskId='T1.5.4', sortOrder=4 WHERE id=54 AND taskId='TMPRB22_T1.5.3';
UPDATE merchant_task_progress SET taskId='T1.5.4' WHERE taskId='TMPRB22_T1.5.3';

-- ⑤ 回滚后校验 SELECT(期望: T1.3 = 1..7、T1.5 = 1..4;残留 0)
SELECT id, taskId, firstLevelTaskId, stageId, title, sortOrder FROM second_level_task WHERE firstLevelTaskId IN ('T1.3','T1.5') ORDER BY firstLevelTaskId, sortOrder;
SELECT COUNT(*) AS tmprb_residue_should_be_0 FROM second_level_task WHERE taskId LIKE 'TMPRB22%';
SELECT COUNT(*) AS mtp_rows_should_be_42 FROM merchant_task_progress WHERE taskId IN ('T1.3.5','T1.3.6','T1.3.7','T1.5.1','T1.5.2','T1.5.3','T1.5.4');