-- ============================================================
-- #DB-22 阶段一任务序号调整 —— 应用脚本(apply)
-- 用户口径: 「签署协议」调整为 T1.3.5、「完成实名认证」为 T1.3.6,其余按插入后顺延、原组不留空号
-- 变更面: second_level_task(taskId/firstLevelTaskId/stageId/sortOrder) + merchant_task_progress(taskId)
-- 库名: **不写死**,执行方显式指定(dev = merchant_task;生产须先过 dev-docs/部署规则.md 确认闸)
-- 幂等: 以主键 id 锚定 + 会话守卫 @db22_pending;**=7 执行**;≠7(=6 表示已应用过,新旧 ID 集合有 6 个重名)则全部 SKIP;
--       其它值(如部分应用中断)需人工介入。注: 已应用后第 ② 步预检会显示 slt=6 / mtp=36,属预期(幂等 SKIP 判据)
-- 两阶段改名: 旧 ID -> TMPDB22_<旧ID> -> 目标 ID,规避 second_level_task.taskId 唯一键与
--             merchant_task_progress 唯一键 (merchantId, taskId) 的中间态冲突
-- 锚点(dev 实测,生产执行前须核对 id 映射是否一致):
--   id=51 T1.5.1 签署协议        -> T1.3.5 (组 T1.5->T1.3, stage opening->application, sort 1->5)
--   id=46 T1.3.5 完成实名认证    -> T1.3.6 (sort 5->6)
--   id=47 T1.3.6 提交入驻申请    -> T1.3.7 (sort 6->7)
--   id=48 T1.3.7 添加商家顾问催审 -> T1.3.8 (sort 7->8)
--   id=52 T1.5.2 联系人信息及地址维护 -> T1.5.1 (sort 2->1)
--   id=53 T1.5.3 开通京东钱包结算账户 -> T1.5.2 (sort 3->2)
--   id=54 T1.5.4 缴费            -> T1.5.3 (sort 4->3)
-- 组(first_level_task)不变: T1.3 由 7 -> 8 个任务,T1.5 由 4 -> 3 个任务;两组 sortOrder 不动
-- ============================================================

-- ① 改前备份 SELECT(执行前先跑,把结果留档)
SELECT id, taskId, firstLevelTaskId, stageId, title, sortOrder FROM second_level_task WHERE id IN (46,47,48,51,52,53,54) ORDER BY id;
SELECT id, merchantId, taskId, status, completedAt FROM merchant_task_progress WHERE taskId IN ('T1.5.1','T1.3.5','T1.3.6','T1.3.7','T1.5.2','T1.5.3','T1.5.4') ORDER BY taskId, id;

-- ② 预检(期望: slt_should_be_7 = 7、mtp_should_be_42 = 42)
SELECT COUNT(*) AS slt_should_be_7 FROM second_level_task WHERE id IN (46,47,48,51,52,53,54) AND taskId IN ('T1.5.1','T1.3.5','T1.3.6','T1.3.7','T1.5.2','T1.5.3','T1.5.4');
SELECT COUNT(*) AS mtp_should_be_42 FROM merchant_task_progress WHERE taskId IN ('T1.5.1','T1.3.5','T1.3.6','T1.3.7','T1.5.2','T1.5.3','T1.5.4');

-- ③ 幂等守卫(7=未应用可执行;0=已应用全 SKIP)
SET @db22_pending := (SELECT COUNT(*) FROM second_level_task WHERE id IN (46,47,48,51,52,53,54) AND taskId IN ('T1.5.1','T1.3.5','T1.3.6','T1.3.7','T1.5.2','T1.5.3','T1.5.4'));
SELECT @db22_pending AS db22_pending_should_be_7_or_0;

-- ④ 阶段1: 旧 ID -> 临时前缀
UPDATE second_level_task SET taskId = CONCAT('TMPDB22_', taskId) WHERE @db22_pending = 7 AND id IN (46,47,48,51,52,53,54) AND taskId IN ('T1.5.1','T1.3.5','T1.3.6','T1.3.7','T1.5.2','T1.5.3','T1.5.4');
UPDATE merchant_task_progress SET taskId = CONCAT('TMPDB22_', taskId) WHERE @db22_pending = 7 AND taskId IN ('T1.5.1','T1.3.5','T1.3.6','T1.3.7','T1.5.2','T1.5.3','T1.5.4');

-- ⑤ 阶段2: 临时名 -> 目标名(second_level_task 同时调整组/stage/sortOrder;merchant_task_progress 只改 taskId)
UPDATE second_level_task SET taskId='T1.3.5', firstLevelTaskId='T1.3', stageId='application', sortOrder=5 WHERE id=51 AND taskId='TMPDB22_T1.5.1';
UPDATE merchant_task_progress SET taskId='T1.3.5' WHERE taskId='TMPDB22_T1.5.1';
UPDATE second_level_task SET taskId='T1.3.6', sortOrder=6 WHERE id=46 AND taskId='TMPDB22_T1.3.5';
UPDATE merchant_task_progress SET taskId='T1.3.6' WHERE taskId='TMPDB22_T1.3.5';
UPDATE second_level_task SET taskId='T1.3.7', sortOrder=7 WHERE id=47 AND taskId='TMPDB22_T1.3.6';
UPDATE merchant_task_progress SET taskId='T1.3.7' WHERE taskId='TMPDB22_T1.3.6';
UPDATE second_level_task SET taskId='T1.3.8', sortOrder=8 WHERE id=48 AND taskId='TMPDB22_T1.3.7';
UPDATE merchant_task_progress SET taskId='T1.3.8' WHERE taskId='TMPDB22_T1.3.7';
UPDATE second_level_task SET taskId='T1.5.1', sortOrder=1 WHERE id=52 AND taskId='TMPDB22_T1.5.2';
UPDATE merchant_task_progress SET taskId='T1.5.1' WHERE taskId='TMPDB22_T1.5.2';
UPDATE second_level_task SET taskId='T1.5.2', sortOrder=2 WHERE id=53 AND taskId='TMPDB22_T1.5.3';
UPDATE merchant_task_progress SET taskId='T1.5.2' WHERE taskId='TMPDB22_T1.5.3';
UPDATE second_level_task SET taskId='T1.5.3', sortOrder=3 WHERE id=54 AND taskId='TMPDB22_T1.5.4';
UPDATE merchant_task_progress SET taskId='T1.5.3' WHERE taskId='TMPDB22_T1.5.4';

-- ⑥ 改后校验 SELECT(期望: T1.3 连续 1..8、T1.5 连续 1..3;残留 0;mtp 42 行;悬挂 0)
SELECT id, taskId, firstLevelTaskId, stageId, title, sortOrder FROM second_level_task WHERE firstLevelTaskId IN ('T1.3','T1.5') ORDER BY firstLevelTaskId, sortOrder;
SELECT COUNT(*) AS tmp_residue_should_be_0 FROM second_level_task WHERE taskId LIKE 'TMPDB22%';
SELECT COUNT(*) AS mtp_rows_should_be_42 FROM merchant_task_progress WHERE taskId IN ('T1.3.5','T1.3.6','T1.3.7','T1.3.8','T1.5.1','T1.5.2','T1.5.3');
SELECT COUNT(*) AS mtp_dangling_should_be_0 FROM merchant_task_progress p LEFT JOIN second_level_task s ON s.taskId = p.taskId WHERE s.id IS NULL;