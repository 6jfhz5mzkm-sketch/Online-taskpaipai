-- ============================================================
-- #DB-23 second_level_task 新增任务行为语义字段 —— 回滚脚本(rollback)
-- 作用: 删除 actionParam 与 actionType 两列(数据行本身不动;51 行原样保留)
-- 库名: **不写死**,执行方显式指定(dev = merchant_task)
-- 幂等: information_schema 存在性检查前置;两列都在才 DROP;都不在则 SKIP;仅一列则报警待人工介入
-- ⚠️ 回滚后 second_level_task 回到 17 列(加列前的结构);schema.sql 侧需同步回退 v1.11 段 12 两列
-- ============================================================

-- ① 回滚前快照 SELECT(稳定列,可重复执行)
SELECT id, taskId, title, status, firstLevelTaskId, stageId, sortOrder, actionUrl FROM second_level_task ORDER BY id;

-- ② 预检
SET @cols_rb := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'second_level_task' AND COLUMN_NAME IN ('actionType','actionParam'));
SELECT @cols_rb AS action_cols_present_should_be_2;

-- ③ 幂等删列
SET @ddl_drop := IF(@cols_rb = 2, 'ALTER TABLE second_level_task DROP COLUMN actionParam, DROP COLUMN actionType', IF(@cols_rb = 0, 'SELECT ''SKIP: actionType/actionParam 均不存在'' AS info', 'SELECT ''PARTIAL: 仅存在一列,请人工确认后再回滚'' AS info'));
PREPARE stmt_drop FROM @ddl_drop;
EXECUTE stmt_drop;
DEALLOCATE PREPARE stmt_drop;

-- ④ 回滚后校验(期望: 两列均不存在;行数仍 51)
SELECT COUNT(*) AS action_cols_after_should_be_0 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'second_level_task' AND COLUMN_NAME IN ('actionType','actionParam');
SELECT COUNT(*) AS total_rows_should_be_51 FROM second_level_task;